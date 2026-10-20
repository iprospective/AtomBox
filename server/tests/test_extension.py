"""D161 — déclencheurs (ORM), événements (hors processus), tâches (cadencées), dépendances entre modules."""
from datetime import datetime, timedelta, timezone
import pytest
from atombox.modules import Module, hook, trigger, event, task, loading
from atombox.modules.triggers import triggers, TriggerRefused
from atombox.modules.events import subscribers, process, DELAYS
from atombox.modules.tasks import tasks

class Journalise(Module):
    nom = "journalise"; seen = []
    @trigger("comm.apres_insertion")
    def insere(self, ctx): self.seen.append(("insertion", ctx["objet"].sujet))
    @trigger("rattachement.avant_modification")
    def modifie(self, ctx): self.seen.append(("modif", ctx["modifie"]))
    @trigger("compte.avant_suppression")
    def refuse(self, ctx): raise TriggerRefused("un compte ne se supprime pas, il se désactive (D118)")
    @event("message.ingere")
    def pousse(self, ctx): self.seen.append(("evenement", ctx["charge"]["comm_id"]))
    @task(every="10m", nom="ramasse")
    def ramasse(self, ctx): self.seen.append(("tache", "ramasse"))

class DependDe(Module):
    nom = "depend"; dependencies = ["journalise"]

class Orphelin(Module):
    nom = "orphelin"; dependencies = ["inexistant"]

@pytest.fixture
def modules():
    Journalise.seen.clear()
    loaded = loading.load(extra=[DependDe(), Journalise(), Orphelin()], tiers=False)
    yield loaded
    loading.load()

def test_declencheurs_par_entite(modules):
    from atombox.schema.models import Comm, Rattachement, Compte
    assert triggers.subscribers("comm.apres_insertion") == ["journalise"]
    assert "comm.avant_insertion" in triggers.points() and "evenement.apres_suppression" in triggers.points()
    triggers.run("comm.apres_insertion", Comm(sujet="Bonjour"))
    triggers.run("rattachement.avant_modification", Rattachement(), modifie={"lu_le": (None, "maintenant")})
    assert Journalise.seen == [("insertion", "Bonjour"), ("modif", {"lu_le": (None, "maintenant")})]
    with pytest.raises(TriggerRefused): triggers.run("compte.avant_suppression", Compte())
    with pytest.raises(ValueError): triggers.declare("nimporte.apres_insertion", lambda c: None, "x")

def test_evenements_tentatives_et_abandon(modules):
    from atombox.schema.models import Evenement
    e = Evenement(type="message.ingere", module="noyau", charge={"comm_id": "c1"}, cree_le=datetime.now(timezone.utc), prochaine_tentative=datetime.now(timezone.utc), tentatives=0)
    assert process(None, e) and e.traite_le and Journalise.seen[-1] == ("evenement", "c1")
    def casse(ctx): raise RuntimeError("webhook injoignable")
    subscribers.declare("appli.push", casse, "fragile")
    f = Evenement(type="appli.push", module="fragile", charge={}, cree_le=datetime.now(timezone.utc), prochaine_tentative=datetime.now(timezone.utc), tentatives=0)
    for i, delay in enumerate(DELAYS, 1):
        assert not process(None, f) and f.tentatives == i and f.traite_le is None
        assert timedelta(seconds=delay - 2) <= f.prochaine_tentative - datetime.now(timezone.utc) <= timedelta(seconds=delay)
    assert not process(None, f) and f.abandonne and f.traite_le, "après la dernière tentative : abandon, bruyant"
    subscribers.remove("fragile")

def test_taches_cadencees(modules):
    due = tasks.due()
    assert [(m, n) for m, n, _ in tasks.listing()] == [("journalise", "ramasse")] and len(due) == 1
    tasks.run(due[0]); assert Journalise.seen[-1] == ("tache", "ramasse")
    assert tasks.due() == [], "pas due avant 10 minutes"
    assert len(tasks.due(datetime.now(timezone.utc) + timedelta(minutes=11))) == 1
    with pytest.raises(ValueError): task(every="bientôt")(lambda c: None) and tasks.declare(lambda c: None, "x", "bientôt")

def test_dependances_ordonnent_et_ecartent(modules):
    names = [m.nom for m in modules]
    assert names.index("journalise") < names.index("depend"), "un module se charge après ses dépendances"
    assert "orphelin" not in names, "une dépendance absente écarte le module"
    assert names[:3] == ["session", "etat", "ingestion"]

def test_le_module_debranche_tout(modules):
    loading.load(tiers=False)
    assert triggers.subscribers("comm.apres_insertion") == [] and tasks.listing() == [] and subscribers.for_type("message.ingere") == []
