"""LE DÉMON D'INGESTION (F001) — une tâche par boîte administrée, tous les dossiers, reprise par
UID, IDLE sur la boîte de réception ; les dossiers IMAP deviennent des `dossier` (F102).

    DATABASE_URL=postgresql:///atombox ATOMBOX_MAGASIN=/var/lib/atombox/magasin \\
    ATOMBOX_IMAP_HOTE=imap.exemple.fr ATOMBOX_IMAP_MASTER=masteruser ATOMBOX_IMAP_MOT_DE_PASSE=… \\
    python3 -m atombox.ingestion.demon

Échouer bruyamment plutôt que deux fois (D152) : un message qui ne s'ingère pas est journalisé
avec sa raison et le démon passe au suivant — il ne réessaie pas en boucle, il ne s'arrête pas.
"""
from __future__ import annotations
import asyncio, logging, os
from sqlalchemy import select
from ..db import session as ouvrir_session
from ..schema.modeles import Adresse, Boite, Dossier
from ..magasin import Magasin
from ..uuid7 import uuid7
from .imap import Releve
from .ingestion import ingerer

log = logging.getLogger("atombox.ingestion")

def _dossier(s, boite_id, alias: str) -> Dossier:
    d = s.scalar(select(Dossier).where(Dossier.boite_id == boite_id, Dossier.alias_imap == alias))
    if d: return d
    d = Dossier(dossier_id=uuid7(), boite_id=boite_id, nom=alias.split("/")[-1], alias_imap=alias,
                protege=alias.upper() in ("INBOX", "SENT", "DRAFTS", "TRASH", "JUNK"))
    s.add(d); s.commit()
    return d

def relever_boite(s, magasin: Magasin, releve: Releve, boite_id, adresse: str) -> int:
    """un passage complet sur tous les dossiers d'une boîte ; rend le nombre de messages ingérés"""
    n = 0
    for alias in releve.dossiers():
        d = _dossier(s, boite_id, alias)
        validity, uidnext = releve.selectionner(alias)
        depuis = d.uid_suivant or 1
        if d.uid_validity is not None and d.uid_validity != validity:
            log.warning("%s/%s : UIDVALIDITY a changé (%s → %s) — resynchronisation depuis 1 (D043)", adresse, alias, d.uid_validity, validity)
            depuis = 1
        for uid in releve.nouveaux(depuis):
            try:
                octets, date, drapeaux = releve.lire(uid)
                r = ingerer(s, magasin, boite_id, octets, uid=uid, uid_validity=validity, dossier_id=d.dossier_id, date_recue=date)
                n += 1
                log.info("%s/%s uid %d → %s (%s)", adresse, alias, uid, "nouveau" if r["nouveau"] else "rattaché", r["nature"])
            except Exception as e:
                s.rollback()
                log.error("%s/%s uid %d : NON INGÉRÉ — %s", adresse, alias, uid, e)   # bruyant, et on continue (D152)
            finally:
                d.uid_validity, d.uid_suivant = validity, uid + 1; s.commit()
        if not releve.nouveaux(depuis):
            d.uid_validity, d.uid_suivant = validity, max(depuis, uidnext); s.commit()
    return n

async def surveiller_boite(boite_id, adresse: str, config: dict):
    while True:
        try:
            s = ouvrir_session(); magasin = Magasin(config["magasin"])
            releve = Releve(config["hote"], config["port"]).ouvrir("%s*%s" % (adresse, config["master"]), config["mot_de_passe"])
            try:
                while True:
                    await asyncio.to_thread(relever_boite, s, magasin, releve, boite_id, adresse)
                    releve.selectionner("INBOX")
                    await asyncio.to_thread(releve.idle, 25 * 60)
            finally:
                releve.fermer(); s.close()
        except Exception as e:
            log.error("%s : %s — nouvelle tentative dans 60 s", adresse, e)
            await asyncio.sleep(60)

async def principal():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = { "hote": os.environ["ATOMBOX_IMAP_HOTE"], "port": int(os.environ.get("ATOMBOX_IMAP_PORT", "993")),
               "master": os.environ.get("ATOMBOX_IMAP_MASTER", "masteruser"), "mot_de_passe": os.environ["ATOMBOX_IMAP_MOT_DE_PASSE"],
               "magasin": os.environ.get("ATOMBOX_MAGASIN", "./magasin") }
    with ouvrir_session() as s:
        boites = s.execute(select(Boite.boite_id, Adresse.adresse_complete).join(Adresse, Adresse.adresse_id == Boite.adresse_id)).all()
    log.info("%d boîte(s) administrée(s)", len(boites))
    await asyncio.gather(*(surveiller_boite(b.boite_id, b.adresse_complete, config) for b in boites))

if __name__ == "__main__":
    asyncio.run(principal())
