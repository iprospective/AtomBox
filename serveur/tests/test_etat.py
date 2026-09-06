"""F122 — le journal se lit dans l'interface, par un compte connecté."""
import os
from fastapi.testclient import TestClient
from atombox import journal as J
from atombox.api.app import creer_app
from atombox.api.securite import compte_courant

class FauxCompte: login = "test"; actif = True

def test_journal_par_l_api(tmp_path):
    d = str(tmp_path / "logs"); J.configurer(dossier_logs=d, niveau="debug", console=False, forcer=True)
    try:
        J.journal("imap").debug("EXAMINE INBOX"); J.journal("imap").warning("IDLE refusé"); J.journal("auth").warning("connexion refusée pour 'x'")
        for lg in ("atombox", "atombox.imap", "atombox.auth"):
            import logging
            for h in logging.getLogger(lg).handlers: h.flush()
        app = creer_app(); app.dependency_overrides[compte_courant] = lambda: FauxCompte()
        c = TestClient(app)
        assert c.get("/api/v1/etat/journal").status_code == 200
        r = c.get("/api/v1/etat/journal", params={"domaine": "imap", "niveau": "DEBUG"}).json()
        assert [l["message"] for l in r["lignes"]] == ["EXAMINE INBOX", "IDLE refusé"]
        r = c.get("/api/v1/etat/journal", params={"domaine": "erreurs"}).json()
        assert {l["domaine"] for l in r["lignes"]} == {"imap", "auth"} and all(l["niveau"] == "WARNING" for l in r["lignes"])
        r = c.get("/api/v1/etat/journal", params={"domaine": "imap", "niveau": "WARNING", "filtre": "idle"}).json()
        assert len(r["lignes"]) == 1
        assert c.get("/api/v1/etat/journal", params={"domaine": "nimporte"}).status_code == 404
        app.dependency_overrides.clear()
        c2 = TestClient(creer_app(), raise_server_exceptions=False)
        assert c2.get("/api/v1/etat/journal").status_code in (401, 500), "sans jeton, pas de journal"
    finally:
        J.configurer(forcer=True)
