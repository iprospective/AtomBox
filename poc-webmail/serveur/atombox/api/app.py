"""L'APPLICATION (D154, D158) : FastAPI, les contrôleurs montés par le routage, le contrat
vérifié au démarrage — une action hors de routes.yml est refusée.

    DATABASE_URL=postgresql:///atombox .venv/bin/uvicorn atombox.api.app:app
"""
from __future__ import annotations
from fastapi import FastAPI
from .routage import enregistrer, verifier_contrat
from ..controleurs import CONTROLEURS

def creer_app(verifier: bool = True) -> FastAPI:
    app = FastAPI(title="AtomBox", version="0.0.1", docs_url="/api/v1/doc", openapi_url="/api/v1/openapi.json")
    table = enregistrer(app, CONTROLEURS)
    app.state.table = table
    if verifier:
        bilan = verifier_contrat(table)
        if bilan["hors_contrat"]:
            raise SystemExit("actions hors contrat (routes.yml) : " + "; ".join(bilan["hors_contrat"]))
        app.state.contrat = bilan
    return app

app = creer_app()
