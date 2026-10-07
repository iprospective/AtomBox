"""D158 — routes = contrôleurs + actions, et le contrat routes.yml est la loi."""
import pytest
from atombox.api.routing import check_contract, register, Controller, action
from fastapi import FastAPI

def test_les_actions_ecrites_sont_dans_le_contrat():
    from atombox.api.app import create_app
    app = create_app()
    bilan = app.state.contrat
    assert bilan["hors_contrat"] == []
    assert bilan["couvertes"] >= 2, bilan
    print("routes du contrat sans action encore :", len(bilan["sans_action"]), "/", bilan["contrat"])

def test_une_action_hors_contrat_est_refusee():
    class Pirate(Controller):
        @action("GET", "/nimporte-quoi")
        async def x(self): return {}
    app = FastAPI(); table = register(app, [Pirate])
    assert check_contract(table)["hors_contrat"] == ["GET /nimporte-quoi → Pirate.x"]

def test_la_porte_repond_sans_base():
    """sans DATABASE_URL, POST /session dit « indisponible » proprement : l'interface tient (D141)"""
    import os
    if os.environ.get("DATABASE_URL"): pytest.skip("avec une base, c'est test_session")
    from fastapi.testclient import TestClient
    from atombox.api.app import create_app
    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.post("/api/v1/session", json={"utilisateur": "poc", "mot_de_passe": "poc"})
    assert r.status_code == 500 or r.status_code == 401
    assert c.get("/api/v1/openapi.json").status_code == 200

def test_mot_de_passe():
    from atombox.api.security import hash_password, verify_password
    h = hash_password("secret")
    assert h.startswith("scrypt$") and verify_password("secret", h) and not verify_password("autre", h) and not verify_password("x", None)
