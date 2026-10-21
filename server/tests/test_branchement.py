"""Le branchement (lot 2) : le webmail servi par l'API, le contrat couvert pour tout ce que le POC appelle."""
import os
from fastapi.testclient import TestClient
from atombox.api.app import create_app

def test_toutes_les_routes_du_poc_ont_une_action():
    app = create_app(); ecrites = {(m, c) for m, c, _ in app.state.table}
    for m, c in (("POST", "/dossiers-virtuels"), ("DELETE", "/dossiers-virtuels/{id}"), ("GET", "/parametres"), ("PUT", "/parametres"),
                 ("GET", "/pieces-jointes"), ("GET", "/recherche"), ("POST", "/session"), ("DELETE", "/session"), ("GET", "/referentiels"), ("GET", "/arborescence")):
        assert (m, c) in ecrites, (m, c)
    print("contrat :", app.state.contrat["couvertes"], "/", app.state.contrat["contrat"], "— sans action :", app.state.contrat["sans_action"])

def test_le_webmail_est_servi_par_l_api():
    app = create_app(); c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200 and "AtomBox" in r.text and "src/noyau/chargeur.js" in r.text
    assert c.get("/css/app.css").status_code == 200 and c.get("/src/noyau/amorcage.js").status_code == 200
    assert c.get("/api/v1/openapi.json").status_code == 200, "l'API reste sous /api/v1, le webmail sur /"

def test_amorcer_est_idempotent_sans_base():
    from atombox.bootstrap import main
    import pytest
    with pytest.raises(SystemExit): main(["--login"])   # argparse : arguments manquants → sortie propre
