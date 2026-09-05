"""F001 + F002 dans une base jetable : déduplication, rattachements, pièces, fil. Sans DATABASE_URL : sauté."""
import os, re, uuid, pytest
from atombox.magasin import Magasin
from atombox.uuid7 import uuid7

F = os.path.join(os.path.dirname(__file__), "fixtures")
def lire(n): return open(os.path.join(F, n), "rb").read()

@pytest.fixture(scope="module")
def base():
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    nom = "atombox_test_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    cnx = psycopg.connect(u, row_factory=dict_row)
    ici = os.path.dirname(os.path.abspath(__file__))
    cnx.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); cnx.commit()
    yield cnx
    cnx.close(); admin.execute('DROP DATABASE "%s"' % nom); admin.close()

@pytest.fixture
def boites(base):
    from atombox.ingestion.ingestion import _adresse_id
    out = []
    for adr in ("contact@exemple.fr", "fred@exemple.fr"):
        cur = base.cursor(); aid = _adresse_id(cur, adr)
        dom = cur.execute("select domaine_id from adresse where adresse_id=%s", (aid,)).fetchone()["domaine_id"]
        bid = uuid7(); cur.execute("insert into boite (boite_id, adresse_id, domaine_id, type) values (%s,%s,%s,'personnelle')", (bid, aid, dom))
        out.append(bid)
    base.commit(); return out

def test_ingestion_complete(base, boites, tmp_path):
    from atombox.ingestion.ingestion import ingerer
    m = Magasin(str(tmp_path))
    r1 = ingerer(base, m, boites[0], lire("simple.eml"), uid=12, uid_validity=1)
    assert r1["nouveau"] and r1["nature"] == "humain"
    assert m.existe(str(r1["comm_id"])), "le message brut est au magasin sous l'UUID de la comm (D145)"
    r2 = ingerer(base, m, boites[1], lire("simple-relivre.eml"), uid=3, uid_validity=1)
    assert not r2["nouveau"] and r2["comm_id"] == r1["comm_id"], "la seconde livraison ne fait qu'un rattachement (D010)"
    assert base.execute("select count(*) n from rattachement where comm_id=%s", (r1["comm_id"],)).fetchone()["n"] == 2
    assert base.execute("select count(*) n from comm").fetchone()["n"] == 1
    r3 = ingerer(base, m, boites[0], lire("reponse.eml"))
    t = base.execute("select thread_id from comm where comm_id=%s", (r3["comm_id"],)).fetchone()["thread_id"]
    assert t == r1["comm_id"], "la réponse rejoint le fil (D055)"
    r4 = ingerer(base, m, boites[0], lire("pieces.eml"))
    assert r4["pieces"] == 3
    pj = base.execute("select count(*) n from piece_jointe").fetchone()["n"]
    assert pj == 2, "deux fichiers identiques → une pièce jointe (D011)"
    assert base.execute("select nb_references from piece_jointe where type_detecte='application/pdf'").fetchone()["nb_references"] == 2
    assert base.execute("select count(*) n from comm_piece_jointe where comm_id=%s", (r4["comm_id"],)).fetchone()["n"] == 3
    assert base.execute("select nature from comm where comm_id=%s", (ingerer(base, m, boites[0], lire("liste.eml"))["comm_id"],)).fetchone()["nature"] == "liste"
