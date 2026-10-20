"""POST /session, DELETE /session — l'écran de connexion du webmail (F124, D157) ; V0 : identifiant
et mot de passe d'un compte, un jeton en retour. Le SSO et les passkeys sont V2 (D150)."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_account, open_session, verify_password
from ..api import rate_limit
from ..schema.models import Compte
from ..journal import journal
from ..modules.hooks import hooks
from .. import settings

log = journal("auth")

class Credentials(BaseModel):
    utilisateur: str
    mot_de_passe: str

class SessionOpened(BaseModel):
    jeton: str
    compte: dict

class ResetRequest(BaseModel):
    utilisateur: str

class ResetApply(BaseModel):
    jeton: str
    mot_de_passe: str

class Constant(BaseModel):
    ok: bool
    message: str

class SessionController(Controller):
    @action("POST", "/session", response_model=SessionOpened, status_code=200)
    async def login(self, corps: Credentials, request: Request, s: AsyncSession = Depends(async_session)):
        ip = request.client.host if request.client else None
        wait_s = rate_limit.check("session", corps.utilisateur, ip)
        if wait_s:
            raise HTTPException(429, "trop d'essais — réessayez dans %d minute(s)" % max(1, wait_s // 60),
                                headers={"Retry-After": str(wait_s)})
        compte = await s.scalar(select(Compte).where(Compte.login == corps.utilisateur.strip().lower()))
        if not compte or not compte.actif or not verify_password(corps.mot_de_passe, compte.mot_de_passe_empreinte):
            rate_limit.count("session", corps.utilisateur, ip)
            log.warning("connexion refusée pour %r depuis %s", corps.utilisateur, ip or "?")
            raise HTTPException(401, "identifiants refusés")
        rate_limit.forget("session", corps.utilisateur, ip)
        jeton = await open_session(s, compte, request.headers.get("user-agent"))
        return SessionOpened(jeton=jeton, compte={"id": str(compte.compte_id), "login": compte.login, "nom": compte.nom})

    @action("POST", "/session/reinitialisation", response_model=Constant, status_code=200)
    async def request_reset(self, corps: ResetRequest, request: Request,
                                        s: AsyncSession = Depends(async_session)):
        """D164 — la réponse est CONSTANTE : compte inconnu, sans adresse de secours, inactif ou
        servi ici, c'est la même phrase. Sinon ce formulaire devient un annuaire des comptes."""
        from ..services import password_reset as reinit
        ip_dem = request.client.host if request.client else None
        wait_s = rate_limit.check("reinitialisation", corps.utilisateur, ip_dem)
        if wait_s:
            # un 429 ne dit rien du compte : la réponse reste constante dans sa FORME
            raise HTTPException(429, "trop de demandes — réessayez dans %d minute(s)" % max(1, wait_s // 60),
                                headers={"Retry-After": str(wait_s)})
        rate_limit.count("reinitialisation", corps.utilisateur, ip_dem)
        # Derrière un proxy, `request.base_url` dit 127.0.0.1:8010 : le lien serait inutilisable.
        # On reconstruit depuis ce qu'Apache transmet, et ATOMBOX_PUBLIC_URL tranche s'il existe.
        hote = request.headers.get("x-forwarded-host") or request.headers.get("host")
        schema = request.headers.get("x-forwarded-proto") or request.url.scheme
        base = settings.read("ATOMBOX_PUBLIC_URL") or (
            "%s://%s" % (schema, hote) if hote else str(request.base_url).rstrip("/"))
        await reinit.request(s, corps.utilisateur, base, ip=ip_dem)
        return Constant(ok=True, message="Si un compte correspond et qu'une adresse de secours y est "
                                          "enregistrée, un lien vient d'y être envoyé.")

    @action("PUT", "/session/reinitialisation", response_model=Constant, status_code=200)
    async def apply_reset(self, corps: ResetApply, s: AsyncSession = Depends(async_session)):
        from ..services import password_reset as reinit
        ok, motif = await reinit.apply(s, corps.jeton, corps.mot_de_passe)
        if not ok:
            raise HTTPException(400, motif)
        return Constant(ok=True, message=motif)

    @action("DELETE", "/session")
    async def close(self, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        ses = request.state.session
        ses.revoque_le = datetime.now(timezone.utc)
        await s.commit()
        log.info("session fermée pour %s", compte.login)
        await hooks.emit_async("session.fermee", compte=compte)
        return {"ok": True, "fermee": True}
