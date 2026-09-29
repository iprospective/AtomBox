"""POST /session, DELETE /session — l'écran de connexion du webmail (F124, D157) ; V0 : identifiant
et mot de passe d'un compte, un jeton en retour. Le SSO et les passkeys sont V2 (D150)."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant, ouvrir_session, verifier_mot_de_passe
from ..api import limitation
from ..schema.modeles import Compte
from ..journal import journal
from ..modules.accroches import accroches
from .. import settings

log = journal("auth")

class Identifiants(BaseModel):
    utilisateur: str
    mot_de_passe: str

class SessionOuverte(BaseModel):
    jeton: str
    compte: dict

class DemandeReinit(BaseModel):
    utilisateur: str

class AppliqueReinit(BaseModel):
    jeton: str
    mot_de_passe: str

class Constante(BaseModel):
    ok: bool
    message: str

class SessionControleur(Controleur):
    @action("POST", "/session", response_model=SessionOuverte, status_code=200)
    async def ouvrir(self, corps: Identifiants, request: Request, s: AsyncSession = Depends(session_async)):
        ip = request.client.host if request.client else None
        attente = limitation.verifier("session", corps.utilisateur, ip)
        if attente:
            raise HTTPException(429, "trop d'essais — réessayez dans %d minute(s)" % max(1, attente // 60),
                                headers={"Retry-After": str(attente)})
        compte = await s.scalar(select(Compte).where(Compte.login == corps.utilisateur.strip().lower()))
        if not compte or not compte.actif or not verifier_mot_de_passe(corps.mot_de_passe, compte.mot_de_passe_empreinte):
            limitation.compter("session", corps.utilisateur, ip)
            log.warning("connexion refusée pour %r depuis %s", corps.utilisateur, ip or "?")
            raise HTTPException(401, "identifiants refusés")
        limitation.oublier("session", corps.utilisateur, ip)
        jeton = await ouvrir_session(s, compte, request.headers.get("user-agent"))
        return SessionOuverte(jeton=jeton, compte={"id": str(compte.compte_id), "login": compte.login, "nom": compte.nom})

    @action("POST", "/session/reinitialisation", response_model=Constante, status_code=200)
    async def demander_reinitialisation(self, corps: DemandeReinit, request: Request,
                                        s: AsyncSession = Depends(session_async)):
        """D164 — la réponse est CONSTANTE : compte inconnu, sans adresse de secours, inactif ou
        servi ici, c'est la même phrase. Sinon ce formulaire devient un annuaire des comptes."""
        from ..services import reinitialisation as reinit
        ip_dem = request.client.host if request.client else None
        attente = limitation.verifier("reinitialisation", corps.utilisateur, ip_dem)
        if attente:
            # un 429 ne dit rien du compte : la réponse reste constante dans sa FORME
            raise HTTPException(429, "trop de demandes — réessayez dans %d minute(s)" % max(1, attente // 60),
                                headers={"Retry-After": str(attente)})
        limitation.compter("reinitialisation", corps.utilisateur, ip_dem)
        # Derrière un proxy, `request.base_url` dit 127.0.0.1:8010 : le lien serait inutilisable.
        # On reconstruit depuis ce qu'Apache transmet, et ATOMBOX_PUBLIC_URL tranche s'il existe.
        hote = request.headers.get("x-forwarded-host") or request.headers.get("host")
        schema = request.headers.get("x-forwarded-proto") or request.url.scheme
        base = settings.read("ATOMBOX_PUBLIC_URL") or (
            "%s://%s" % (schema, hote) if hote else str(request.base_url).rstrip("/"))
        await reinit.demander(s, corps.utilisateur, base, ip=ip_dem)
        return Constante(ok=True, message="Si un compte correspond et qu'une adresse de secours y est "
                                          "enregistrée, un lien vient d'y être envoyé.")

    @action("PUT", "/session/reinitialisation", response_model=Constante, status_code=200)
    async def appliquer_reinitialisation(self, corps: AppliqueReinit, s: AsyncSession = Depends(session_async)):
        from ..services import reinitialisation as reinit
        ok, motif = await reinit.appliquer(s, corps.jeton, corps.mot_de_passe)
        if not ok:
            raise HTTPException(400, motif)
        return Constante(ok=True, message=motif)

    @action("DELETE", "/session")
    async def fermer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        ses = request.state.session
        ses.revoque_le = datetime.now(timezone.utc)
        await s.commit()
        log.info("session fermée pour %s", compte.login)
        await accroches.emettre_async("session.fermee", compte=compte)
        return {"ok": True, "fermee": True}
