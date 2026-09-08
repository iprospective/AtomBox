"""F113 — la synchronisation des états avec IMAP, dans les deux sens (D140b : IMAP reste la vérité).

Sans serveur IMAP : on éprouve la TRADUCTION (état ↔ FLAGS), la garde anti-boucle, et le fait
qu'un geste du webmail met bien un ordre dans la file. Le dialogue IMAP lui-même se valide sur
le pilote — un serveur simulé mentirait sur le seul point qui compte, le protocole."""
import uuid
from datetime import datetime, timezone
import pytest
from atombox.sync.sync import appliquer_descendante, descendante, drapeaux_voulus, en_descendante, etat_imap
from atombox.sync.module import login_de
from atombox.schema.modeles import Rattachement

def ratt(**k):
    d = dict(comm_id=uuid.uuid4(), boite_id=uuid.uuid4(), drapeau=False, statut="nouveau",
             personnel=False, gele=False, lu_le=None, uid_imap=12)
    d.update(k); return Rattachement(**d)

def test_traduction_vers_imap():
    poser, retirer = drapeaux_voulus(ratt())
    assert poser == [] and set(retirer) == {"\\Seen", "\\Flagged"}, "non lu et sans drapeau : on RETIRE les deux"
    poser, retirer = drapeaux_voulus(ratt(lu_le=datetime.now(timezone.utc), drapeau=True))
    assert set(poser) == {"\\Seen", "\\Flagged"} and retirer == []

def test_on_ne_touche_que_ce_qu_on_traduit():
    """un mot-clé posé par un autre client (\\Answered, $Label1) n'est jamais effacé (D140b)"""
    poser, retirer = drapeaux_voulus(ratt(lu_le=datetime.now(timezone.utc)))
    assert all(f in ("\\Seen", "\\Flagged") for f in poser + retirer)

def test_traduction_depuis_imap():
    assert etat_imap(["\\Seen", "$Label1"]) == {"lu": True, "drapeau": False, "supprime": False}
    assert etat_imap(["\\Flagged", "\\Deleted"]) == {"lu": False, "drapeau": True, "supprime": True}

def test_descendante_applique_et_se_tait_quand_rien_ne_bouge():
    r = ratt()
    assert appliquer_descendante(None, r, ["\\Seen"]) == ["lu"] and r.lu_le is not None
    assert appliquer_descendante(None, r, ["\\Seen"]) == [], "rien de neuf : rien à dire (le cas courant)"
    assert appliquer_descendante(None, r, []) == ["non lu"] and r.lu_le is None, "IMAP fait foi, même pour dé-lire"
    assert appliquer_descendante(None, r, ["\\Flagged"]) == ["drapeau"] and r.drapeau is True

def test_la_garde_anti_boucle():
    """appliquer un changement venu d'IMAP ne doit pas le renvoyer à IMAP"""
    assert not descendante()
    vu = []
    r = ratt()
    with en_descendante():
        assert descendante()
        appliquer_descendante(None, r, ["\\Seen"]); vu.append(descendante())
    assert vu == [True] and not descendante(), "le jeton se referme, même imbriqué"
    with en_descendante():
        with en_descendante(): pass
        assert descendante(), "imbrication : le jeton intérieur ne referme pas l'extérieur"

def test_login_master_ou_adresse():
    assert login_de("a@b.fr", "master") == "a@b.fr*master"
    assert login_de("a@b.fr", "") == "a@b.fr", "sans compte master : l'adresse seule"
    assert login_de("a@b.fr", "a@b.fr") == "a@b.fr", "le master EST la boîte : pas de séparateur"

def test_le_module_est_charge_et_abonne():
    from atombox.modules import chargement
    from atombox.modules.evenements import abonnes
    charges = chargement.charger(tiers=False)
    assert "sync" in [m.nom for m in charges]
    assert abonnes.pour("rattachement.change") and abonnes.pour("rattachement.change")[0][0] == "sync"
