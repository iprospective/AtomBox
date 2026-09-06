"""Les trois contrôleurs (referentiels, arborescence, messages) — sans base : la sérialisation, le contrat, la
résolution des dossiers ; avec DATABASE_URL : le parcours complet du webmail contre le vrai serveur."""
import os, re, uuid, pytest
from datetime import datetime, timezone
from atombox.services import messages as svc

def test_dossiers_speciaux_par_alias():
    from atombox.schema.modeles import Dossier
    assert svc.special_de("INBOX") == "inbox" and svc.special_de("Sent") == "sent" and svc.special_de("Junk") == "junk" and svc.special_de("Corbeille") == "trash"
    d = Dossier(dossier_id=uuid.uuid4(), nom="Devis", alias_imap="Devis"); assert svc.dossier_id_court(d) == str(d.dossier_id)
    assert svc.dossier_id_court(Dossier(dossier_id=uuid.uuid4(), nom="INBOX", alias_imap="INBOX")) == "inbox"

def test_serialisation_porte_le_contrat():
    from atombox.schema.modeles import Comm, Rattachement, Dossier
    did = uuid.uuid4(); inbox = Dossier(dossier_id=did, nom="INBOX", alias_imap="INBOX"); trash = Dossier(dossier_id=uuid.uuid4(), nom="Trash", alias_imap="Trash")
    ds = {did: inbox, trash.dossier_id: trash}
    c = Comm(comm_id=uuid.uuid4(), sujet="Devis 12", from_nom="Jean", from_adresse="jean@x.fr", date_recue=datetime(2026, 9, 4, 9, 12, tzinfo=timezone.utc), thread_id=None, nb_pieces_jointes=1, taille=2048, sens="in", nature="humain", snippet="Bonjour")
    r = Rattachement(comm_id=c.comm_id, boite_id=uuid.uuid4(), lu_le=None, statut="nouveau", dossier_id=trash.dossier_id, dossier_origine_id=did, motif_sortie=None)
    o = svc.serialiser(r, c, ds, "contact@exemple.fr")
    assert o["id"] == str(c.comm_id) and o["date_recue"] == "2026-09-04T09:12:00+00:00" and o["lu"] is False
    assert o["dossier_origine"] == "inbox" and o["dossier"] == "trash", "déplacé en corbeille : origine gardée (D088)"
    for k in ("sujet", "from_nom", "from_adresse", "date_recue", "thread_id", "nb_pieces_jointes", "taille", "sorti_le", "motif_sortie", "dossier_origine", "destinataires", "reponse_possible", "list_id", "lu", "sens", "nature", "snippet", "boite", "dossier", "statut", "tags"):
        assert k in o, k

def test_quand_accepte_ms_et_iso():
    assert svc.quand(1756976400000).year == 2025 or svc.quand(1756976400000).year == 2026
    assert svc.quand("2026-09-04T09:12:00Z").tzinfo is not None and svc.quand(None) is None

def test_le_contrat_couvre_ce_que_le_webmail_appelle():
    from atombox.api.app import creer_app
    app = creer_app(); b = app.state.contrat
    assert b["hors_contrat"] == [] and b["couvertes"] >= 10, b
    ecrites = {(m, c) for m, c, _ in app.state.table}
    for m, c in (("GET", "/referentiels"), ("GET", "/arborescence"), ("GET", "/messages"), ("GET", "/messages/{id}"),
                 ("GET", "/messages/{id}/fil"), ("PATCH", "/messages/{id}/rattachement"), ("DELETE", "/messages/{id}/rattachement"), ("POST", "/messages")):
        assert (m, c) in ecrites, (m, c)

# ---- avec une base : le parcours complet du webmail ----------------------------------------
F = os.path.join(os.path.dirname(__file__), "fixtures")
def lire(n): return open(os.path.join(F, n), "rb").read()

@pytest.fixture(scope="module")
def monde(tmp_path_factory):
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    import psycopg
    from atombox.db import session as ouvrir
    from atombox.schema.modeles import Acces, Boite, Compte, Dossier
    from atombox.ingestion.ingestion import adresse, ingerer
    from atombox.api.securite import hacher_mot_de_passe
    from atombox.magasin import Magasin
    from atombox.uuid7 import uuid7
    nom = "atombox_test_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c: c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    os.environ["DATABASE_URL"] = u; os.environ["ATOMBOX_MAGASIN"] = str(tmp_path_factory.mktemp("magasin"))
    s = ouvrir(u); m = Magasin(os.environ["ATOMBOX_MAGASIN"])
    a = adresse(s, "contact@exemple.fr")
    boite = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(boite)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True, cree_le=datetime.now(timezone.utc), mot_de_passe_empreinte=hacher_mot_de_passe("secret")); s.add(compte)
    s.add(Acces(compte_id=compte.compte_id, boite_id=boite.boite_id, role="lecteur", debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
    inbox = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(inbox)
    for alias in ("Sent", "Drafts", "Trash", "Junk"): s.add(Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=alias, alias_imap=alias, protege=True))
    s.commit()
    ids = [ingerer(s, m, boite.boite_id, lire(f), dossier_id=inbox.dossier_id)["comm_id"] for f in ("simple.eml", "reponse.eml", "pieces.eml", "liste.eml")]
    yield {"session": s, "ids": ids, "url": u}
    s.close(); admin.execute('DROP DATABASE "%s"' % nom); admin.close()

def test_parcours_du_webmail(monde):
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    import atombox.db as db; db._async.clear(); db._sync.clear()
    c = TestClient(creer_app())
    r = c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"}); assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["jeton"]}
    ref = c.get("/api/v1/referentiels", headers=h).json()
    assert ref["moi"]["boites"][0]["adresse"] == "contact@exemple.fr" and [x["id"] for x in ref["speciaux"]][:2] == ["inbox", "sent"] and ref["axes"] == []
    arbo = c.get("/api/v1/arborescence", headers=h).json()
    assert arbo["compteurs"]["inbox"]["t"] == 4 and arbo["compteurs"]["inbox"]["u"] == 4
    l = c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=h).json()
    assert l["total"] == 4 and l["messages"][0]["date_recue"].startswith("2026-09-04T") and l["messages"][0]["lu"] is False
    assert c.get("/api/v1/messages", params={"dossier": "inbox", "filtre": "pj"}, headers=h).json()["total"] == 1
    mid = str(monde["ids"][2])
    d = c.get("/api/v1/messages/" + mid, headers=h).json()
    assert d["corps"].startswith("Veuillez") and len(d["pieces_jointes"]) == 3 and d["pieces_jointes"][1]["mime_detecte"] == "application/pdf"
    fil = c.get("/api/v1/messages/%s/fil" % monde["ids"][1], headers=h).json()["messages"]
    assert len(fil) == 2, "simple et sa réponse forment un fil (D055)"
    p = c.patch("/api/v1/messages/" + mid + "/rattachement", json={"lu": True}, headers=h).json()
    assert p["ok"] and p["modifies"] == 1 and p["message"]["lu"] is True
    assert c.get("/api/v1/arborescence", headers=h).json()["compteurs"]["inbox"]["u"] == 3
    p = c.patch("/api/v1/messages/" + mid + "/rattachement", json={"dossier": "trash"}, headers=h).json()
    assert p["message"]["dossier"] == "trash" and p["message"]["dossier_origine"] == "inbox"
    assert c.get("/api/v1/messages", params={"dossier": "trash"}, headers=h).json()["total"] == 1
    p = c.patch("/api/v1/messages/" + mid + "/rattachement", json={"dossier": None}, headers=h).json(); assert p["message"]["dossier"] is None
    p = c.patch("/api/v1/messages/" + str(monde["ids"][3]) + "/rattachement", json={"motif_sortie": "archive", "sorti_le": 1757000000000}, headers=h).json()
    assert p["message"]["motif_sortie"] == "archive" and c.get("/api/v1/messages", params={"dossier": "archives"}, headers=h).json()["total"] == 1
    n = c.post("/api/v1/messages", json={"boite": "contact@exemple.fr", "destinataires": ["jean@x.fr"], "sujet": "Test", "corps": "Bonjour", "composition": None}, headers=h).json()
    assert n["ok"] and n["crees"] == 1 and n["message"]["sens"] == "out" and n["message"]["dossier_origine"] == "sent"
    assert c.get("/api/v1/messages", params={"dossier": "sent"}, headers=h).json()["total"] == 1
    assert c.delete("/api/v1/messages/" + mid + "/rattachement", headers=h).json()["detache"]
    assert c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=h).json()["total"] == 2
    assert c.get("/api/v1/messages/" + str(uuid.uuid4()), headers=h).status_code == 404
    assert c.get("/api/v1/messages", headers={}).status_code == 401
