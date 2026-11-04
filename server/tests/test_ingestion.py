"""F001 + F002 dans une base jetable, par l'ORM : déduplication, rattachements, pièces, fil. Sans DATABASE_URL : sauté."""
import os, re, uuid, pytest
from sqlalchemy import select, func
from atombox.store import Store
from atombox.uuid7 import uuid7

F = os.path.join(os.path.dirname(__file__), "fixtures")
def read(n): return open(os.path.join(F, n), "rb").read()

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
    s.close()
    import atombox.db as db; db.engine(u).dispose(); db._sync.clear()   # sinon la base est « in use » à la destruction
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()

@pytest.fixture
def boites(base):
    from atombox.ingestion.ingestion import address_of
    from atombox.schema.models import Boite
    out = []
    for adr in ("contact@exemple.fr", "fred@exemple.fr"):
        a = address_of(base, adr)
        b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="personnelle")
        base.add(b); out.append(b.boite_id)
    base.commit(); return out

def test_ingestion_complete(base, boites, tmp_path):
    from atombox.ingestion.ingestion import ingest
    from atombox.schema.models import Comm, Rattachement, PieceJointe, CommPieceJointe
    m = Store(str(tmp_path))
    r1 = ingest(base, m, boites[0], read("simple.eml"), uid=12, uid_validity=1)
    assert r1["nouveau"] and r1["nature"] == "humain"
    assert m.exists(str(r1["comm_id"])), "le message brut est au magasin sous l'UUID de la comm (D145)"
    r2 = ingest(base, m, boites[1], read("simple-relivre.eml"), uid=3, uid_validity=1)
    assert not r2["nouveau"] and r2["comm_id"] == r1["comm_id"], "la seconde livraison ne fait qu'un rattachement (D010)"
    assert base.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.comm_id == r1["comm_id"])) == 2
    assert base.scalar(select(func.count()).select_from(Comm)) == 1
    r3 = ingest(base, m, boites[0], read("reponse.eml"))
    assert base.get(Comm, r3["comm_id"]).thread_id == r1["comm_id"], "la réponse rejoint le fil (D055)"
    r4 = ingest(base, m, boites[0], read("pieces.eml"))
    assert r4["pieces"] == 3
    assert base.scalar(select(func.count()).select_from(PieceJointe)) == 2, "deux fichiers identiques → une pièce jointe (D011)"
    assert base.scalar(select(PieceJointe).where(PieceJointe.type_detecte == "application/pdf")).nb_references == 2
    assert base.scalar(select(func.count()).select_from(CommPieceJointe).where(CommPieceJointe.comm_id == r4["comm_id"])) == 3
    assert base.get(Comm, ingest(base, m, boites[0], read("liste.eml"))["comm_id"]).nature == "liste"

def test_message_stocke_en_squelette_sans_doublon_du_brut(base, boites, tmp_path):
    """RM3631 (D208, D209) : le brut n'est plus écrit deux fois ; les pièces, décodées, sont les blobs des
    pièces jointes ; le message se relit à l'octet par son UUID."""
    from atombox.ingestion.ingestion import ingest
    from atombox.schema.models import Blob, CommEmail, CommPieceJointe, PieceJointe
    m = Store(str(tmp_path)); raw = read("pieces.eml").replace(b"Subject: ", b"Subject: [RM3631] ", 1)
    r = ingest(base, m, boites[0], raw, uid=40, uid_validity=1)
    cid = r["comm_id"]
    e = base.get(CommEmail, cid)
    assert m.read_message(str(cid)) == raw, "reconstitué à l'octet"
    assert not m.exists(e.blob_ref), "plus de second exemplaire du brut sous son empreinte"
    b = base.get(Blob, e.blob_ref)
    assert b.compression in ("squelette", "squelette-brut") and b.taille_octets == len(raw)
    pjs = {p.blob_ref for p in base.scalars(select(PieceJointe).join(CommPieceJointe, CommPieceJointe.piece_jointe_id == PieceJointe.piece_jointe_id)
                                                     .where(CommPieceJointe.comm_id == cid))}
    from atombox.store import skeleton as Sq
    man, sq = Sq.read_container(m.read(str(cid)))
    assert b.compression == "squelette" and man["segments"], "la fixture a des pièces base64 : elles sortent du squelette"
    assert {s["b"] for s in man["segments"] if s["m"] == "b64"} <= pjs | {s["b"] for s in man["segments"]}
    assert {s["b"] for s in man["segments"] if s["m"] == "b64"} & pjs, "une pièce du squelette EST le blob de la pièce jointe (D011)"
    assert len(sq) < len(raw)

def test_migration_de_l_existant_en_squelette(base, boites, tmp_path):
    """RM3631 : un message écrit À L'ANCIENNE (brut sous l'UUID ET sous l'empreinte) est réécrit en squelette ;
    à blanc rien ne bouge ; appliqué, le second exemplaire disparaît et l'octet reste."""
    from atombox.ingestion.ingestion import ingest
    from atombox.schema.models import Blob, CommEmail
    from atombox.store.migrate import migrate
    m = Store(str(tmp_path)); raw = read("pieces.eml").replace(b"Subject: ", b"Subject: [migration] ", 1)
    cid = ingest(base, m, boites[0], raw, uid=41, uid_validity=1)["comm_id"]
    e = base.get(CommEmail, cid)
    m.write(str(cid), raw, replace=True); m.put(raw)          # l'état d'avant RM3631
    b = base.get(Blob, e.blob_ref); b.compression = "zstd"; base.commit()
    blanc = migrate(base, m, apply=False)
    assert m.exists(e.blob_ref) and m.read(str(cid)) == raw, "à blanc : rien n'est touché"
    assert blanc["apres"] < blanc["avant"], "le gain est mesuré"
    r = migrate(base, m, apply=True)
    assert r["migres"] == 1 and str(cid) not in dict(r["ignores"])
    assert not m.exists(e.blob_ref), "le second exemplaire du brut est effacé"
    assert m.read_message(str(cid)) == raw, "l'octet est intact"
    base.refresh(b); assert b.compression == "squelette"
    assert migrate(base, m, apply=True)["migres"] == 0, "rejouer ne refait rien"
