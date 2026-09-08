"""/dossiers, /identites, /carnet — F013 (D051, D047), F032 (D102, D116), F108 (D109)."""
from __future__ import annotations
import uuid
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..journal import journal
from ..schema.modeles import Boite, Compte, Dossier, Identite
from ..services import dossiers_util as svc
from ..services.messages import boites_du_compte

log = journal("api")

def _uuid(v: str, quoi: str):
    try: return uuid.UUID(v)
    except ValueError: raise HTTPException(404, quoi + " inconnu")

async def _boite_du_compte(s, compte, boite_id: str | None) -> Boite:
    boites = await boites_du_compte(s, compte)
    if not boites: raise HTTPException(404, "aucune boîte")
    if not boite_id: return boites[0]
    b = next((x for x in boites if str(x.boite_id) == boite_id), None)
    if b is None: raise HTTPException(404, "boîte inconnue")      # hors portée = 404 (D108)
    return b

class DossiersControleur(Controleur):
    prefixe = "/dossiers"

    @action("POST", "")
    async def creer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        c = await request.json() or {}
        b = await _boite_du_compte(s, compte, c.get("boite_id"))
        parent = await self._mien(s, compte, c["parent_id"]) if c.get("parent_id") else None
        try: d = await svc.creer_dossier(s, b, c.get("nom"), parent)
        except ValueError as e: raise HTTPException(400, str(e))
        return {"ok": True, "crees": 1, "dossier": d}

    @action("PATCH", "/{id}")
    async def renommer(self, id: str, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        d = await self._mien(s, compte, id)
        c = await request.json() or {}
        try: r = await svc.renommer_dossier(s, await s.get(Boite, d.boite_id), d, c.get("nom"))
        except PermissionError as e: raise HTTPException(409, str(e))
        except ValueError as e: raise HTTPException(400, str(e))
        return {"ok": True, "modifies": 1, "dossier": r}

    @action("DELETE", "/{id}")
    async def supprimer(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        d = await self._mien(s, compte, id)
        try: await svc.supprimer_dossier(s, await s.get(Boite, d.boite_id), d)
        except PermissionError as e: raise HTTPException(409, str(e))
        except ValueError as e: raise HTTPException(409, str(e))
        return {"ok": True, "supprimes": 1}

    async def _mien(self, s, compte, id: str) -> Dossier:
        d = await s.get(Dossier, _uuid(id, "dossier"))
        boites = [b.boite_id for b in await boites_du_compte(s, compte)]
        if d is None or d.boite_id not in boites: raise HTTPException(404, "dossier inconnu")
        return d

class IdentitesControleur(Controleur):
    prefixe = "/identites"

    @action("GET", "")
    async def liste(self, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        l = await svc.identites(s, await boites_du_compte(s, compte))
        return {"identites": l, "total": len(l)}

    @action("POST", "")
    async def creer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        c = await request.json() or {}
        b = await _boite_du_compte(s, compte, c.get("boite_id"))
        return {"ok": True, "crees": 1, "identite": await svc.creer_identite(s, b, c)}

    @action("PATCH", "/{id}")
    async def modifier(self, id: str, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        i = await self._mienne(s, compte, id)
        return {"ok": True, "modifies": 1, "identite": await svc.modifier_identite(s, i, await request.json() or {})}

    @action("DELETE", "/{id}")
    async def supprimer(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        i = await self._mienne(s, compte, id)
        try: await svc.supprimer_identite(s, i)
        except ValueError as e: raise HTTPException(409, str(e))
        return {"ok": True, "supprimes": 1}

    async def _mienne(self, s, compte, id: str) -> Identite:
        i = await s.get(Identite, _uuid(id, "identité"))
        boites = [b.boite_id for b in await boites_du_compte(s, compte)]
        if i is None or i.boite_id not in boites: raise HTTPException(404, "identité inconnue")
        return i

class CarnetControleur(Controleur):
    @action("GET", "/carnet")
    async def carnet(self, q: str = Query(""), limite: int = Query(50, ge=1, le=500),
                     compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        l = await svc.carnet(s, await boites_du_compte(s, compte), q, limite)
        return {"carnet": l, "total": len(l)}
