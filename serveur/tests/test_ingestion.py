"""F001 + F002 dans une base jetable, par l'ORM : déduplication, rattachements, pièces, fil. Sans DATABASE_URL : sauté."""
import os, re, uuid, pytest
from sqlalchemy import select, func
from atombox.magasin import Magasin
from atombox.uuid7 import uuid7

F = os.path.join(os.path.dirname(__file__), "fixtures")
def lire(n): return open(os.path.join(F, n), "rb").read()

@pytest.fixture(scope="module")
def base():
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    psycopg = pytest.importorskip("psycopg")
    from atombox.db import session
    nom = "atombox_test_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c: c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    s = session(u)
    yield s
    s.close(); admin.execute('DROP DATABASE "%s"' % nom); admin.close()

@pytest.fixture
def boites(base):
    from atombox.ingestion.ingestion import adresse
    from atombox.schema.modeles import Boite
    out = []
    for adr in ("contact@exemple.fr", "fred@exemple.fr"):
        a = adresse(base, adr)
        b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="personnelle")
        base.add(b); out.append(b.boite_id)
    base.commit(); return out

def test_ingestion_complete(base, boites, tmp_path):
    from atombox.ingestion.ingestion import ingerer
    from atombox.schema.modeles import Comm, Rattachement, PieceJointe, CommPieceJointe
    m = Magasin(str(tmp_path))
    r1 = ingerer(base, m, boites[0], lire("simple.eml"), uid=12, uid_validity=1)
    assert r1["nouveau"] and r1["nature"] == "humain"
    assert m.existe(str(r1["comm_id"])), "le message brut est au magasin sous l'UUID de la comm (D145)"
    r2 = ingerer(base, m, boites[1], lire("simple-relivre.eml"), uid=3, uid_validity=1)
    assert not r2["nouveau"] and r2["comm_id"] == r1["comm_id"], "la seconde livraison ne fait qu'un rattachement (D010)"
    assert base.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.comm_id == r1["comm_id"])) == 2
    assert base.scalar(select(func.count()).select_from(Comm)) == 1
    r3 = ingerer(base, m, boites[0], lire("reponse.eml"))
    assert base.get(Comm, r3["comm_id"]).thread_id == r1["comm_id"], "la réponse rejoint le fil (D055)"
    r4 = ingerer(base, m, boites[0], lire("pieces.eml"))
    assert r4["pieces"] == 3
    assert base.scalar(select(func.count()).select_from(PieceJointe)) == 2, "deux fichiers identiques → une pièce jointe (D011)"
    assert base.scalar(select(PieceJointe).where(PieceJointe.type_detecte == "application/pdf")).nb_references == 2
    assert base.scalar(select(func.count()).select_from(CommPieceJointe).where(CommPieceJointe.comm_id == r4["comm_id"])) == 3
    assert base.get(Comm, ingerer(base, m, boites[0], lire("liste.eml"))["comm_id"]).nature == "liste"
