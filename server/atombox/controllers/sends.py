"""GET /envois, GET /envois/{comm_id}, POST /envois/{comm_id}/relancer — le suivi de l'émission (D099).
Le message est la clé : c'est lui que l'utilisateur voit, pas l'identifiant d'envoi."""
from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_account
from ..journal import journal
from ..schema.models import Compte
from ..services import sends as svc

log = journal("api")

def _uuid(v: str):
    try: return uuid.UUID(v)
    except ValueError: raise HTTPException(404, "envoi inconnu")

class SendsController(Controller):
    prefix = "/envois"

    @action("GET", "")
    async def listing(self, limit: int = Query(100, ge=1, le=500),
                    compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        l = await svc.listing(s, compte, limit)
        return {"envois": l, "total": len(l)}

    @action("GET", "/{comm_id}")
    async def one(self, comm_id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        e = await svc.for_message(s, compte, _uuid(comm_id))
        if e is None: raise HTTPException(404, "aucun envoi pour ce message")
        return e

    @action("POST", "/{comm_id}/relancer")
    async def follow_up(self, comm_id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        r = await svc.follow_up(s, compte, _uuid(comm_id))
        if r is None: raise HTTPException(404, "aucun message émis à relancer")
        return {"ok": True, "relance": 1, **r}
