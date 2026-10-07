"""GET /referentiels — ce que le webmail charge à l'amorçage (D141) : moi, mes boîtes, les dossiers, les statuts, les vues."""
from __future__ import annotations
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_account
from ..schema.models import Compte
from ..services import messages as svc
from ..journal import journal

log = journal("api")

class ReferencesController(Controller):
    @action("GET", "/referentiels")
    async def read(self, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        ref = await svc.references(s, compte)
        log.debug("référentiels de %s : %d boîte(s), %d dossier(s)", compte.login, len(ref["moi"]["boites"]), len(ref["util"]))
        return ref
