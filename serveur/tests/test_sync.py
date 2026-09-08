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

def test_la_descendante_n_ecrase_pas_un_etat_en_vol(monkeypatch, tmp_path):
    """Le défaut vu en production le 8 septembre : marquer lu dans AtomBox, redémarrer, et tout
    redevenait non lu — la relève lisait des FLAGS qui ne portaient pas encore notre \\Seen."""
    import os, re as _re, uuid as _uuid
    if not os.environ.get("DATABASE_URL"): pytest.skip("DATABASE_URL absent")
    import psycopg
    from datetime import datetime, timezone
    from sqlalchemy import select
    from atombox.db import session as ouvrir
    from atombox.ingestion.demon import synchroniser_descendante
    from atombox.modules import evenements
    from atombox.schema.modeles import Adresse, Boite, Dossier, Evenement
    from atombox.ingestion.ingestion import adresse as adresse_de
    from atombox.uuid7 import uuid7

    nom = "atombox_sync_" + _uuid.uuid4().hex[:8]
    admin = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = _re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", os.environ["DATABASE_URL"], count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c: c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    s = ouvrir(u)
    try:
        a = adresse_de(s, "boite@exemple.fr")
        b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="personnelle"); s.add(b)
        d = Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(d)
        from atombox.schema.modeles import Comm
        cid = uuid7()
        s.add(Comm(comm_id=cid, type="email", date_recue=datetime.now(timezone.utc), date_ingestion=datetime.now(timezone.utc),
                   sens="in", nature="humain", from_adresse="x@y.fr", taille=1, nb_pieces_jointes=0, est_chiffre=False, est_signe=False))
        r = Rattachement(comm_id=cid, boite_id=b.boite_id, drapeau=False, statut="nouveau", personnel=False, gele=False,
                         dossier_id=d.dossier_id, uid_imap=7, lu_le=datetime.now(timezone.utc))   # lu dans AtomBox
        s.add(r); s.commit()

        class FausseReleve:
            def drapeaux(self, uids): return {u: [] for u in uids}      # IMAP ne porte PAS encore \Seen
        # sans ordre en vol : IMAP fait foi, le message redevient non lu
        synchroniser_descendante(s, FausseReleve(), b.boite_id, "boite@exemple.fr", d)
        assert r.lu_le is None, "sans ordre en attente, IMAP fait foi (D140b)"

        r.lu_le = datetime.now(timezone.utc)
        evenements.emettre(s, "rattachement.change", {"comm_id": str(cid), "boite_id": str(b.boite_id)})
        s.commit()
        synchroniser_descendante(s, FausseReleve(), b.boite_id, "boite@exemple.fr", d)
        assert r.lu_le is not None, "un ordre en vol protège l'état local — c'était le bug du 8 septembre"

        ev = s.scalar(select(Evenement).where(Evenement.type == "rattachement.change"))
        ev.traite_le = datetime.now(timezone.utc); s.commit()
        synchroniser_descendante(s, FausseReleve(), b.boite_id, "boite@exemple.fr", d)
        assert r.lu_le is None, "une fois l'ordre parti, IMAP redevient la vérité"
    finally:
        s.close()
        import atombox.db as db; db.moteur(u).dispose(); db._sync.clear()
        admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
        admin.execute('DROP DATABASE "%s"' % nom); admin.close()
