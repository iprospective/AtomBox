"""CE QU'UNE APPLICATION DIT D'ELLE-MÊME (F048, D019, D187 ; RM3518).

Trois routes, et seulement pour un jeton d'APPLICATION — une personne qui les appelle reçoit 404 :
une session n'est pas une application, et ces ressources n'existent pas pour elle (D108).

    GET   /application                 qui suis-je : portée, axes (avec leurs libellés), paramètres
    PATCH /application                 mes paramètres — pour Dolibarr, les hôtes de mes Message-ID
    PUT   /axes/{axe}/valeurs          mes valeurs, avec leur LIBELLÉ (« PR2610-0012 — client »)

Le module pousse ; AtomBox n'appelle jamais l'application (chapitre 07)."""
from __future__ import annotations
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_reader
from ..applications import AppPrincipal
from ..connectors import declaration
from ..journal import journal
from ..schema.models import Axe, Tag
from ..uuid7 import uuid7

log = journal("api")
MAX_VALUES = 5000          # un lot ; au-delà, l'application pousse en plusieurs fois


def _app(qui):
    if not isinstance(qui, AppPrincipal): raise HTTPException(404, "réservé à une application connectée")
    return qui.application


def describe(app) -> dict:
    d = declaration(app.type_connecteur) or {}
    libelles = {k: v.get("libelle", k) for k, v in (d.get("axes") or {}).items()}
    return {"nom": app.nom, "type": app.type_connecteur, "portee": app.portee,
            "axes": [{"id": a, "libelle": libelles.get(a, a)} for a in (app.axes or [])],
            "parametres": app.parametres or {}}


class ApplicationController(Controller):
    @action("GET", "/application")
    async def me(self, qui=Depends(current_reader)):
        return describe(_app(qui))

    @action("PATCH", "/application")
    async def settings(self, request: Request, qui=Depends(current_reader), s: AsyncSession = Depends(async_session)):
        """Seuls les paramètres que le TYPE connaît se règlent ici ; la portée et les axes restent à
        l'administrateur (ce serait sinon un jeton qui élargit lui-même ce qu'il voit)."""
        app = _app(qui)
        corps = await request.json() or {}
        p = dict(app.parametres or {})
        if "hotes" in corps:
            hotes = corps["hotes"]
            if not isinstance(hotes, list) or not all(isinstance(h, str) and h.strip() and "@" not in h for h in hotes):
                raise HTTPException(422, "hotes : une liste de noms d'hôte")
            p["hotes"] = sorted({h.strip().lower() for h in hotes})
        app.parametres = p
        await s.commit()
        log.info("application « %s » : paramètres %s", app.nom, p)
        return describe(app)

    @action("PUT", "/axes/{axe}/valeurs")
    async def values(self, axe: str, request: Request, qui=Depends(current_reader), s: AsyncSession = Depends(async_session)):
        """Upsert d'un lot : la VALEUR est la clé stable (l'id chez l'application), le LIBELLÉ se
        resynchronise librement (champs.yml : tag.libelle est recalculable). `actif: false` retire
        la valeur des complétions sans toucher aux messages déjà étiquetés."""
        app = _app(qui)
        a = await s.scalar(select(Axe).where(Axe.nom == axe.lower(), Axe.application_id == app.application_id))
        if a is None: raise HTTPException(404, "axe inconnu de cette application")
        corps = await request.json() or {}
        lot = corps.get("valeurs") if isinstance(corps, dict) else None
        if not isinstance(lot, list) or len(lot) > MAX_VALUES:
            raise HTTPException(422, "valeurs : une liste de {valeur, libelle, actif?, ref_externe?} (%d au plus)" % MAX_VALUES)
        existants = {t.valeur: t for t in await s.scalars(select(Tag).where(Tag.axe_id == a.axe_id))}
        crees = modifies = 0
        for v in lot:
            valeur = str((v or {}).get("valeur") or "").strip()
            if not valeur: raise HTTPException(422, "une valeur sans clé")
            libelle = str(v.get("libelle") or valeur).strip()
            t = existants.get(valeur)
            if t is None:
                t = Tag(tag_id=uuid7(), axe_id=a.axe_id, valeur=valeur, libelle=libelle,
                        ref_externe=v.get("ref_externe"), actif=v.get("actif", True) is not False)
                s.add(t); existants[valeur] = t; crees += 1
            elif (t.libelle, t.actif, t.ref_externe) != (libelle, v.get("actif", True) is not False, v.get("ref_externe", t.ref_externe)):
                t.libelle, t.actif = libelle, v.get("actif", True) is not False
                if "ref_externe" in v: t.ref_externe = v["ref_externe"]
                modifies += 1
        await s.commit()
        log.info("application « %s », axe %s : %d valeur(s) créée(s), %d modifiée(s)", app.nom, a.nom, crees, modifies)
        return {"ok": True, "crees": crees, "modifies": modifies}
