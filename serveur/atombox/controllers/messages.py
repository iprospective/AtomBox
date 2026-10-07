"""/messages — la liste d'un dossier, un message, son fil, son rattachement (D036), sa création.
Hors portée = 404, jamais 403 (D108)."""
from __future__ import annotations
import os, uuid
from fastapi import Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_account
from ..store import Store
from ..schema.models import Compte
from ..services import messages as svc
from ..journal import journal
from .. import settings

log = journal("api")

def store() -> Store: return Store(settings.read("ATOMBOX_STORE", "./magasin"))

def _uuid(id_: str):
    try: return uuid.UUID(id_)
    except ValueError: raise HTTPException(404, "message inconnu")

class MessagesController(Controller):
    prefix = "/messages"

    @action("GET", "")
    async def listing(self, dossier: str = Query("inbox"), kind: str | None = None, axe: str | None = None, filtre: str | None = "file",
                    tri: str | None = "date_desc", sens: str | None = None, statut: str | None = None, tout: int = 0,
                    compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        l = await svc.listing(s, compte, dossier, kind, filtre, tri, sens, statut, tout=bool(tout))
        log.debug("liste %s/%s pour %s : %d", dossier, filtre, compte.login, len(l))
        return {"messages": l, "total": len(l)}

    @action("GET", "/{id}")
    async def detail(self, id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        m = await svc.detail(s, compte, _uuid(id), store())
        if not m: raise HTTPException(404, "message inconnu")
        return m

    @action("GET", "/{id}/pieces-jointes/{pj}")
    async def attachment(self, id: str, pj: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        """Les octets d'une pièce (F136). `inline` pour ce qu'un navigateur sait afficher sans danger,
        `attachment` pour tout le reste — et jamais le type déclaré par le message (D032)."""
        p = await svc.attachment(s, compte, _uuid(id), _uuid(pj), store())
        if not p: raise HTTPException(404, "pièce jointe inconnue")
        entetes = {"Content-Disposition": '%s; filename="%s"' % (p["disposition"], p["nom"]),
                   "X-Content-Type-Options": "nosniff"}       # le navigateur ne redevine pas le type
        return Response(content=p["octets"], media_type=p["type"], headers=entetes)

    @action("GET", "/{id}/fil")
    async def thread(self, id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        return {"messages": await svc.thread(s, compte, _uuid(id))}

    @action("PATCH", "/{id}/rattachement")
    async def filing(self, id: str, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        corps = await request.json()
        r = await svc.patch(s, compte, _uuid(id), corps or {})
        if r is None: raise HTTPException(404, "message inconnu")
        return {"ok": True, **r}

    @action("POST", "/{id}/envoyer")
    async def send(self, id: str, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        """Envoyer un BROUILLON : c'est le même message qui part (D089, RM3246)."""
        m = await svc.replace_draft(s, compte, _uuid(id), await request.json() or {}, store(), envoi=True)
        if m is None: raise HTTPException(404, "aucun brouillon à ce nom")
        return {"ok": True, "message": m}

    @action("DELETE", "/{id}/rattachement")
    async def detach(self, id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        if not await svc.detach(s, compte, _uuid(id)): raise HTTPException(404, "message inconnu")
        return {"ok": True, "modifies": 1, "detache": True}

    @action("POST", "/{id}/tags")
    async def add_tag(self, id: str, request: Request, compte: Compte = Depends(current_account),
                        s: AsyncSession = Depends(async_session)):
        """D002/D017 — le tag est posé sur le MESSAGE : deux personnes d'une boîte partagée voient
        les mêmes. La source distingue ce qu'un humain a posé de ce qu'un connecteur a déduit."""
        from ..services import tags as svct
        corps = await request.json() or {}
        tags = await svct.add(s, compte, _uuid(id), corps.get("axe"), corps.get("val") or corps.get("valeur"))
        if tags is None: raise HTTPException(404, "message inconnu ou axe et valeur manquants")
        return {"ok": True, "tags": tags}

    @action("DELETE", "/{id}/tags/{tag}")
    async def remove_tag(self, id: str, tag: str, compte: Compte = Depends(current_account),
                          s: AsyncSession = Depends(async_session)):
        """`tag` est « axe=valeur » — un tag n'a pas d'identité propre du point de vue de l'API :
        il EST la paire, et c'est ce qui rend l'appel idempotent."""
        from ..services import tags as svct
        axe, _, val = tag.partition("=")
        tags = await svct.remove(s, compte, _uuid(id), axe, val)
        if tags is None: raise HTTPException(404, "tag inconnu sur ce message")
        return {"ok": True, "supprimes": 1, "tags": tags}

    @action("PUT", "/{id}")
    async def resave(self, id: str, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        m = await svc.replace_draft(s, compte, _uuid(id), await request.json() or {}, store())
        if m is None: raise HTTPException(404, "aucun brouillon à ce nom")
        return {"ok": True, "modifies": 1, "message": m}

    @action("POST", "")
    async def create(self, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        corps = await request.json()
        m = await svc.create(s, compte, corps or {}, store(), ip_client=(request.client.host if request.client else None))
        if m is None: raise HTTPException(400, "aucune boîte pour ce compte")
        log.info("message %s créé par %s (%s)", m["id"], compte.login, "brouillon" if (corps or {}).get("composition") else "à envoyer")
        return {"ok": True, "crees": 1, "message": m}
