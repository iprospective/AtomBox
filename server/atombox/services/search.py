"""LA RECHERCHE PLEIN TEXTE (F104 — D031, D034) : sur le sujet et l'extrait texte du message, dans la
portée du compte, zone active d'abord (les non sortis). PostgreSQL fait le texte (to_tsvector french) ;
l'index GIN d'expression est posé par la migration 0005."""
from __future__ import annotations
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.models import Adresse, Boite, Comm, Compte, Rattachement
from . import messages as svcm
from ..journal import journal

log = journal("api")

async def search(s: AsyncSession, compte: Compte, q: str, sortis: bool = False, limit: int = 100, wanted: str | None = None) -> list[dict]:
    q = (q or "").strip()
    if len(q) < 2: log.debug("recherche trop courte : %r", q); return []
    boites = svcm.chosen([b.boite_id for b in await svcm.account_mailboxes(s, compte)], wanted)   # D176 § 3
    if not boites: return []
    ds = await svcm._folders_by_id(s, boites)
    texte = func.to_tsvector("french", func.coalesce(Comm.sujet, "") + " " + func.coalesce(Comm.corps_texte, ""))
    requete = func.plainto_tsquery("french", q)
    stmt = (select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id)
            .where(Rattachement.boite_id.in_(boites), or_(texte.op("@@")(requete), Comm.from_adresse.ilike("%" + q + "%"), Comm.from_nom.ilike("%" + q + "%")))
            .order_by(func.ts_rank(texte, requete).desc(), Comm.date_recue.desc()).limit(limit))
    if not sortis: stmt = stmt.where(Rattachement.exit_reason.is_(None))
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    lines = (await s.execute(stmt)).all()
    from . import personal_state as personal
    etats = await personal.states_of(s, compte.compte_id, [c.comm_id for _, c in lines])
    seen, out = set(), []
    for r, c in lines:
        if c.comm_id in seen: continue
        seen.add(c.comm_id)
        out.append(svcm.serialize(r, c, ds, adresses.get(r.boite_id), etat=etats.get((r.comm_id, r.boite_id))))
    return out
