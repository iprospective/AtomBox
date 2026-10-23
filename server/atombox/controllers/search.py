"""GET /recherche?q= — plein texte, portée du jeton, zone active par défaut (D034)."""
from __future__ import annotations
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_reader
from ..journal import journal
from ..schema.models import Compte
from ..services import search as svc

log = journal("api")

class SearchController(Controller):
    @action("GET", "/recherche")
    async def search(self, q: str = Query(""), sortis: int = 0, boites: str | None = None, compte: Compte = Depends(current_reader), s: AsyncSession = Depends(async_session)):
        l = await svc.search(s, compte, q, sortis=bool(sortis), wanted=boites)
        log.debug("recherche %r par %s : %d", q, compte.login, len(l))
        return {"messages": l, "total": len(l), "q": q}
