"""LA RECHERCHE PLEIN TEXTE (F104 — D031, D034) : sur le sujet et l'extrait texte du message, dans la
portée du compte, zone active d'abord (les non sortis). PostgreSQL fait le texte (to_tsvector french) ;
l'index GIN d'expression est posé par la migration 0005."""
from __future__ import annotations
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.modeles import Adresse, Boite, Comm, Compte, Rattachement
from . import messages as svcm
from ..journal import journal

log = journal("api")

async def rechercher(s: AsyncSession, compte: Compte, q: str, sortis: bool = False, limite: int = 100) -> list[dict]:
    q = (q or "").strip()
    if len(q) < 2: log.debug("recherche trop courte : %r", q); return []
    boites = [b.boite_id for b in await svcm.boites_du_compte(s, compte)]
    if not boites: return []
    ds = await svcm._dossiers_par_id(s, boites)
    texte = func.to_tsvector("french", func.coalesce(Comm.sujet, "") + " " + func.coalesce(Comm.corps_texte, ""))
    requete = func.plainto_tsquery("french", q)
    stmt = (select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id)
            .where(Rattachement.boite_id.in_(boites), or_(texte.op("@@")(requete), Comm.from_adresse.ilike("%" + q + "%"), Comm.from_nom.ilike("%" + q + "%")))
            .order_by(func.ts_rank(texte, requete).desc(), Comm.date_recue.desc()).limit(limite))
    if not sortis: stmt = stmt.where(Rattachement.motif_sortie.is_(None))
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    vus, out = set(), []
    for r, c in (await s.execute(stmt)).all():
        if c.comm_id in vus: continue
        vus.add(c.comm_id); out.append(svcm.serialiser(r, c, ds, adresses.get(r.boite_id)))
    return out
