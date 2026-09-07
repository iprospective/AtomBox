"""LE SUIVI DES ENVOIS (D099, F109) — où en est chaque message émis, destinataire par destinataire,
et la RELANCE d'un envoi qui n'est pas parti.

Un envoi n'échoue pas en bloc : chaque destinataire a son état (préparé, remis au relais, rejeté).
Relancer, c'est remettre l'événement `message.a_envoyer` dans la file (D161 : au moins une fois) —
jamais réémettre en direct depuis une requête HTTP, qui n'a pas le droit d'attendre un réseau."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..journal import journal
from ..modules import evenements
from ..schema.modeles import Adresse, Comm, Envoi, EnvoiDestinataire, Evenement, Rattachement
from .messages import boites_du_compte, iso

log = journal("api")

async def liste(s: AsyncSession, compte, limite: int = 100) -> list[dict]:
    """les envois des boîtes du compte, du plus récent au plus ancien"""
    """On part des messages ÉMIS, pas des lignes d'envoi : un message qui n'est jamais parti n'a pas
    encore de ligne d'envoi, et c'est précisément celui qu'il faut voir."""
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    if not boites: return []
    rows = (await s.execute(
        select(Comm).join(Rattachement, Rattachement.comm_id == Comm.comm_id)
        .where(Rattachement.boite_id.in_(boites), Comm.sens == "out")
        .order_by(Comm.date_recue.desc()).limit(limite))).scalars().all()
    out, vus = [], set()
    for c in rows:
        if c.comm_id in vus: continue
        vus.add(c.comm_id)
        e = await s.scalar(select(Envoi).where(Envoi.comm_id == c.comm_id))
        dests = [] if e is None else (await s.execute(
            select(EnvoiDestinataire, Adresse).join(Adresse, Adresse.adresse_id == EnvoiDestinataire.adresse_id)
            .where(EnvoiDestinataire.envoi_id == e.envoi_id))).all()
        ev = await s.scalar(select(Evenement).where(Evenement.type == "message.a_envoyer",
                                                    Evenement.charge["comm_id"].astext == str(c.comm_id))
                            .order_by(Evenement.cree_le.desc()).limit(1))
        if e is None and ev is None: continue          # un brouillon n'est pas un envoi
        out.append(await _serialiser(e, c, dests, ev))
    return out

async def pour_message(s: AsyncSession, compte, comm_id) -> dict | None:
    """le suivi d'UN message — ce que la vue du message affiche sous un message émis"""
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, Rattachement.boite_id.in_(boites)).limit(1))
    if not r: return None
    e = await s.scalar(select(Envoi).where(Envoi.comm_id == comm_id))
    ev = await s.scalar(select(Evenement).where(Evenement.type == "message.a_envoyer",
                                                Evenement.charge["comm_id"].astext == str(comm_id))
                        .order_by(Evenement.cree_le.desc()).limit(1))
    if not e and not ev: return None
    c = await s.get(Comm, comm_id)
    dests = []
    if e:
        dests = (await s.execute(
            select(EnvoiDestinataire, Adresse).join(Adresse, Adresse.adresse_id == EnvoiDestinataire.adresse_id)
            .where(EnvoiDestinataire.envoi_id == e.envoi_id))).all()
    return await _serialiser(e, c, dests, ev)

async def _serialiser(e: Envoi | None, c: Comm, dests, ev: Evenement | None) -> dict:
    """L'état LISIBLE d'un envoi, celui qu'on montre : ce que la file dit prime tant que rien n'est
    remis — « en attente », « en échec, nouvelle tentative à… », « abandonné », puis l'état des
    destinataires (remis, rejeté)."""
    destinataires = [{"adresse": a.adresse_complete, "etat": d.etat, "code": d.code,
                      "mis_a_jour_le": iso(d.mis_a_jour_le)} for d, a in dests]
    etats = {d["etat"] for d in destinataires}
    if e is not None and e.remis_le and etats and etats <= {"remis", "livre", "accepte"}:
        global_, detail = "remis", "remis au relais"
    elif "rejete" in etats:
        global_, detail = "rejete", "rejeté par le serveur distant"
    elif ev is not None and ev.abandonne:
        global_, detail = "abandonne", "abandonné après %d tentatives : %s" % (ev.tentatives, ev.erreur or "")
    elif ev is not None and ev.traite_le is None and ev.tentatives:
        global_, detail = "en_echec", "échec (%d tentative%s), nouvelle tentative à %s : %s" % (
            ev.tentatives, "s" if ev.tentatives > 1 else "", (ev.prochaine_tentative or datetime.now(timezone.utc)).strftime("%H:%M"), ev.erreur or "")
    elif ev is not None and ev.traite_le is None:
        global_, detail = "en_attente", "en attente de remise au relais"
    else:
        global_, detail = ("remis", "remis au relais") if e is not None and e.remis_le else ("en_attente", "en attente")
    return {"comm_id": str(c.comm_id), "sujet": c.sujet, "date": iso(c.date_recue),
            "envoi_id": str(e.envoi_id) if e is not None else None,
            "remis_le": iso(e.remis_le) if e is not None else None,
            "etat": global_, "detail": detail,
            "tentatives": ev.tentatives if ev is not None else 0,
            "erreur": ev.erreur if ev is not None else None,
            "relancable": global_ in ("en_echec", "abandonne", "rejete", "en_attente"),
            "destinataires": destinataires}

async def relancer(s: AsyncSession, compte, comm_id) -> dict | None:
    """Remet l'envoi dans la file : l'événement existant repart à zéro, ou un nouveau est émis si
    l'ancien a été purgé. Idempotent — relancer deux fois ne duplique pas l'envoi (le module
    d'émission réutilise la ligne `envoi` du message)."""
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, Rattachement.boite_id.in_(boites)).limit(1))
    if not r: return None
    c = await s.get(Comm, comm_id)
    if not c or c.sens != "out": return None
    dest = [a for (a,) in (await s.execute(
        select(Adresse.adresse_complete).join(EnvoiDestinataire, EnvoiDestinataire.adresse_id == Adresse.adresse_id)
        .join(Envoi, Envoi.envoi_id == EnvoiDestinataire.envoi_id).where(Envoi.comm_id == comm_id))).all()]
    ev = await s.scalar(select(Evenement).where(Evenement.type == "message.a_envoyer",
                                                Evenement.charge["comm_id"].astext == str(comm_id))
                        .order_by(Evenement.cree_le.desc()).limit(1))
    if ev is not None:
        if not dest: dest = list((ev.charge or {}).get("destinataires") or [])
        ev.traite_le = None; ev.abandonne = None; ev.tentatives = 0; ev.erreur = None
        ev.prochaine_tentative = datetime.now(timezone.utc)
    else:
        evenements.emettre(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(r.boite_id), "destinataires": dest})
    await s.commit()
    log.info("envoi de %s relancé par %s (%d destinataire(s))", comm_id, compte.login, len(dest))
    return {"comm_id": str(comm_id), "destinataires": dest}
