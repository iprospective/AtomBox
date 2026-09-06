"""POST /session, DELETE /session — l'écran de connexion du webmail (F124, D157) ; V0 : identifiant
et mot de passe d'un compte, un jeton en retour. Le SSO et les passkeys sont V2 (D150)."""
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant, ouvrir_session, verifier_mot_de_passe
from ..schema.modeles import Compte
from ..journal import journal

log = journal("auth")

class Identifiants(BaseModel):
    utilisateur: str
    mot_de_passe: str

class SessionOuverte(BaseModel):
    jeton: str
    compte: dict

class SessionControleur(Controleur):
    @action("POST", "/session", response_model=SessionOuverte, status_code=200)
    async def ouvrir(self, corps: Identifiants, request: Request, s: AsyncSession = Depends(session_async)):
        compte = await s.scalar(select(Compte).where(Compte.login == corps.utilisateur.strip().lower()))
        if not compte or not compte.actif or not verifier_mot_de_passe(corps.mot_de_passe, compte.mot_de_passe_empreinte):
            log.warning("connexion refusée pour %r depuis %s", corps.utilisateur, request.client.host if request.client else "?")
            raise HTTPException(401, "identifiants refusés")
        jeton = await ouvrir_session(s, compte, request.headers.get("user-agent"))
        return SessionOuverte(jeton=jeton, compte={"id": str(compte.compte_id), "login": compte.login, "nom": compte.nom})

    @action("DELETE", "/session")
    async def fermer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        ses = request.state.session
        ses.revoque_le = datetime.now(timezone.utc)
        await s.commit()
        log.info("session fermée pour %s", compte.login)
        return {"ok": True, "fermee": True}
