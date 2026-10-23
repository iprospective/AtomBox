"""LA SÉCURITÉ de l'API (D063, D157, D150) : un jeton opaque au porteur, haché en base ; un mot
de passe haché par scrypt (bibliothèque standard) — les passkeys et le SSO viennent en V2."""
from __future__ import annotations
import hashlib, hmac, os, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.models import Compte, Session as SessionModele
from ..uuid7 import uuid7
from .dependencies import async_session
from ..journal import journal
from ..modules.hooks import hooks

log = journal("auth")

LIFETIME = timedelta(days=30)

def hash_password(mdp: str, sel: bytes | None = None) -> str:
    sel = sel or os.urandom(16)
    h = hashlib.scrypt(mdp.encode(), salt=sel, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$%s$%s" % (sel.hex(), h.hex())

def verify_password(mdp: str, stocke: str | None) -> bool:
    if not stocke or not stocke.startswith("scrypt$"): return False
    _, sel, h = stocke.split("$")
    return hmac.compare_digest(hash_password(mdp, bytes.fromhex(sel)).split("$")[2], h)

def token_fingerprint(jeton: str) -> str: return hashlib.sha256(jeton.encode()).hexdigest()

def new_token() -> str: return secrets.token_urlsafe(32)

async def current_account(request: Request, s: AsyncSession = Depends(async_session)) -> Compte:
    """le compte du jeton porteur — 401 sinon (jamais 403 : hors portée = inexistant, D108)"""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        log.debug("%s %s sans jeton", request.method, request.url.path); raise HTTPException(401, "jeton absent")
    jeton = auth[7:].strip()
    ses = await s.scalar(select(SessionModele).where(SessionModele.jeton_empreinte == token_fingerprint(jeton)))
    if not ses or ses.revoque_le or ses.expire_le < datetime.now(timezone.utc):
        log.warning("jeton %s : %s (%s)", "inconnu" if not ses else ("révoqué" if ses.revoque_le else "expiré"), request.url.path, request.client.host if request.client else "?")
        raise HTTPException(401, "session invalide")
    compte = await s.get(Compte, ses.compte_id)
    if not compte or not compte.actif:
        log.warning("session %s : compte inactif", ses.session_id); raise HTTPException(401, "compte inactif")
    request.state.session = ses
    return compte

async def current_reader(request: Request, s: AsyncSession = Depends(async_session)):
    """CELUI QUI LIT : une personne (session), ou une APPLICATION connectée (F048, RM3517).

    Seules les routes de lecture et d'étiquetage acceptent ce dépendant ; tout ce qui classe,
    supprime ou envoie reste à `current_account` — une application qui présente son jeton à ces
    routes-là reçoit 401, comme un jeton inconnu. Le jeton d'application se reconnaît à son
    préfixe : il n'est cherché que dans sa table."""
    from ..applications import PREFIX, AppPrincipal
    from ..schema.models import Application
    auth = request.headers.get("authorization", "")
    jeton = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not jeton.startswith(PREFIX):
        return await current_account(request, s)
    app = await s.scalar(select(Application).where(Application.jeton_empreinte == token_fingerprint(jeton)))
    if not app or not app.actif:
        log.warning("jeton d'application %s : %s (%s)", "inconnu" if not app else "révoqué", request.url.path,
                    request.client.host if request.client else "?")
        raise HTTPException(401, "jeton d'application invalide")
    # le dernier appel se VOIT (la liste des applications le montre) : une route de lecture ne
    # valide rien, donc on valide ici — expire_on_commit est faux, l'objet reste lisible
    app.dernier_appel = datetime.now(timezone.utc)
    await s.commit()
    request.state.application = app
    return AppPrincipal(app)

async def open_session(s: AsyncSession, compte: Compte, agent: str | None) -> str:
    jeton = new_token()
    s.add(SessionModele(session_id=uuid7(), compte_id=compte.compte_id, jeton_empreinte=token_fingerprint(jeton),
                        cree_le=datetime.now(timezone.utc), expire_le=datetime.now(timezone.utc) + LIFETIME, agent=agent))
    await s.commit()
    log.info("session ouverte pour %s (%s)", compte.login, agent or "agent inconnu")
    await hooks.emit_async("session.ouverte", compte=compte, agent=agent)
    return jeton
