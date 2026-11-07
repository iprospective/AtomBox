"""LE DÉMON D'INGESTION (F001) — une tâche par boîte administrée, tous les dossiers, reprise par
UID, IDLE sur la boîte de réception ; les dossiers IMAP deviennent des `dossier` (F102).

    DATABASE_URL=postgresql:///atombox ATOMBOX_STORE=/var/lib/atombox/magasin \\
    ATOMBOX_IMAP_HOST=imap.exemple.fr ATOMBOX_IMAP_MASTER=masteruser ATOMBOX_IMAP_PASSWORD=… \\
    python3 -m atombox.ingestion.daemon

Sans compte master, chaque boîte entre avec ses propres identifiants : `/etc/atombox/boxes`
(credentials.py).

Échouer bruyamment plutôt que deux fois (D152) : un message qui ne s'ingère pas est journalisé
avec sa raison et le démon passe au suivant — il ne réessaie pas en boucle, il ne s'arrête pas.
"""
from __future__ import annotations
import asyncio, os
from ..journal import journal
from sqlalchemy import select
from ..db import session as open_session
from ..schema.models import Adresse, Boite, Dossier, Evenement, Rattachement
from ..sync.sync import apply_down_sync
from ..store import Store
from ..uuid7 import uuid7
from .imap import Poller, open_mailbox
from .ingestion import ingest
from ..modules import loading
from ..modules.hooks import hooks
from .. import settings

log = journal("daemon")

def _folder(s, boite_id, alias: str, presents=()) -> Dossier:
    d = s.scalar(select(Dossier).where(Dossier.boite_id == boite_id, Dossier.alias_imap == alias))
    # UN DOSSIER DU FOURNISSEUR QUI EST UNE BOÎTE D'ÉTAT (« Archives », « Spam »…) est ADOPTÉ par la
    # boîte d'état d'AtomBox, si celle-ci pointe vers un nom que le fournisseur n'a pas — au lieu d'en
    # faire un dossier ordinaire à côté (04/11). Un ordinaire déjà créé ainsi y est fondu.
    from ..services.mailbox import state_named, state_box, fold_into_state
    etat = state_named(alias)
    if etat and (d is None or d.exit_reason is None):
        box = state_box(s, boite_id, etat)
        if box is not None and box.alias_imap != alias and box.alias_imap not in presents:
            if d is not None:
                from ..services import personal_state as personal
                from ..schema.models import Acces
                # le journal veut un auteur : celui qui relève, sinon le premier membre de la boîte
                qui = personal.polling_account(s, boite_id) or s.scalar(
                    select(Acces.compte_id).where(Acces.boite_id == boite_id, Acces.fin.is_(None)).limit(1))
                n = fold_into_state(s, d, box, qui)
                log.info("dossier « %s » fondu dans la boîte d'état %s (%d message(s))", alias, etat, n)
            else:
                box.alias_imap, box.uid_validity, box.uid_suivant = alias, None, None
                log.info("dossier « %s » du fournisseur adopté par la boîte d'état %s", alias, etat)
            s.commit()
            return box
    if d: return d
    from ..imap import mutf7
    # `alias_imap` : le nom du FIL (modified UTF-7) ; `nom` : ce qu'on LIT (« Pièces », pas « Pi&AOg-ces »)
    d = Dossier(dossier_id=uuid7(), boite_id=boite_id, nom=mutf7.decode(alias.split("/")[-1]), alias_imap=alias,
                protege=alias.upper() in ("INBOX", "SENT", "DRAFTS", "TRASH", "JUNK"))
    s.add(d); s.commit()
    return d

# ── LA COLLECTE QUI VIDE LA SOURCE (D205, RM3645) ──────────────────────────────────────────────────
# Une option PAR BOÎTE : `ATOMBOX_COLLECT_MOVE` liste les adresses (virgules ou blancs ; « * » = toutes). Une fois
# le message stocké et VÉRIFIÉ (le magasin le reconstitue à l'octet, RM3631), il est DÉPLACÉ à la source dans
# « AtomBox/Relevé » — jamais effacé : le fournisseur garde tout, sa boîte de réception se vide. AtomBox devient la
# vérité de ce message : son `uid_imap` est remis à vide, et les deux synchronisations d'état (montante, F113 ;
# descendante, sync_down) ne le touchent plus. Ce dossier-là n'est jamais relevé (sinon tout reviendrait en boucle).
# Seul le courrier REÇU part : envoyés et brouillons restent où les autres clients les cherchent.
COLLECTED_FOLDER = "AtomBox/Relev&AOk-"          # « AtomBox/Relevé », en modified UTF-7 (le nom du fil)
_COLLECT_PARENT = "AtomBox"
COLLECT_BATCH = 200                              # par dossier et par passage : un premier passage sur une grosse boîte


def collect_moves(adresse: str) -> bool:
    """l'option de D205 est-elle active pour cette boîte ? (relue à chaque passage)"""
    v = (settings.read("ATOMBOX_COLLECT_MOVE") or "").replace(",", " ").lower().split()
    return "*" in v or (adresse or "").lower() in v


def never_polled(alias: str) -> bool:
    """« AtomBox/Relevé » (et son parent) : ce que la collecte y range n'est jamais relu (D205 § 3)"""
    return alias in (COLLECTED_FOLDER, _COLLECT_PARENT) or alias.startswith(COLLECTED_FOLDER + "/")


def _received_folder(d) -> bool:
    from ..services.messages import special_of
    return not (d.special_use in ("\\Sent", "\\Drafts") or special_of(d.alias_imap) in ("sent", "drafts"))


def move_collected(s, store: Store, releve: Poller, boite_id, adresse: str, d, bruts: dict | None = None,
                   batch: int = COLLECT_BATCH) -> int:
    """déplace à la source ce qui, dans ce dossier, est stocké ET vérifié ; rend le nombre de messages déplacés.
    Un message que le magasin ne reconstitue pas, ou un MOVE refusé, reste à la source, garde son UID (donc sa
    synchronisation), et sera rejoué au passage suivant — bruyamment, jamais en silence (D152)."""
    if not collect_moves(adresse) or not _received_folder(d):
        return 0
    from ..schema.models import Rattachement
    ratts = list(s.scalars(select(Rattachement).where(Rattachement.boite_id == boite_id,
                                                      Rattachement.dossier_id == d.dossier_id,
                                                      Rattachement.uid_imap.isnot(None)).limit(batch)))
    if not ratts:
        return 0
    if not getattr(releve, "_collect_ready", False):
        if COLLECTED_FOLDER not in releve.folders():
            releve.create_folder(COLLECTED_FOLDER)
        releve._collect_ready = True
    releve.select_folder(d.alias_imap, writable=True)
    bruts = bruts or {}
    n = 0
    for r in ratts:
        uid = r.uid_imap
        try:
            source = bruts.get(uid)
            if source is None:
                source = releve.read(uid)[0]
            if store.read_message(str(r.comm_id)) != source:
                log.error("%s/%s uid %d : le magasin ne reconstitue pas l'original à l'octet — LAISSÉ à la source",
                          adresse, d.alias_imap, uid)
                continue
            releve.move(uid, COLLECTED_FOLDER)
        except Exception as e:
            s.rollback()
            log.error("%s/%s uid %d : non déplacé vers « AtomBox/Relevé » — %s (rejoué au prochain passage)",
                      adresse, d.alias_imap, uid, e)
            continue
        r.uid_imap = None              # AtomBox devient la vérité de ce message (D205 § 2)
        s.commit(); n += 1
    if n:
        log.info("%s/%s : %d message(s) déplacé(s) vers « AtomBox/Relevé » (D205)", adresse, d.alias_imap, n)
    return n


def poll_mailbox(s, store: Store, releve: Poller, boite_id, adresse: str) -> int:
    """un passage complet sur tous les dossiers d'une boîte ; rend le nombre de messages ingérés"""
    n = 0
    log.debug("%s : relève", adresse)
    presents = [a for a in releve.folders() if not never_polled(a)]
    for alias in presents:
        d = _folder(s, boite_id, alias, presents)
        validity, uidnext = releve.select_folder(alias)
        since = d.uid_suivant or 1
        if d.uid_validity is not None and d.uid_validity != validity:
            log.warning("%s/%s : UIDVALIDITY a changé (%s → %s) — resynchronisation depuis 1 (D043)", adresse, alias, d.uid_validity, validity)
            since = 1
        bruts = {}                    # ce qu'on vient de lire : la collecte (D205) le compare au magasin sans relire
        for uid in releve.new_uids(since):
            try:
                raw_bytes, date, drapeaux = releve.read(uid)
                if collect_moves(adresse): bruts[uid] = raw_bytes
                # LE SENS PAR LE DOSSIER DU FOURNISSEUR (D185) : ce qui est dans ses Envoyés ou ses
                # Brouillons est ÉMIS. La relève passait « reçu » pour tout — deux messages de nos
                # Envoyés étaient marqués reçus (mesuré le 21/10).
                from ..services.messages import special_of
                r = ingest(s, store, boite_id, raw_bytes, uid=uid, uid_validity=validity, dossier_id=d.dossier_id,
                            date_recue=date, dossier_alias=d.alias_imap,
                            sens="out" if (d.special_use in ("\\Sent", "\\Drafts")
                                           or special_of(d.alias_imap) in ("sent", "drafts")) else "in")
                n += 1
                log.debug("%s/%s uid %d → %s (%s)", adresse, alias, uid, "nouveau" if r["nouveau"] else "rattaché", r["nature"])
            except Exception as e:
                s.rollback()
                log.error("%s/%s uid %d : NON INGÉRÉ — %s", adresse, alias, uid, e)   # bruyant, et on continue (D152)
            finally:
                d.uid_validity, d.uid_suivant = validity, uid + 1; s.commit()
        if not releve.new_uids(since):
            d.uid_validity, d.uid_suivant = validity, max(since, uidnext); s.commit()
        # ce que les AUTRES clients ont changé descend maintenant (F113)
        try: sync_down(s, releve, boite_id, adresse, d)
        except Exception as e:
            s.rollback(); log.error("%s/%s : synchronisation descendante en échec — %s", adresse, alias, e)
        # puis, si l'option est active, ce qui est stocké et vérifié quitte la source (D205)
        try: move_collected(s, store, releve, boite_id, adresse, d, bruts)
        except Exception as e:
            s.rollback(); log.error("%s/%s : collecte (déplacement à la source) en échec — %s", adresse, alias, e)
    if n: log.info("%s : %d message(s) ingéré(s)", adresse, n)
    return n


def sync_down(s, releve: Poller, boite_id, adresse: str, dossier, batch: int = 500) -> int:
    """IMAP → AtomBox (F113) : ce que les AUTRES clients ont fait (lu dans Thunderbird, drapeau posé
    depuis le téléphone) descend dans le rattachement. On ne relit que les UID qu'on connaît : un
    message inconnu n'est pas un changement d'état, c'est une ingestion."""
    ratts = list(s.scalars(select(Rattachement).where(Rattachement.boite_id == boite_id,
                                                      Rattachement.dossier_id == dossier.dossier_id,
                                                      Rattachement.uid_imap.isnot(None)).limit(batch)))
    if not ratts: return 0
    # Ne JAMAIS écraser un état dont l'ordre montant n'est pas encore parti : entre le clic et le
    # STORE, IMAP ignore ce que l'utilisateur vient de faire — appliquer « IMAP fait foi » à cet
    # instant-là rendrait ses messages non lus à chaque relève (F113).
    in_flight = {str(e.charge.get("comm_id")) for e in s.scalars(
        select(Evenement).where(Evenement.type == "rattachement.change", Evenement.traite_le.is_(None)))}
    if in_flight:
        guards = [r for r in ratts if str(r.comm_id) in in_flight]
        if guards: log.debug("%s : %d état(s) en vol vers IMAP — non écrasés", dossier.alias_imap, len(guards))
        ratts = [r for r in ratts if str(r.comm_id) not in in_flight]
    par_uid = {r.uid_imap: r for r in ratts}
    n = 0
    for uid, f in releve.flags(sorted(par_uid)).items():
        r = par_uid.get(uid)
        if r is None: continue
        change = apply_down_sync(s, r, f)
        if change:
            n += 1
            # ÉTAT.DESCENDU (RM3632) : un changement venu du fournisseur (un client branché directement
            # sur le serveur mail) se voit aussi en direct. Pas `rattachement.change` : celui-là
            # repartirait vers le fournisseur — la boucle.
            from ..modules import events
            events.emit(s, "etat.descendu", {"comm_id": str(r.comm_id), "boite_id": str(r.boite_id),
                                              "sens": r.sens, "change": change}, cible=None)
            log.info("%s/%s uid %d : %s (venu d'IMAP)", adresse, dossier.alias_imap, uid, ", ".join(change))
    if n: s.commit()
    return n

def _next_uid(s, boite_id, alias: str) -> int | None:
    """le prochain UID qu'on attend dans ce dossier — ce que la relève a déjà vu"""
    s.expire_all()
    return s.scalar(select(Dossier.uid_suivant).where(Dossier.boite_id == boite_id, Dossier.alias_imap == alias))


def _resync(s, releve: Poller, boite_id, adresse: str, alias: str) -> int:
    """la synchronisation descendante d'UN dossier, déjà sélectionné"""
    d = s.scalar(select(Dossier).where(Dossier.boite_id == boite_id, Dossier.alias_imap == alias))
    if d is None: return 0
    try: return sync_down(s, releve, boite_id, adresse, d)
    except Exception as e:
        s.rollback(); log.error("%s/%s : synchronisation descendante en échec — %s", adresse, alias, e); return 0


async def watch_mailbox(boite_id, adresse: str, config: dict):
    while True:
        try:
            s = open_session(); store = Store(config["magasin"])
            # les identifiants sont relus à CHAQUE tentative (credentials.py) : une boîte ajoutée au
            # fichier des identifiants est prise à la tentative suivante, sans redémarrer
            releve = open_mailbox(adresse)
            try:
                while True:
                    await asyncio.to_thread(poll_mailbox, s, store, releve, boite_id, adresse)
                    _, uidnext = releve.select_folder("INBOX")
                    # UN MESSAGE ARRIVÉ PENDANT LA RELÈVE existe déjà quand IDLE commence, et IDLE ne
                    # signale que ce qui arrive APRÈS (RFC 2177) : il attendait le réveil suivant, 25
                    # minutes. UIDNEXT le dit — on relève encore au lieu de s'endormir (RM3188).
                    if uidnext > (_next_uid(s, boite_id, "INBOX") or 1):
                        log.debug("%s : du courrier est arrivé pendant la relève (uidnext %d) — on relève encore", adresse, uidnext)
                        continue
                    # MÊME FENÊTRE POUR LES DRAPEAUX : un état changé ailleurs PENDANT la relève, après la
                    # synchronisation de ce dossier, est effacé de la session par l'EXAMINE — IDLE ne le
                    # signalera pas. On relit les drapeaux d'INBOX juste avant de s'endormir. Le remède
                    # industriel est CONDSTORE/QRESYNC (RFC 7162) : ne relire que ce qui a changé.
                    await asyncio.to_thread(_resync, s, releve, boite_id, adresse, "INBOX")
                    await asyncio.to_thread(releve.idle, int(os.environ.get("ATOMBOX_IDLE_SECONDS", str(25 * 60))))
            finally:
                releve.close(); s.close()
        except Exception as e:
            log.error("%s : %s — nouvelle tentative dans 60 s", adresse, e)
            await asyncio.sleep(60)

async def main():
    config = { "hote": settings.read("ATOMBOX_IMAP_HOST"), "magasin": settings.read("ATOMBOX_STORE", "./magasin") }
    with open_session() as s:
        boites = s.execute(select(Boite.boite_id, Adresse.adresse_complete).join(Adresse, Adresse.adresse_id == Boite.adresse_id)).all()
    # grosses infrastructures (D161) : N démons se partagent les boîtes — ATOMBOX_PART="2/4" prend la 2e part sur 4
    part = settings.read("ATOMBOX_PART")
    if part:
        i, n = (int(x) for x in part.split("/")); boites = [b for b in boites if int(b.boite_id.hex, 16) % n == i - 1]
        log.info("part %s : %d boîte(s)", part, len(boites))
    loading.load()
    log.info("démarrage : %d boîte(s) administrée(s), hôte %s, magasin %s", len(boites), config["hote"], config["magasin"])
    hooks.emit("demon.demarrage", boites=boites)
    await asyncio.gather(*(watch_mailbox(b.boite_id, b.adresse_complete, config) for b in boites))

if __name__ == "__main__":
    asyncio.run(main())
