"""/dossiers, /identites, /carnet — F013 (D051, D047), F032 (D102, D116), F108 (D109)."""
from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_account
from ..journal import journal
from ..schema.models import Boite, Compte, Dossier, Identite
from ..services import folders_util as svc
from ..services.messages import account_mailboxes

log = journal("api")

def _uuid(v: str, quoi: str):
    try: return uuid.UUID(v)
    except ValueError: raise HTTPException(404, quoi + " inconnu")

async def _account_mailbox(s, compte, boite_id: str | None) -> Boite:
    boites = await account_mailboxes(s, compte)
    if not boites: raise HTTPException(404, "aucune boîte")
    if not boite_id: return boites[0]
    b = next((x for x in boites if str(x.boite_id) == boite_id), None)
    if b is None: raise HTTPException(404, "boîte inconnue")      # hors portée = 404 (D108)
    return b

class FoldersController(Controller):
    prefix = "/dossiers"

    @action("POST", "")
    async def create(self, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        c = await request.json() or {}
        b = await _account_mailbox(s, compte, c.get("boite_id"))
        parent = await self._my_folder(s, compte, c["parent_id"]) if c.get("parent_id") else None
        try: d = await svc.create_folder(s, b, c.get("nom"), parent)
        except ValueError as e: raise HTTPException(400, str(e))
        return {"ok": True, "crees": 1, "dossier": d}

    @action("PATCH", "/{id}")
    async def rename(self, id: str, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        d = await self._my_folder(s, compte, id)
        c = await request.json() or {}
        try: r = await svc.rename_folder(s, await s.get(Boite, d.boite_id), d, c.get("nom"))
        except PermissionError as e: raise HTTPException(409, str(e))
        except ValueError as e: raise HTTPException(400, str(e))
        return {"ok": True, "modifies": 1, "dossier": r}

    @action("DELETE", "/{id}")
    async def delete(self, id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        d = await self._my_folder(s, compte, id)
        try: await svc.delete_folder(s, await s.get(Boite, d.boite_id), d)
        except PermissionError as e: raise HTTPException(409, str(e))
        except ValueError as e: raise HTTPException(409, str(e))
        return {"ok": True, "supprimes": 1}

    async def _my_folder(self, s, compte, id: str) -> Dossier:
        d = await s.get(Dossier, _uuid(id, "dossier"))
        boites = [b.boite_id for b in await account_mailboxes(s, compte)]
        if d is None or d.boite_id not in boites: raise HTTPException(404, "dossier inconnu")
        return d

class IdentitiesController(Controller):
    prefix = "/identites"

    @action("GET", "")
    async def listing(self, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        l = await svc.identities(s, await account_mailboxes(s, compte))
        return {"identites": l, "total": len(l)}

    @action("POST", "")
    async def create(self, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        c = await request.json() or {}
        b = await _account_mailbox(s, compte, c.get("boite_id"))
        return {"ok": True, "crees": 1, "identite": await svc.create_identity(s, b, c)}

    @action("PATCH", "/{id}")
    async def update(self, id: str, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        i = await self._my_identity(s, compte, id)
        return {"ok": True, "modifies": 1, "identite": await svc.update_identity(s, i, await request.json() or {})}

    @action("DELETE", "/{id}")
    async def delete(self, id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        i = await self._my_identity(s, compte, id)
        try: await svc.delete_identity(s, i)
        except ValueError as e: raise HTTPException(409, str(e))
        return {"ok": True, "supprimes": 1}

    async def _my_identity(self, s, compte, id: str) -> Identite:
        i = await s.get(Identite, _uuid(id, "identité"))
        boites = [b.boite_id for b in await account_mailboxes(s, compte)]
        if i is None or i.boite_id not in boites: raise HTTPException(404, "identité inconnue")
        return i

class AddressBookController(Controller):
    @action("GET", "/carnet")
    async def address_book(self, q: str = Query(""), limit: int = Query(50, ge=1, le=500),
                     compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        l = await svc.address_book(s, await account_mailboxes(s, compte), q, limit)
        return {"carnet": l, "total": len(l)}
