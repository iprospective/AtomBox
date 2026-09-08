"""F016 — le moteur de filtres (D074) : prédicats, ordre, actions, et le compteur qui rend une
règle muette visible (D075 § 1 — celle du chapitre 14, un `allof` là où il fallait `anyof`)."""
import os, re as _re, uuid as _uuid
from datetime import datetime, timedelta, timezone
import pytest
from atombox.filtres.moteur import ACTIONS, CHAMPS, OPERATEURS, appliquer, evaluer
from atombox.ingestion.analyse import analyser

F = os.path.join(os.path.dirname(__file__), "fixtures")
def lire(n): return open(os.path.join(F, n), "rb").read()

class Regle:
    """une règle en mémoire — le moteur ne demande qu'une chose : des attributs"""
    def __init__(self, nom, predicat, action, ordre=1, debut=None, fin=None):
        self.nom, self.predicat, self.action, self.ordre = nom, predicat, action, ordre
        self.fenetre_debut, self.fenetre_fin = debut, fin
        self.nb_declenchements, self.dernier_declenchement = 0, None

def crit(champ, op, val, mode="et"): return {"mode": mode, "criteres": [{"champ": champ, "operateur": op, "valeur": val}]}

def test_les_operateurs():
    a = analyser(lire("simple.eml"))
    assert evaluer(crit("from", "contient", "tessier"), a)
    assert evaluer(crit("from", "finit_par", ".example"), a)
    assert not evaluer(crit("from", "est", "autre@x.fr"), a)
    assert evaluer(crit("sujet", "commence_par", "Re:"), a)
    assert evaluer(crit("sujet", "correspond_a", r"commande \d+"), a)
    assert evaluer(crit("destinataire", "contient", "contact@exemple.fr"), a)
    assert evaluer(crit("taille", "superieur_a", 10), a) and not evaluer(crit("taille", "superieur_a", 10 ** 9), a)
    assert evaluer(crit("pieces", "superieur_a", 0), analyser(lire("pieces.eml")))
    assert evaluer(crit("liste", "existe", None), analyser(lire("liste.eml")))
    assert not evaluer(crit("liste", "existe", None), a), "un message humain n'a pas de List-Id"

def test_et_ou():
    a = analyser(lire("simple.eml"))
    deux = lambda mode: {"mode": mode, "criteres": [{"champ": "from", "operateur": "contient", "valeur": "tessier"},
                                                    {"champ": "sujet", "operateur": "contient", "valeur": "introuvable"}]}
    assert not evaluer(deux("et"), a) and evaluer(deux("ou"), a)

def test_un_critere_incomprehensible_est_faux():
    """une règle qu'on ne comprend pas ne doit pas attraper du courrier"""
    a = analyser(lire("simple.eml"))
    assert not evaluer(crit("champ_inconnu", "contient", "x"), a)
    assert not evaluer(crit("from", "operateur_inconnu", "x"), a)
    assert not evaluer({"criteres": []}, a), "un prédicat vide n'attrape rien"

def test_ordre_et_arret():
    a = analyser(lire("liste.eml"))
    r1 = Regle("classer les listes", crit("liste", "existe", None), {"type": "classer", "dossier": "Lettres"}, 1)
    r2 = Regle("tout marquer lu", crit("from", "contient", "@"), {"type": "marquer_lu"}, 2)
    r = appliquer(None, [r1, r2], a)
    assert r["dossier"] == "Lettres" and r["patch"]["lu"] is True and r["regles"] == ["classer les listes", "tout marquer lu"]
    r1b = Regle("classer et stop", crit("liste", "existe", None), {"type": "classer", "dossier": "Lettres", "arreter": True}, 1)
    r = appliquer(None, [r1b, r2], a)
    assert r["regles"] == ["classer et stop"], "« arrêter » interrompt la chaîne, comme le stop de Sieve"

def test_les_actions():
    a = analyser(lire("simple.eml"))
    tout = lambda t, **k: appliquer(None, [Regle("r", crit("from", "contient", "tessier"), {"type": t, **k})], a)
    assert tout("corbeille")["dossier"] == "Trash"
    assert tout("indesirable")["dossier"] == "Junk"
    assert tout("drapeau")["patch"]["drapeau"] is True
    assert tout("statut", statut="a_faire")["patch"]["statut"] == "a_faire"
    assert tout("ignorer")["ignorer"] is True
    assert set(ACTIONS) >= {"classer", "marquer_lu", "drapeau", "statut", "corbeille", "indesirable", "arreter", "ignorer"}

def test_le_compteur_rend_une_regle_muette_visible():
    """D075 § 1 : le chapitre 14 a trouvé une règle jamais déclenchée depuis des années"""
    a = analyser(lire("simple.eml"))
    active = Regle("attrape", crit("from", "contient", "tessier"), {"type": "drapeau"}, 1)
    muette = Regle("jamais", crit("from", "contient", "personne-de-ce-nom"), {"type": "drapeau"}, 2)
    appliquer(None, [active, muette], a); appliquer(None, [active, muette], a)
    assert active.nb_declenchements == 2 and active.dernier_declenchement is not None
    assert muette.nb_declenchements == 0 and muette.dernier_declenchement is None, "une règle muette se voit"

def test_la_fenetre_de_dates():
    """une absence est une règle à fenêtre (D113)"""
    a = analyser(lire("simple.eml"))
    hier = datetime.now(timezone.utc) - timedelta(days=1); demain = datetime.now(timezone.utc) + timedelta(days=1)
    passee = Regle("finie", crit("from", "contient", "@"), {"type": "drapeau"}, 1, debut=hier - timedelta(days=2), fin=hier)
    active = Regle("en cours", crit("from", "contient", "@"), {"type": "drapeau"}, 2, debut=hier, fin=demain)
    r = appliquer(None, [passee, active], a)
    assert r["regles"] == ["en cours"] and passee.nb_declenchements == 0

def test_le_vocabulaire_est_ferme():
    assert "from" in CHAMPS and "dossier" in CHAMPS and "corps" in CHAMPS
    assert "contient" in OPERATEURS and "correspond_a" in OPERATEURS

def test_les_routes_sont_au_contrat():
    from atombox.api.app import creer_app
    app = creer_app(); ecrites = {(m, c) for m, c, _ in app.state.table}
    for m, c in (("GET", "/filtres"), ("POST", "/filtres"), ("PATCH", "/filtres/{id}"), ("DELETE", "/filtres/{id}")):
        assert (m, c) in ecrites, (m, c)
    assert app.state.contrat["hors_contrat"] == []
