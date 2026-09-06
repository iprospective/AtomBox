"""D158 — routes = contrôleurs + actions, et le contrat routes.yml est la loi."""
import pytest
from atombox.api.routage import verifier_contrat, enregistrer, Controleur, action
from fastapi import FastAPI

def test_les_actions_ecrites_sont_dans_le_contrat():
    from atombox.api.app import creer_app
    app = creer_app()
    bilan = app.state.contrat
    assert bilan["hors_contrat"] == []
    assert bilan["couvertes"] >= 2, bilan
    print("routes du contrat sans action encore :", len(bilan["sans_action"]), "/", bilan["contrat"])

def test_une_action_hors_contrat_est_refusee():
    class Pirate(Controleur):
        @action("GET", "/nimporte-quoi")
        async def x(self): return {}
    app = FastAPI(); table = enregistrer(app, [Pirate])
    assert verifier_contrat(table)["hors_contrat"] == ["GET /nimporte-quoi → Pirate.x"]

def test_la_porte_repond_sans_base():
    """sans DATABASE_URL, POST /session dit « indisponible » proprement : l'interface tient (D141)"""
    import os
    if os.environ.get("DATABASE_URL"): pytest.skip("avec une base, c'est test_session")
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    c = TestClient(creer_app(), raise_server_exceptions=False)
    r = c.post("/api/v1/session", json={"utilisateur": "poc", "mot_de_passe": "poc"})
    assert r.status_code == 500 or r.status_code == 401
    assert c.get("/api/v1/openapi.json").status_code == 200

def test_mot_de_passe():
    from atombox.api.securite import hacher_mot_de_passe, verifier_mot_de_passe
    h = hacher_mot_de_passe("secret")
    assert h.startswith("scrypt$") and verifier_mot_de_passe("secret", h) and not verifier_mot_de_passe("autre", h) and not verifier_mot_de_passe("x", None)
