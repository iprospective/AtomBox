"""GET /envois, GET /envois/{comm_id}, POST /envois/{comm_id}/relancer — le suivi de l'émission (D099).
Le message est la clé : c'est lui que l'utilisateur voit, pas l'identifiant d'envoi."""
from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..journal import journal
from ..schema.modeles import Compte
from ..services import envois as svc

log = journal("api")

def _uuid(v: str):
    try: return uuid.UUID(v)
    except ValueError: raise HTTPException(404, "envoi inconnu")

class EnvoisControleur(Controleur):
    prefixe = "/envois"

    @action("GET", "")
    async def liste(self, limite: int = Query(100, ge=1, le=500),
                    compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        l = await svc.liste(s, compte, limite)
        return {"envois": l, "total": len(l)}

    @action("GET", "/{comm_id}")
    async def un(self, comm_id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        e = await svc.pour_message(s, compte, _uuid(comm_id))
        if e is None: raise HTTPException(404, "aucun envoi pour ce message")
        return e

    @action("POST", "/{comm_id}/relancer")
    async def relancer(self, comm_id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        r = await svc.relancer(s, compte, _uuid(comm_id))
        if r is None: raise HTTPException(404, "aucun message émis à relancer")
        return {"ok": True, "relance": 1, **r}
