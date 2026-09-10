"""D160 — tout est module : un module tiers apporte des routes propres et des accroches ; un module qui plante n'abat pas le noyau."""
import pytest
from fastapi.testclient import TestClient
from atombox.modules import Module, accroche
from atombox.modules.accroches import accroches, POINTS
from atombox.modules import chargement
from atombox.api.routage import Controleur, action
from atombox.api.app import creer_app

class PingControleur(Controleur):
    @action("GET", "/ping")
    async def ping(self): return {"pong": True}

class ModuleTest(Module):
    nom = "test"; version = "1"; description = "un module tiers de test"
    controleurs = [PingControleur]
    vus = []
    @accroche("message.avant_ingestion")
    def etiqueter(self, ctx):
        ctx["tags"].append({"axe": "test", "val": "vu"})
        if "poison" in (ctx["analyse"].sujet or ""): ctx["ignorer"] = True; ctx["raison"] = "poison"
    @accroche("message.ingere")
    def noter(self, ctx): self.vus.append(ctx["comm_id"])

class ModuleCasse(Module):
    nom = "casse"
    @accroche("message.ingere")
    def boum(self, ctx): raise RuntimeError("je plante")

def test_module_tiers_routes_propres_et_contrat():
    app = creer_app(modules=[ModuleTest()])
    noms = [m.nom for m in app.state.modules]
    assert noms[:3] == ["session", "etat", "ingestion"] and "test" in noms, "les internes d'abord, écrits comme des modules"
    assert app.state.contrat["hors_contrat"] == [] and app.state.contrat["propres"] == 1
    c = TestClient(app)
    assert c.get("/api/v1/modules/test/ping").json() == {"pong": True}, "les routes d'un module tiers vivent sous /modules/<nom>/"
    assert accroches.abonnes("message.ingere") == ["test", "ingestion"] or set(accroches.abonnes("message.ingere")) == {"test", "ingestion"}
    chargement.charger()

def test_accroches_enrichissent_et_ignorent():
    from atombox.ingestion.analyse import analyser
    chargement.charger(supplementaires=[ModuleTest(), ModuleCasse()], tiers=False)
    a = analyser(b"From: a@b.fr\r\nSubject: bonjour\r\n\r\ncorps\r\n")
    ctx = accroches.emettre("message.avant_ingestion", analyse=a, boite_id=None, octets=b"", tags=[])
    assert ctx["tags"] == [{"axe": "test", "val": "vu"}] and not ctx.get("ignorer")
    ctx = accroches.emettre("message.avant_ingestion", analyse=analyser(b"Subject: poison\r\n\r\n"), boite_id=None, octets=b"", tags=[])
    assert ctx["ignorer"] and ctx["raison"] == "poison"
    ModuleTest.vus.clear()
    accroches.emettre("message.ingere", comm_id="c1", nouveau=True, analyse=a, boite_id=None, tags=[])
    assert ModuleTest.vus == ["c1"], "un module qui plante (casse) n'empêche pas les autres"
    chargement.charger()

def test_point_inconnu_refuse():
    with pytest.raises(ValueError):
        class M(Module):
            nom = "m"
            @accroche("nimporte.quoi")
            def x(self, ctx): pass

def test_les_points_sont_documentes():
    assert all(POINTS[p] for p in POINTS) and "message.ingere" in POINTS

def test_le_notify_ne_peut_plus_etre_muet():
    """Une session asynchrone rendait `execute` sous forme de coroutine : le NOTIFY ne partait
    jamais, l'événement attendait le réveil périodique (15 s) et l'écran ne bougeait pas. Une
    coroutine perdue ne se voit pas — ce refus, si."""
    from atombox.modules import evenements

    class SessionAsyncFactice:                      # ce que voit `emettre` d'une AsyncSession
        __name__ = "AsyncSession"
        def __init__(self): self.sync_session = object()
        def add(self, x): raise AssertionError("rien ne doit être ajouté avant le refus")

    SessionAsyncFactice.__name__ = "AsyncSession"
    faux = SessionAsyncFactice(); faux.__class__.__name__ = "AsyncSession"
    with pytest.raises(TypeError, match="emettre_async"):
        evenements.emettre(faux, "message.a_envoyer", {})
