"""/messages — la liste d'un dossier, un message, son fil, son rattachement (D036), sa création.
Hors portée = 404, jamais 403 (D108)."""
from __future__ import annotations
import os, uuid
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..magasin import Magasin
from ..schema.modeles import Compte
from ..services import messages as svc
from ..journal import journal

log = journal("api")

def magasin() -> Magasin: return Magasin(os.environ.get("ATOMBOX_MAGASIN", "./magasin"))

def _uuid(id_: str):
    try: return uuid.UUID(id_)
    except ValueError: raise HTTPException(404, "message inconnu")

class MessagesControleur(Controleur):
    prefixe = "/messages"

    @action("GET", "")
    async def liste(self, dossier: str = Query("inbox"), kind: str | None = None, axe: str | None = None, filtre: str | None = "file",
                    tri: str | None = "date_desc", sens: str | None = None, statut: str | None = None, tout: int = 0,
                    compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        l = await svc.liste(s, compte, dossier, kind, filtre, tri, sens, statut, tout=bool(tout))
        log.debug("liste %s/%s pour %s : %d", dossier, filtre, compte.login, len(l))
        return {"messages": l, "total": len(l)}

    @action("GET", "/{id}")
    async def detail(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        m = await svc.detail(s, compte, _uuid(id), magasin())
        if not m: raise HTTPException(404, "message inconnu")
        return m

    @action("GET", "/{id}/fil")
    async def fil(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        return {"messages": await svc.fil(s, compte, _uuid(id))}

    @action("PATCH", "/{id}/rattachement")
    async def rattachement(self, id: str, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        corps = await request.json()
        r = await svc.patcher(s, compte, _uuid(id), corps or {})
        if r is None: raise HTTPException(404, "message inconnu")
        return {"ok": True, **r}

    @action("DELETE", "/{id}/rattachement")
    async def detacher(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        if not await svc.detacher(s, compte, _uuid(id)): raise HTTPException(404, "message inconnu")
        return {"ok": True, "modifies": 1, "detache": True}

    @action("PUT", "/{id}")
    async def reenregistrer(self, id: str, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        m = await svc.remplacer_brouillon(s, compte, _uuid(id), await request.json() or {}, magasin())
        if m is None: raise HTTPException(404, "aucun brouillon à ce nom")
        return {"ok": True, "modifies": 1, "message": m}

    @action("POST", "")
    async def creer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        corps = await request.json()
        m = await svc.creer(s, compte, corps or {}, magasin(), ip_client=(request.client.host if request.client else None))
        if m is None: raise HTTPException(400, "aucune boîte pour ce compte")
        log.info("message %s créé par %s (%s)", m["id"], compte.login, "brouillon" if (corps or {}).get("composition") else "à envoyer")
        return {"ok": True, "crees": 1, "message": m}
