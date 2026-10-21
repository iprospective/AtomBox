"""LE DÉMON D'INGESTION (F001) — une tâche par boîte administrée, tous les dossiers, reprise par
UID, IDLE sur la boîte de réception ; les dossiers IMAP deviennent des `dossier` (F102).

    DATABASE_URL=postgresql:///atombox ATOMBOX_STORE=/var/lib/atombox/magasin \\
    ATOMBOX_IMAP_HOST=imap.exemple.fr ATOMBOX_IMAP_MASTER=masteruser ATOMBOX_IMAP_PASSWORD=… \\
    python3 -m atombox.ingestion.daemon

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
from .imap import Poller, tls_imap
from .ingestion import ingest
from ..modules import loading
from ..modules.hooks import hooks
from .. import settings

log = journal("daemon")

def _folder(s, boite_id, alias: str) -> Dossier:
    d = s.scalar(select(Dossier).where(Dossier.boite_id == boite_id, Dossier.alias_imap == alias))
    if d: return d
    from ..imap import mutf7
    # `alias_imap` : le nom du FIL (modified UTF-7) ; `nom` : ce qu'on LIT (« Pièces », pas « Pi&AOg-ces »)
    d = Dossier(dossier_id=uuid7(), boite_id=boite_id, nom=mutf7.decode(alias.split("/")[-1]), alias_imap=alias,
                protege=alias.upper() in ("INBOX", "SENT", "DRAFTS", "TRASH", "JUNK"))
    s.add(d); s.commit()
    return d

def poll_mailbox(s, store: Store, releve: Poller, boite_id, adresse: str) -> int:
    """un passage complet sur tous les dossiers d'une boîte ; rend le nombre de messages ingérés"""
    n = 0
    log.debug("%s : relève", adresse)
    for alias in releve.folders():
        d = _folder(s, boite_id, alias)
        validity, uidnext = releve.select_folder(alias)
        since = d.uid_suivant or 1
        if d.uid_validity is not None and d.uid_validity != validity:
            log.warning("%s/%s : UIDVALIDITY a changé (%s → %s) — resynchronisation depuis 1 (D043)", adresse, alias, d.uid_validity, validity)
            since = 1
        for uid in releve.new_uids(since):
            try:
                raw_bytes, date, drapeaux = releve.read(uid)
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
            # compte master (chapitre 06) : « boite*master » ; sans master, ou si le master EST la boîte, le login est l'adresse
            master = (config.get("master") or "").strip()
            login = adresse if not master or master.lower() == adresse.lower() else "%s*%s" % (adresse, master)
            releve = Poller(config["hote"], config["port"], tls=tls_imap()).connect(login, config["mot_de_passe"])
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
    config = { "hote": settings.read("ATOMBOX_IMAP_HOST"), "port": int(settings.read("ATOMBOX_IMAP_PORT", "993")),
               "master": settings.read("ATOMBOX_IMAP_MASTER", "masteruser"), "mot_de_passe": settings.read("ATOMBOX_IMAP_PASSWORD"),
               "magasin": settings.read("ATOMBOX_STORE", "./magasin") }
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
