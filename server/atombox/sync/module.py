"""LE MODULE DE SYNCHRONISATION MONTANTE (F113) — AtomBox → IMAP, hors processus.

Un geste dans le webmail (lu, drapeau, déplacement) écrit le rattachement et émet
`rattachement.change`. Ce module le consomme : il ouvre la boîte, pose le STORE, déplace si le
dossier a changé, et met à jour l'UID. Un serveur IMAP injoignable n'empêche pas le clic : la
file réessaie (D161), et IMAP finira par recevoir l'état."""
from __future__ import annotations
import os, uuid
from sqlalchemy import select
from ..ingestion.imap import open_mailbox
from ..journal import journal
from ..modules import Module, event
from ..schema.models import Adresse, Boite, CommEmail, Dossier, Rattachement
from .sync import wanted_flags
from .. import settings

log = journal("imap")


class ModuleSync(Module):
    nom = "sync"; version = "0.1"; interne = True
    description = "synchronisation montante des états vers IMAP : STORE et MOVE (F113, D140b)"

    @event("rattachement.change")
    def push(self, ctx):
        s, charge = ctx["session"], ctx["charge"]
        comm_id, boite_id = uuid.UUID(charge["comm_id"]), uuid.UUID(charge["boite_id"])
        # LA place qui a changé (D185). Un événement d'avant D185 ne porte pas de sens : c'est alors
        # la place reçue s'il y en a une — la seule qui existait.
        r = s.get(Rattachement, (comm_id, boite_id, charge.get("sens") or "in")) \
            or (None if charge.get("sens") else s.get(Rattachement, (comm_id, boite_id, "out")))
        if r is None: log.debug("rattachement %s/%s disparu — rien à pousser", comm_id, boite_id); return
        if r.uid_imap is None:
            log.debug("%s : pas d'UID IMAP (message écrit ici, pas encore relevé) — rien à pousser", comm_id); return
        if not settings.read("ATOMBOX_IMAP_HOST"):
            log.warning("ATOMBOX_IMAP_HOST absent : synchronisation montante impossible"); return
        boite = s.get(Boite, boite_id); adresse = s.get(Adresse, boite.adresse_id).adresse_complete
        source = s.get(Dossier, charge.get("dossier_avant") and uuid.UUID(charge["dossier_avant"]) or r.dossier_id)
        cible = s.get(Dossier, r.dossier_id)
        if source is None or cible is None:
            log.warning("%s : dossier IMAP inconnu — rien à pousser", comm_id); return
        releve = open_mailbox(adresse)
        try:
            releve.select_folder(source.alias_imap or source.nom, writable=True)
            # Les drapeaux qu'on POUSSE sont ceux du membre qui relève (D175 § 3) : le
            # fournisseur n'a qu'un jeu de drapeaux, et c'est le sien qui le représente.
            from ..services import personal_state as personal
            releveur = personal.polling_account(s, boite_id)
            add, remove = wanted_flags(r, personal.state_sync(s, releveur, r.comm_id, r.boite_id))
            releve.set_flags(r.uid_imap, add, remove)
            if cible.dossier_id != source.dossier_id:
                neuf = releve.move(r.uid_imap, cible.alias_imap or cible.nom)
                r.uid_imap = neuf                      # None : le prochain passage le retrouvera
                s.commit()
            log.info("%s : état poussé vers %s/%s (uid %s)", comm_id, adresse, cible.alias_imap, r.uid_imap)
        finally:
            releve.close()

    @event("message.envoye")
    def copy_sent(self, ctx):
        """D140c — l'envoi est copié dans le dossier IMAP des envoyés, marqué lu : sinon le téléphone ne
        voit AUCUN message envoyé depuis AtomBox, et l'utilisateur croit que rien n'est parti.

        Une tâche À PART, abonnée à `message.envoye` : si IMAP est injoignable, c'est la COPIE qui
        réessaie (D161) — jamais l'envoi, qui partirait une seconde fois chez le destinataire. Et elle
        est idempotente : rejouée, elle retrouve sa copie par le Message-ID au lieu d'en faire une
        autre. Disparaît avec la V3, quand Dovecot lira le stockage d'AtomBox (Q024)."""
        s, charge = ctx["session"], ctx["charge"]
        comm_id, boite_id = uuid.UUID(charge["comm_id"]), uuid.UUID(charge["boite_id"])
        r = s.get(Rattachement, (comm_id, boite_id, "out"))          # un envoi est une place ÉMISE (D185)
        if r is None or r.uid_imap is not None:
            log.debug("%s : rien à copier (%s)", comm_id, "déjà dans IMAP" if r is not None else "rattachement disparu"); return
        if not settings.read("ATOMBOX_IMAP_HOST"):
            log.warning("ATOMBOX_IMAP_HOST absent : l'envoi %s n'est pas copié dans IMAP", comm_id); return
        dossier = s.get(Dossier, r.dossier_id)
        if dossier is None or not (dossier.alias_imap or dossier.nom):
            log.warning("%s : dossier des envoyés inconnu — rien à copier", comm_id); return
        from ..store import Store
        raw_bytes = Store(settings.read("ATOMBOX_STORE", "./magasin")).read(str(comm_id))
        e = s.get(CommEmail, comm_id)
        boite = s.get(Boite, boite_id); adresse = s.get(Adresse, boite.adresse_id).adresse_complete
        releve = open_mailbox(adresse)
        try:
            alias = dossier.alias_imap or dossier.nom
            releve.select_folder(alias, writable=True)
            uid = releve.find_message_id(e.message_id if e else None)
            if uid is None:
                uid = releve.append(alias, raw_bytes)
            else:
                log.info("%s : déjà copié dans %s (uid %d) — une tâche rejouée ne duplique pas", comm_id, alias, uid)
            r.uid_imap = uid
            s.commit()
        finally:
            releve.close()
