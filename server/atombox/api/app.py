"""L'APPLICATION (D154, D158) : FastAPI, les contrôleurs montés par le routage, le contrat
vérifié au démarrage — une action hors de routes.yml est refusée.

    DATABASE_URL=postgresql:///atombox .venv/bin/uvicorn atombox.api.app:app
"""
from __future__ import annotations
import os, time
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from ..journal import journal
from .routing import register, check_contract
from ..modules import loading
from ..modules.hooks import hooks

def create_app(check: bool = True, modules=None) -> FastAPI:
    """monte les modules (internes, tiers, et ceux passés ici) — tout est module (D160)"""
    app = FastAPI(title="AtomBox", version="0.0.1", docs_url="/api/v1/doc", openapi_url="/api/v1/openapi.json")
    loaded = loading.load(extra=modules)
    controllers = [c for m in loaded for c in m.controllers]
    for m in loaded:
        for c in m.controllers:
            if not m.interne and not c.prefix.startswith(m.own_routes()): c.prefix = m.own_routes() + c.prefix
    table = register(app, controllers)
    app.state.modules = loaded
    app.state.table = table
    log = journal("api")

    cache = {"t": 0.0, "origines": []}
    async def _framers() -> list[str]:
        """les origines des applications autorisées à encadrer le webmail — relues toutes les 60 s"""
        if time.monotonic() - cache["t"] < 60: return cache["origines"]
        try:
            from sqlalchemy import select
            from urllib.parse import urlsplit
            from ..db import async_session_factory
            from ..schema.models import Application
            async with async_session_factory()() as s:
                apps = (await s.scalars(select(Application).where(Application.actif.is_(True)))).all()
            o = set()
            for a in apps:
                p = a.parametres or {}; u = urlsplit(p.get("url") or "")
                if p.get("delegation") and u.scheme in ("http", "https") and u.netloc: o.add("%s://%s" % (u.scheme, u.netloc))
            cache.update(t=time.monotonic(), origines=sorted(o))
        except Exception as e:
            log.warning("origines d'encadrement illisibles : %s — 'self' seul", e)
        return cache["origines"]

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        t0 = time.perf_counter()
        try:
            reponse = await call_next(request)
        except Exception:
            log.exception("%s %s : exception", request.method, request.url.path); raise
        # QUI PEUT AFFICHER LE WEBMAIL DANS UN CADRE (F148) : lui-même, et les applications qui ont
        # une délégation et une adresse. Sans cet en-tête, n'importe quel site pouvait l'encadrer.
        if not request.url.path.startswith("/api/"):
            reponse.headers["Content-Security-Policy"] = "frame-ancestors " + " ".join(["'self'"] + await _framers())
        ms = (time.perf_counter() - t0) * 1000
        (log.warning if reponse.status_code >= 500 else log.info if reponse.status_code >= 400 else log.debug)(
            "%s %s → %d en %.0f ms", request.method, request.url.path, reponse.status_code, ms)
        return reponse
    if check:
        bilan = check_contract(table, modules=[m.nom for m in loaded])
        if bilan["hors_contrat"]:
            raise SystemExit("actions hors contrat (routes.yml) : " + "; ".join(bilan["hors_contrat"]))
        app.state.contrat = bilan
        log.info("démarrage : %d module(s), %d action(s), %d/%d route(s) du contrat couverte(s), %d route(s) propre(s) aux modules", len(loaded), len(table), bilan["couvertes"], bilan["contrat"], bilan["propres"])
    hooks.emit("api.demarrage", app=app, table=table)
    # le webmail lui-même, en statique (D157 : un seul index ; ATOMBOX_WEBMAIL pour le dossier, vide = pas de statique)
    webmail = os.environ.get("ATOMBOX_WEBMAIL", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "webmail"))
    if webmail and os.path.isfile(os.path.join(webmail, "index.html")):
        app.mount("/", StaticFiles(directory=webmail, html=True), name="webmail")
    return app

app = create_app()
