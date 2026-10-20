"""LES DOSSIERS UTILISATEUR (F013 — D051, D047) et LES IDENTITÉS (F032 — D102, D116).

Un dossier utilisateur est une vraie entité (D051), et tant qu'IMAP est la vérité (D140b) il doit
exister des deux côtés : le créer ici et pas là-bas ferait disparaître les messages qu'on y range
au prochain passage du démon. Les dossiers protégés (INBOX, Sent…) ne se renomment ni ne se
suppriment (D047)."""
from __future__ import annotations
import os
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..journal import journal
from ..schema.models import Adresse, Boite, Dossier, Identite, Rattachement
from ..uuid7 import uuid7
from .. import settings

log = journal("api")

def _imap_available() -> bool: return bool(settings.read("ATOMBOX_IMAP_HOST"))

async def _imap(s: AsyncSession, boite: Boite):
    """une relève ouverte sur la boîte, ou None si l'IMAP n'est pas configuré"""
    from ..ingestion.imap import Poller, tls_imap
    from ..sync.module import config_imap, login_of
    if not _imap_available(): return None
    cfg = config_imap(); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    return Poller(cfg["hote"], cfg["port"], tls=tls_imap()).connect(login_of(adresse, cfg["master"]), cfg["mot_de_passe"])

def serialize_folder(d: Dossier) -> dict:
    return {"id": str(d.dossier_id), "nom": d.nom, "alias_imap": d.alias_imap,
            "protege": bool(d.protege), "ordre": d.ordre}

async def create_folder(s: AsyncSession, boite: Boite, nom: str, parent: Dossier | None = None) -> dict:
    nom = (nom or "").strip().strip("/")
    if not nom: raise ValueError("un nom")
    alias = ((parent.alias_imap + "/") if parent and parent.alias_imap else "") + nom
    if await s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id, Dossier.alias_imap == alias)):
        raise ValueError("ce dossier existe déjà")
    rel = await _imap(s, boite)
    if rel is not None:
        try: rel.create_folder(alias)
        finally: rel.close()
    d = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=nom, alias_imap=alias,
                parent_id=parent.dossier_id if parent else None, protege=False)
    s.add(d); await s.commit()
    log.info("dossier « %s » créé dans %s", alias, boite.boite_id)
    return serialize_folder(d)

async def rename_folder(s: AsyncSession, boite: Boite, d: Dossier, nom: str) -> dict:
    if d.protege: raise PermissionError("un dossier protégé ne se renomme pas (D047)")
    nom = (nom or "").strip().strip("/")
    if not nom: raise ValueError("un nom")
    parent = (d.alias_imap or "").rsplit("/", 1)[0] if "/" in (d.alias_imap or "") else ""
    alias = (parent + "/" if parent else "") + nom
    rel = await _imap(s, boite)
    if rel is not None:
        try: rel.rename_folder(d.alias_imap, alias)
        finally: rel.close()
    d.nom, d.alias_imap = nom, alias
    await s.commit()
    return serialize_folder(d)

async def delete_folder(s: AsyncSession, boite: Boite, d: Dossier) -> None:
    if d.protege: raise PermissionError("un dossier protégé ne se supprime pas (D047)")
    n = await s.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.dossier_id == d.dossier_id))
    if n: raise ValueError("le dossier contient %d message(s) — le vider d'abord" % n)
    rel = await _imap(s, boite)
    if rel is not None:
        try: rel.delete_folder(d.alias_imap)
        finally: rel.close()
    await s.delete(d); await s.commit()
    log.info("dossier « %s » supprimé", d.alias_imap)

# ---- identités (F032) ------------------------------------------------------------------------
def serialize_identity(i: Identite, adresse: str) -> dict:
    return {"id": str(i.identite_id), "boite_id": str(i.boite_id), "nom_affiche": i.nom_affiche,
            "adresse": adresse, "reply_to": i.reply_to, "signature": i.signature,
            "au_nom_de": bool(i.au_nom_de), "par_defaut": bool(i.par_defaut)}

async def identities(s: AsyncSession, boites: list[Boite]) -> list[dict]:
    out = []
    for b in boites:
        adresse = (await s.get(Adresse, b.adresse_id)).adresse_complete
        for i in await s.scalars(select(Identite).where(Identite.boite_id == b.boite_id).order_by(Identite.par_defaut.desc())):
            out.append(serialize_identity(i, adresse))
    return out

async def create_identity(s: AsyncSession, boite: Boite, c: dict) -> dict:
    i = Identite(identite_id=uuid7(), boite_id=boite.boite_id, adresse_id=boite.adresse_id,
                 nom_affiche=(c.get("nom_affiche") or "").strip() or "(sans nom)",
                 reply_to=c.get("reply_to") or None, signature=c.get("signature") or None,
                 au_nom_de=bool(c.get("au_nom_de")), par_defaut=bool(c.get("par_defaut")))
    if i.par_defaut:
        for autre in await s.scalars(select(Identite).where(Identite.boite_id == boite.boite_id)): autre.par_defaut = False
    s.add(i); await s.commit()
    return serialize_identity(i, (await s.get(Adresse, boite.adresse_id)).adresse_complete)

async def update_identity(s: AsyncSession, i: Identite, c: dict) -> dict:
    for champ in ("nom_affiche", "reply_to", "signature"):
        if champ in c: setattr(i, champ, c[champ] or None)
    if "au_nom_de" in c: i.au_nom_de = bool(c["au_nom_de"])
    if c.get("par_defaut"):
        for autre in await s.scalars(select(Identite).where(Identite.boite_id == i.boite_id)): autre.par_defaut = False
        i.par_defaut = True
    await s.commit()
    b = await s.get(Boite, i.boite_id)
    return serialize_identity(i, (await s.get(Adresse, b.adresse_id)).adresse_complete)

async def delete_identity(s: AsyncSession, i: Identite) -> None:
    n = await s.scalar(select(func.count()).select_from(Identite).where(Identite.boite_id == i.boite_id))
    if n <= 1: raise ValueError("c'est la dernière identité de cette boîte")
    await s.delete(i); await s.commit()

# ---- carnet auto-collecté (F108, D109) --------------------------------------------------------
async def address_book(s: AsyncSession, boites: list[Boite], q: str = "", limit: int = 50) -> list[dict]:
    """Les adresses à qui ce compte a ÉCRIT, par fréquence puis récence. Le carnet gratuit de la
    V0 (D109) : personne ne le saisit, il se déduit des envois."""
    from ..schema.models import Comm, Participant
    ids = [b.boite_id for b in boites]
    if not ids: return []
    st = (select(Adresse.adresse_complete, func.max(Participant.nom_affiche).label("nom"),
                 func.count().label("n"), func.max(Comm.date_recue).label("dernier"))
          .join(Participant, Participant.adresse_id == Adresse.adresse_id)
          .join(Comm, Comm.comm_id == Participant.comm_id)
          .join(Rattachement, Rattachement.comm_id == Comm.comm_id)
          .where(Rattachement.boite_id.in_(ids), Comm.sens == "out", Participant.role.in_(("to", "cc")))
          .group_by(Adresse.adresse_complete).order_by(func.count().desc(), func.max(Comm.date_recue).desc()).limit(limit))
    if q: st = st.where(func.lower(Adresse.adresse_complete).contains(q.lower()))
    return [{"adresse": a, "nom": nom, "echanges": n, "dernier": d.isoformat() if d else None}
            for a, nom, n, d in (await s.execute(st)).all()]
