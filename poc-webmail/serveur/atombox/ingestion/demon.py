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
from ..db import connecter
from ..magasin import Magasin
from ..uuid7 import uuid7
from .imap import Releve
from .ingestion import ingerer

log = logging.getLogger("atombox.ingestion")

def _dossier(cnx, boite_id, alias: str):
    r = cnx.execute('select dossier_id, uid_validity, uid_suivant from dossier where boite_id=%s and alias_imap=%s', (boite_id, alias)).fetchone()
    if r: return r
    did = uuid7()
    cnx.execute('insert into dossier (dossier_id, boite_id, nom, alias_imap, protege) values (%s,%s,%s,%s,%s)', (did, boite_id, alias.split("/")[-1], alias, alias.upper() in ("INBOX", "SENT", "DRAFTS", "TRASH", "JUNK")))
    cnx.commit()
    return {"dossier_id": did, "uid_validity": None, "uid_suivant": None}

def relever_boite(cnx, magasin: Magasin, releve: Releve, boite_id, adresse: str) -> int:
    """un passage complet sur tous les dossiers d'une boîte ; rend le nombre de messages ingérés"""
    n = 0
    for alias in releve.dossiers():
        d = _dossier(cnx, boite_id, alias)
        validity, uidnext = releve.selectionner(alias)
        depuis = d["uid_suivant"] or 1
        if d["uid_validity"] is not None and d["uid_validity"] != validity:
            log.warning("%s/%s : UIDVALIDITY a changé (%s → %s) — resynchronisation depuis 1 (D043)", adresse, alias, d["uid_validity"], validity)
            depuis = 1
        for uid in releve.nouveaux(depuis):
            try:
                octets, date, drapeaux = releve.lire(uid)
                r = ingerer(cnx, magasin, boite_id, octets, uid=uid, uid_validity=validity, dossier_id=d["dossier_id"], date_recue=date)
                n += 1
                log.info("%s/%s uid %d → %s (%s)", adresse, alias, uid, "nouveau" if r["nouveau"] else "rattaché", r["nature"])
            except Exception as e:
                log.error("%s/%s uid %d : NON INGÉRÉ — %s", adresse, alias, uid, e)   # bruyant, et on continue (D152)
            finally:
                cnx.execute('update dossier set uid_validity=%s, uid_suivant=%s where dossier_id=%s', (validity, uid + 1, d["dossier_id"])); cnx.commit()
        if not releve.nouveaux(depuis):
            cnx.execute('update dossier set uid_validity=%s, uid_suivant=%s where dossier_id=%s', (validity, max(depuis, uidnext), d["dossier_id"])); cnx.commit()
    return n

async def surveiller_boite(boite_id, adresse: str, config: dict):
    while True:
        try:
            cnx = connecter(); magasin = Magasin(config["magasin"])
            releve = Releve(config["hote"], config["port"]).ouvrir("%s*%s" % (adresse, config["master"]), config["mot_de_passe"])
            try:
                while True:
                    await asyncio.to_thread(relever_boite, cnx, magasin, releve, boite_id, adresse)
                    releve.selectionner("INBOX")
                    await asyncio.to_thread(releve.idle, 25 * 60)
            finally:
                releve.fermer(); cnx.close()
        except Exception as e:
            log.error("%s : %s — nouvelle tentative dans 60 s", adresse, e)
            await asyncio.sleep(60)

async def principal():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = { "hote": os.environ["ATOMBOX_IMAP_HOTE"], "port": int(os.environ.get("ATOMBOX_IMAP_PORT", "993")),
               "master": os.environ.get("ATOMBOX_IMAP_MASTER", "masteruser"), "mot_de_passe": os.environ["ATOMBOX_IMAP_MOT_DE_PASSE"],
               "magasin": os.environ.get("ATOMBOX_MAGASIN", "./magasin") }
    with connecter() as cnx:
        boites = cnx.execute('select b.boite_id, a.adresse_complete from boite b join adresse a using (adresse_id)').fetchall()
    log.info("%d boîte(s) administrée(s)", len(boites))
    await asyncio.gather(*(surveiller_boite(b["boite_id"], b["adresse_complete"], config) for b in boites))

if __name__ == "__main__":
    asyncio.run(principal())
