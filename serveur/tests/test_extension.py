"""D161 — déclencheurs (ORM), événements (hors processus), tâches (cadencées), dépendances entre modules."""
from datetime import datetime, timedelta, timezone
import pytest
from atombox.modules import Module, accroche, declencheur, evenement, tache, chargement
from atombox.modules.declencheurs import declencheurs, RefusDeclencheur
from atombox.modules.evenements import abonnes, traiter, DELAIS
from atombox.modules.taches import taches

class Journalise(Module):
    nom = "journalise"; vus = []
    @declencheur("comm.apres_insertion")
    def insere(self, ctx): self.vus.append(("insertion", ctx["objet"].sujet))
    @declencheur("rattachement.avant_modification")
    def modifie(self, ctx): self.vus.append(("modif", ctx["modifie"]))
    @declencheur("compte.avant_suppression")
    def refuse(self, ctx): raise RefusDeclencheur("un compte ne se supprime pas, il se désactive (D118)")
    @evenement("message.ingere")
    def pousse(self, ctx): self.vus.append(("evenement", ctx["charge"]["comm_id"]))
    @tache(chaque="10m", nom="ramasse")
    def ramasse(self, ctx): self.vus.append(("tache", "ramasse"))

class DependDe(Module):
    nom = "depend"; dependances = ["journalise"]

class Orphelin(Module):
    nom = "orphelin"; dependances = ["inexistant"]

@pytest.fixture
def modules():
    Journalise.vus.clear()
    charges = chargement.charger(supplementaires=[DependDe(), Journalise(), Orphelin()], tiers=False)
    yield charges
    chargement.charger()

def test_declencheurs_par_entite(modules):
    from atombox.schema.modeles import Comm, Rattachement, Compte
    assert declencheurs.abonnes("comm.apres_insertion") == ["journalise"]
    assert "comm.avant_insertion" in declencheurs.points() and "evenement.apres_suppression" in declencheurs.points()
    declencheurs.lancer("comm.apres_insertion", Comm(sujet="Bonjour"))
    declencheurs.lancer("rattachement.avant_modification", Rattachement(), modifie={"lu_le": (None, "maintenant")})
    assert Journalise.vus == [("insertion", "Bonjour"), ("modif", {"lu_le": (None, "maintenant")})]
    with pytest.raises(RefusDeclencheur): declencheurs.lancer("compte.avant_suppression", Compte())
    with pytest.raises(ValueError): declencheurs.declarer("nimporte.apres_insertion", lambda c: None, "x")

def test_evenements_tentatives_et_abandon(modules):
    from atombox.schema.modeles import Evenement
    e = Evenement(type="message.ingere", module="noyau", charge={"comm_id": "c1"}, cree_le=datetime.now(timezone.utc), prochaine_tentative=datetime.now(timezone.utc), tentatives=0)
    assert traiter(None, e) and e.traite_le and Journalise.vus[-1] == ("evenement", "c1")
    def casse(ctx): raise RuntimeError("webhook injoignable")
    abonnes.declarer("appli.push", casse, "fragile")
    f = Evenement(type="appli.push", module="fragile", charge={}, cree_le=datetime.now(timezone.utc), prochaine_tentative=datetime.now(timezone.utc), tentatives=0)
    for i, delai in enumerate(DELAIS, 1):
        assert not traiter(None, f) and f.tentatives == i and f.traite_le is None
        assert timedelta(seconds=delai - 2) <= f.prochaine_tentative - datetime.now(timezone.utc) <= timedelta(seconds=delai)
    assert not traiter(None, f) and f.abandonne and f.traite_le, "après la dernière tentative : abandon, bruyant"
    abonnes.retirer("fragile")

def test_taches_cadencees(modules):
    dues = taches.dues()
    assert [(m, n) for m, n, _ in taches.liste()] == [("journalise", "ramasse")] and len(dues) == 1
    taches.lancer(dues[0]); assert Journalise.vus[-1] == ("tache", "ramasse")
    assert taches.dues() == [], "pas due avant 10 minutes"
    assert len(taches.dues(datetime.now(timezone.utc) + timedelta(minutes=11))) == 1
    with pytest.raises(ValueError): tache(chaque="bientôt")(lambda c: None) and taches.declarer(lambda c: None, "x", "bientôt")

def test_dependances_ordonnent_et_ecartent(modules):
    noms = [m.nom for m in modules]
    assert noms.index("journalise") < noms.index("depend"), "un module se charge après ses dépendances"
    assert "orphelin" not in noms, "une dépendance absente écarte le module"
    assert noms[:3] == ["session", "etat", "ingestion"]

def test_le_module_debranche_tout(modules):
    chargement.charger(tiers=False)
    assert declencheurs.abonnes("comm.apres_insertion") == [] and taches.liste() == [] and abonnes.pour("message.ingere") == []
