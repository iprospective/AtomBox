"""F113 — la synchronisation des états avec IMAP, dans les deux sens (D140b : IMAP reste la vérité).

Sans serveur IMAP : on éprouve la TRADUCTION (état ↔ FLAGS), la garde anti-boucle, et le fait
qu'un geste du webmail met bien un ordre dans la file. Le dialogue IMAP lui-même se valide sur
le pilote — un serveur simulé mentirait sur le seul point qui compte, le protocole.

CE QUE D175 A CHANGÉ ICI, et qu'il faut éprouver : les drapeaux ne sont plus sur le rattachement,
ils sont sur la PERSONNE qui relève. Deux conséquences testées plus bas, parce qu'elles sont
exactement ce qu'on risquait de perdre :

  * un `\\Seen` retiré chez le fournisseur n'EFFACE PLUS la date d'ouverture — il pose « à revoir » ;
  * une boîte à plusieurs membres n'impute l'état à personne : le fournisseur ne dit pas qui a lu.
"""
import os, re as _re, uuid
from datetime import datetime, timezone
import pytest
from atombox.sync.sync import appliquer_descendante, descendante, drapeaux_voulus, en_descendante, etat_imap
from atombox.sync.module import login_de
from atombox.schema.modeles import Rattachement


def ratt(**k):
    d = dict(comm_id=uuid.uuid4(), boite_id=uuid.uuid4(), status="new",
             personnel=False, gele=False, uid_imap=12)
    d.update(k); return Rattachement(**d)


# L'objet de valeur du PRODUIT, pas une doublure locale : c'est lui qui porte la règle
# « vu = ouvert ET pas à revoir », et une doublure l'aurait contournée sans qu'on le voie.
from atombox.services.personal_state import PersonalState as EtatFeint


def test_traduction_vers_imap():
    poser, retirer = drapeaux_voulus(ratt(), None)
    assert poser == [] and set(retirer) == {"\\Seen", "\\Flagged"}, \
        "personne n'y a touché : aucune ligne, donc on RETIRE les deux"
    poser, retirer = drapeaux_voulus(ratt(), EtatFeint(datetime.now(timezone.utc), flagged=True))
    assert set(poser) == {"\\Seen", "\\Flagged"} and retirer == []
    # « à revoir » se PROJETTE en IMAP par le retrait de \\Seen : le message reparaît en gras dans
    # Thunderbird comme dans le webmail, et le fait (opened_at) reste écrit dessous (D175 § 2).
    poser, retirer = drapeaux_voulus(ratt(), EtatFeint(datetime.now(timezone.utc), a_revoir=True))
    assert "\\Seen" in retirer and "\\Seen" not in poser


def test_le_drapeau_pousse_est_celui_d_une_personne():
    """LA RÉGRESSION À INTERDIRE : lire l'état sur le rattachement. Il n'y est plus, et s'il y
    revenait par un `getattr` distrait, ce test le verrait — le rattachement n'a plus ni `lu_le`
    ni `drapeau`, donc la traduction ne peut rien en tirer."""
    r = ratt()
    assert not hasattr(r, "lu_le") and not hasattr(r, "drapeau"), \
        "l'état personnel a quitté le rattachement (D175) : il ne doit pas y repousser"
    poser, _ = drapeaux_voulus(r, EtatFeint(datetime.now(timezone.utc)))
    assert poser == ["\\Seen"], "c'est l'état de la PERSONNE qui décide, et lui seul"


def test_on_ne_touche_que_ce_qu_on_traduit():
    """un mot-clé posé par un autre client (\\Answered, $Label1) n'est jamais effacé (D140b)"""
    poser, retirer = drapeaux_voulus(ratt(), EtatFeint(datetime.now(timezone.utc)))
    assert all(f in ("\\Seen", "\\Flagged") for f in poser + retirer)


def test_traduction_depuis_imap():
    assert etat_imap(["\\Seen", "$Label1"]) == {"lu": True, "drapeau": False, "supprime": False}
    assert etat_imap(["\\Flagged", "\\Deleted"]) == {"lu": False, "drapeau": True, "supprime": True}


def test_la_garde_anti_boucle():
    """appliquer un changement venu d'IMAP ne doit pas le renvoyer à IMAP"""
    assert not descendante()
    with en_descendante():
        assert descendante()
    assert not descendante(), "le jeton se referme"
    with en_descendante():
        with en_descendante(): pass
        assert descendante(), "imbrication : le jeton intérieur ne referme pas l'extérieur"
    assert not descendante()


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


# ── ce qui demande une vraie base ───────────────────────────────────────────────────────────────
@pytest.fixture
def base():
    """une base jetable au schéma courant — la descendante écrit, on ne peut pas la feindre"""
    if not os.environ.get("DATABASE_URL"): pytest.skip("DATABASE_URL absent")
    import psycopg
    from atombox.db import session as ouvrir
    nom = "atombox_sync_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    admin.execute('CREATE DATABASE "%s"' % nom)
    u = _re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", os.environ["DATABASE_URL"], count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c:
        c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    s = ouvrir(u)
    try:
        yield s, u
    finally:
        s.close()
        import atombox.db as db; db.moteur(u).dispose(); db._sync.clear()
        admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
        admin.execute('DROP DATABASE "%s"' % nom); admin.close()


def _boite_avec(s, membres: int):
    """une boîte, son INBOX, un message rattaché, et `membres` comptes qui y accèdent"""
    from atombox.ingestion.ingestion import adresse as adresse_de
    from atombox.schema.modeles import Acces, Boite, Comm, Compte, Dossier
    from atombox.schema.seeds import seed_builtins
    from atombox.uuid7 import uuid7
    a = adresse_de(s, "boite@exemple.fr")
    b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="personnelle"); s.add(b)
    d = Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(d)
    comptes = []
    for i in range(membres):
        c = Compte(compte_id=uuid7(), login="m%d@exemple.fr" % i, nom="M%d" % i, actif=True,
                   cree_le=datetime.now(timezone.utc))
        s.add(c); comptes.append(c)
        s.add(Acces(compte_id=c.compte_id, boite_id=b.boite_id, role="membre",
                    debut=datetime.now(timezone.utc), accorde_par=c.compte_id))
    seed_builtins(s)      # les marqueurs livrés d'office : schema.sql est un DDL, il n'apporte pas de données
    cid = uuid7()
    s.add(Comm(comm_id=cid, type="email", date_recue=datetime.now(timezone.utc),
               date_ingestion=datetime.now(timezone.utc), sens="in", nature="humain",
               from_adresse="x@y.fr", taille=1, nb_pieces_jointes=0, est_chiffre=False, est_signe=False))
    r = Rattachement(comm_id=cid, boite_id=b.boite_id, status="new", personnel=False, gele=False,
                     dossier_id=d.dossier_id, uid_imap=7)
    s.add(r); s.commit()
    return b, d, r, comptes


def test_la_descendante_impute_au_membre_qui_releve(base):
    """Un `\\Seen` chez le fournisseur devient l'ouverture DE QUELQU'UN — le seul membre de la boîte."""
    from atombox.schema.modeles import ReadState
    s, _ = base
    b, d, r, (m,) = _boite_avec(s, membres=1)
    assert appliquer_descendante(s, r, ["\\Seen"]) == ["lu"]
    s.commit()
    etat = s.get(ReadState, (m.compte_id, r.comm_id, r.boite_id))
    assert etat is not None and etat.opened_at is not None, "l'ouverture est portée par la personne"
    assert appliquer_descendante(s, r, ["\\Seen"]) == [], "rien de neuf : rien à dire (le cas courant)"


def test_un_seen_retire_ne_detruit_plus_la_trace(base):
    """LE DÉFAUT QUE D175 CORRIGE, éprouvé de bout en bout : avant, retirer `\\Seen` remettait
    `lu_le` à NULL et l'on perdait la seule preuve que quelqu'un avait regardé le message. La
    contre-épreuve est simple — si `opened_at` bougeait, ce test rougirait."""
    from atombox.schema.modeles import Marker, MarkerPersonal, ReadState
    s, _ = base
    b, d, r, (m,) = _boite_avec(s, membres=1)
    appliquer_descendante(s, r, ["\\Seen"]); s.commit()
    ouvert_le = s.get(ReadState, (m.compte_id, r.comm_id, r.boite_id)).opened_at
    assert ouvert_le is not None

    assert appliquer_descendante(s, r, []) == ["à revoir"], "on ne dé-lit pas : on dit « à revoir »"
    s.commit()
    assert s.get(ReadState, (m.compte_id, r.comm_id, r.boite_id)).opened_at == ouvert_le, \
        "un FAIT ne s'efface pas, même quand le fournisseur retire son drapeau (D175 § 1)"
    marqueur = s.scalar(__import__("sqlalchemy").select(Marker).where(Marker.code == "to_review"))
    assert s.get(MarkerPersonal, (m.compte_id, r.comm_id, r.boite_id, marqueur.marker_id)) is not None, \
        "l'intention est écrite là où elle vit : dans la table creuse des marqueurs"


def test_une_boite_a_plusieurs_n_impute_a_personne(base):
    """Le fournisseur n'a qu'un jeu de drapeaux : il ne dit pas QUI a lu. Écrire « les trois ont
    ouvert » serait un faux fait, et un faux fait ne se distingue plus d'un vrai. On s'abstient."""
    from atombox.schema.modeles import ReadState
    from sqlalchemy import func, select
    s, _ = base
    b, d, r, comptes = _boite_avec(s, membres=3)
    assert appliquer_descendante(s, r, ["\\Seen"]) == [], "à plusieurs, on ne choisit pas"
    s.commit()
    assert s.scalar(select(func.count()).select_from(ReadState)) == 0


def test_la_descendante_n_ecrase_pas_un_etat_en_vol(base):
    """Le défaut vu en production le 8 septembre : marquer lu dans AtomBox, redémarrer, et tout
    redevenait non lu — la relève lisait des FLAGS qui ne portaient pas encore notre \\Seen.

    Depuis D175 le symptôme a changé de forme : ce n'est plus `lu_le` qui retombait à NULL, c'est
    un « à revoir » qui se posait tout seul. La garde, elle, est la même, et c'est elle qu'on teste."""
    from sqlalchemy import select
    from atombox.ingestion.demon import synchroniser_descendante
    from atombox.modules import evenements
    from atombox.schema.modeles import Evenement, Marker, MarkerPersonal, ReadState
    from atombox.services import personal_state as perso
    s, _ = base
    b, d, r, (m,) = _boite_avec(s, membres=1)
    s.execute(perso.open_stmt(m.compte_id, r.comm_id, r.boite_id)); s.commit()   # lu dans AtomBox
    marqueur = s.scalar(select(Marker).where(Marker.code == "to_review"))
    cle = (m.compte_id, r.comm_id, r.boite_id, marqueur.marker_id)

    class FausseReleve:
        def drapeaux(self, uids): return {u: [] for u in uids}      # IMAP ne porte PAS encore \Seen

    # sans ordre en vol : IMAP fait foi, et « il faut y retourner » se pose
    synchroniser_descendante(s, FausseReleve(), b.boite_id, "boite@exemple.fr", d)
    s.commit()
    assert s.get(MarkerPersonal, cle) is not None, "sans ordre en attente, IMAP fait foi (D140b)"

    s.delete(s.get(MarkerPersonal, cle)); s.commit()
    evenements.emettre(s, "rattachement.change", {"comm_id": str(r.comm_id), "boite_id": str(b.boite_id)})
    s.commit()
    synchroniser_descendante(s, FausseReleve(), b.boite_id, "boite@exemple.fr", d)
    s.commit()
    assert s.get(MarkerPersonal, cle) is None, \
        "un ordre en vol protège l'état local — c'était le bug du 8 septembre"

    ev = s.scalar(select(Evenement).where(Evenement.type == "rattachement.change"))
    ev.traite_le = datetime.now(timezone.utc); s.commit()
    synchroniser_descendante(s, FausseReleve(), b.boite_id, "boite@exemple.fr", d)
    s.commit()
    assert s.get(MarkerPersonal, cle) is not None, "une fois l'ordre parti, IMAP redevient la vérité"
    assert s.get(ReadState, (m.compte_id, r.comm_id, r.boite_id)).opened_at is not None, \
        "et dans tous les cas, l'ouverture reste écrite"
