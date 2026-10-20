"""GET /arborescence — les compteurs de TOUTE l'arborescence en une passe (D078), les dossiers virtuels personnels (D143), les épingles (D144)."""
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

class TreeController(Controller):
    @action("GET", "/arborescence")
    async def read(self, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        arbo = await svc.counters(s, compte)
        log.debug("arborescence de %s : %d dossier(s) comptés", compte.login, len(arbo["compteurs"]))
        return arbo
