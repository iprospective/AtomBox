"""L'APPLICATION (D154, D158) : FastAPI, les contrôleurs montés par le routage, le contrat
vérifié au démarrage — une action hors de routes.yml est refusée.

    DATABASE_URL=postgresql:///atombox .venv/bin/uvicorn atombox.api.app:app
"""
from __future__ import annotations
import time
from fastapi import FastAPI, Request
from ..journal import journal
from .routage import enregistrer, verifier_contrat
from ..controleurs import CONTROLEURS

def creer_app(verifier: bool = True) -> FastAPI:
    app = FastAPI(title="AtomBox", version="0.0.1", docs_url="/api/v1/doc", openapi_url="/api/v1/openapi.json")
    table = enregistrer(app, CONTROLEURS)
    app.state.table = table
    log = journal("api")

    @app.middleware("http")
    async def acces(request: Request, suite):
        t0 = time.perf_counter()
        try:
            reponse = await suite(request)
        except Exception:
            log.exception("%s %s : exception", request.method, request.url.path); raise
        ms = (time.perf_counter() - t0) * 1000
        (log.warning if reponse.status_code >= 500 else log.info if reponse.status_code >= 400 else log.debug)(
            "%s %s → %d en %.0f ms", request.method, request.url.path, reponse.status_code, ms)
        return reponse
    if verifier:
        bilan = verifier_contrat(table)
        if bilan["hors_contrat"]:
            raise SystemExit("actions hors contrat (routes.yml) : " + "; ".join(bilan["hors_contrat"]))
        app.state.contrat = bilan
        log.info("démarrage : %d action(s), %d/%d route(s) du contrat couverte(s)", len(table), bilan["couvertes"], bilan["contrat"])
    return app

app = creer_app()
