"""LA SÉCURITÉ de l'API (D063, D157, D150) : un jeton opaque au porteur, haché en base ; un mot
de passe haché par scrypt (bibliothèque standard) — les passkeys et le SSO viennent en V2."""
from __future__ import annotations
import hashlib, hmac, os, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.modeles import Compte, Session as SessionModele
from ..uuid7 import uuid7
from .dependances import session_async
from ..journal import journal
from ..modules.accroches import accroches

log = journal("auth")

DUREE = timedelta(days=30)

def hacher_mot_de_passe(mdp: str, sel: bytes | None = None) -> str:
    sel = sel or os.urandom(16)
    h = hashlib.scrypt(mdp.encode(), salt=sel, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$%s$%s" % (sel.hex(), h.hex())

def verifier_mot_de_passe(mdp: str, stocke: str | None) -> bool:
    if not stocke or not stocke.startswith("scrypt$"): return False
    _, sel, h = stocke.split("$")
    return hmac.compare_digest(hacher_mot_de_passe(mdp, bytes.fromhex(sel)).split("$")[2], h)

def empreinte_jeton(jeton: str) -> str: return hashlib.sha256(jeton.encode()).hexdigest()

def nouveau_jeton() -> str: return secrets.token_urlsafe(32)

async def compte_courant(request: Request, s: AsyncSession = Depends(session_async)) -> Compte:
    """le compte du jeton porteur — 401 sinon (jamais 403 : hors portée = inexistant, D108)"""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        log.debug("%s %s sans jeton", request.method, request.url.path); raise HTTPException(401, "jeton absent")
    jeton = auth[7:].strip()
    ses = await s.scalar(select(SessionModele).where(SessionModele.jeton_empreinte == empreinte_jeton(jeton)))
    if not ses or ses.revoque_le or ses.expire_le < datetime.now(timezone.utc):
        log.warning("jeton %s : %s (%s)", "inconnu" if not ses else ("révoqué" if ses.revoque_le else "expiré"), request.url.path, request.client.host if request.client else "?")
        raise HTTPException(401, "session invalide")
    compte = await s.get(Compte, ses.compte_id)
    if not compte or not compte.actif:
        log.warning("session %s : compte inactif", ses.session_id); raise HTTPException(401, "compte inactif")
    request.state.session = ses
    return compte

async def ouvrir_session(s: AsyncSession, compte: Compte, agent: str | None) -> str:
    jeton = nouveau_jeton()
    s.add(SessionModele(session_id=uuid7(), compte_id=compte.compte_id, jeton_empreinte=empreinte_jeton(jeton),
                        cree_le=datetime.now(timezone.utc), expire_le=datetime.now(timezone.utc) + DUREE, agent=agent))
    await s.commit()
    log.info("session ouverte pour %s (%s)", compte.login, agent or "agent inconnu")
    await accroches.emettre_async("session.ouverte", compte=compte, agent=agent)
    return jeton
