"""LE MODULE DE SYNCHRONISATION MONTANTE (F113) — AtomBox → IMAP, hors processus.

Un geste dans le webmail (lu, drapeau, déplacement) écrit le rattachement et émet
`rattachement.change`. Ce module le consomme : il ouvre la boîte, pose le STORE, déplace si le
dossier a changé, et met à jour l'UID. Un serveur IMAP injoignable n'empêche pas le clic : la
file réessaie (D161), et IMAP finira par recevoir l'état."""
from __future__ import annotations
import os, uuid
from sqlalchemy import select
from ..ingestion.imap import Releve
from ..journal import journal
from ..modules import Module, evenement
from ..schema.modeles import Adresse, Boite, Dossier, Rattachement
from .sync import drapeaux_voulus

log = journal("imap")

def config_imap() -> dict:
    return {"hote": os.environ.get("ATOMBOX_IMAP_HOTE"), "port": int(os.environ.get("ATOMBOX_IMAP_PORT", "993")),
            "master": (os.environ.get("ATOMBOX_IMAP_MASTER") or "").strip(),
            "mot_de_passe": os.environ.get("ATOMBOX_IMAP_MOT_DE_PASSE")}

def login_de(adresse: str, master: str) -> str:
    """« boîte*master » avec un compte master (chapitre 06) ; l'adresse seule sinon"""
    return adresse if not master or master.lower() == adresse.lower() else "%s*%s" % (adresse, master)

class ModuleSync(Module):
    nom = "sync"; version = "0.1"; interne = True
    description = "synchronisation montante des états vers IMAP : STORE et MOVE (F113, D140b)"

    @evenement("rattachement.change")
    def pousser(self, ctx):
        s, charge = ctx["session"], ctx["charge"]
        comm_id, boite_id = uuid.UUID(charge["comm_id"]), uuid.UUID(charge["boite_id"])
        r = s.get(Rattachement, (comm_id, boite_id))
        if r is None: log.debug("rattachement %s/%s disparu — rien à pousser", comm_id, boite_id); return
        if r.uid_imap is None:
            log.debug("%s : pas d'UID IMAP (message écrit ici, pas encore relevé) — rien à pousser", comm_id); return
        cfg = config_imap()
        if not cfg["hote"]:
            log.warning("ATOMBOX_IMAP_HOTE absent : synchronisation montante impossible"); return
        boite = s.get(Boite, boite_id); adresse = s.get(Adresse, boite.adresse_id).adresse_complete
        source = s.get(Dossier, charge.get("dossier_avant") and uuid.UUID(charge["dossier_avant"]) or r.dossier_id)
        cible = s.get(Dossier, r.dossier_id)
        if source is None or cible is None:
            log.warning("%s : dossier IMAP inconnu — rien à pousser", comm_id); return
        releve = Releve(cfg["hote"], cfg["port"]).ouvrir(login_de(adresse, cfg["master"]), cfg["mot_de_passe"])
        try:
            releve.selectionner(source.alias_imap or source.nom, ecriture=True)
            poser, retirer = drapeaux_voulus(r)
            releve.poser_drapeaux(r.uid_imap, poser, retirer)
            if cible.dossier_id != source.dossier_id:
                neuf = releve.deplacer(r.uid_imap, cible.alias_imap or cible.nom)
                r.uid_imap = neuf                      # None : le prochain passage le retrouvera
                s.commit()
            log.info("%s : état poussé vers %s/%s (uid %s)", comm_id, adresse, cible.alias_imap, r.uid_imap)
        finally:
            releve.fermer()
