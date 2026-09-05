"""F114 — le schéma est fidèle au dictionnaire, et il s'applique.

Sans base : la syntaxe (pglast, le parseur de PostgreSQL) et la fidélité — une table par
entité du dictionnaire, chaque champ une colonne, chaque référence à cible connue une clé
étrangère. Avec DATABASE_URL (un rôle qui peut créer une base) : une base jetable reçoit le
schéma, on compte ce qui existe, on la détruit."""
import os, re, json, uuid, subprocess, pytest, yaml

ICI = os.path.dirname(os.path.abspath(__file__))
SERVEUR = os.path.join(ICI, "..")
SCHEMA = os.path.join(SERVEUR, "atombox", "schema", "schema.sql")
MANIFEST = os.path.join(SERVEUR, "atombox", "schema", "manifest.json")

def trouver_dict():
    d = os.path.abspath(SERVEUR)
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs", "dict")
        if os.path.isdir(c): return c
        d = os.path.dirname(d)
    return os.environ.get("CDC_DIR") and os.path.join(os.environ["CDC_DIR"], "dict")

@pytest.fixture(scope="module")
def sql(): return open(SCHEMA, encoding="utf-8").read()

@pytest.fixture(scope="module")
def manifest(): return json.load(open(MANIFEST, encoding="utf-8"))

@pytest.fixture(scope="module")
def dico():
    d = trouver_dict()
    if not d: pytest.skip("dictionnaire introuvable (.mmi-pm/docs/dict)")
    lire = lambda n: yaml.safe_load(open(os.path.join(d, n + ".yml"), encoding="utf-8"))
    return {"entites": lire("entites"), "champs": lire("champs"), "relations": lire("relations")}

def test_le_schema_se_parse(sql):
    pglast = pytest.importorskip("pglast")
    pglast.parse_sql(sql)   # lève si PostgreSQL ne l'accepterait pas

def test_une_table_par_entite(sql, manifest, dico):
    entites = [e["id"] for e in dico["entites"]]
    for e in entites:
        assert e in manifest["tables"], "entité sans table : " + e
        assert re.search(r'CREATE TABLE "%s" \(' % e, sql), e
    assert len(manifest["tables"]) == len(entites)

def test_chaque_champ_une_colonne(manifest, dico):
    for ent, champs in dico["champs"].items():
        cols = {c["nom"] for c in manifest["tables"][ent]["colonnes"]}
        manquent = [c["nom"] for c in champs if c["nom"] not in cols]
        assert not manquent, "%s : colonnes manquantes %s" % (ent, manquent)
        assert len(cols) == len(champs), ent

def test_chaque_table_a_une_cle(manifest, sql):
    for ent, t in manifest["tables"].items():
        assert t["cle"], ent
        assert ('CONSTRAINT "pk_%s" PRIMARY KEY' % ent) in sql, ent

def test_les_references_sont_des_cles_etrangeres(sql, manifest, dico):
    ent_ids = {e["id"] for e in dico["entites"]}
    attendues = 0
    for ent, champs in dico["champs"].items():
        cle = manifest["tables"][ent]["cle"]
        for c in champs:
            if c["type"] not in ("ref", "empreinte"): continue
            cible = c.get("vers") if "vers" in c else (re.fullmatch(r"(\w+)_id", c["nom"]) or [None, None])[1]
            if cible is None or cible not in ent_ids: continue   # une auto-référence (thread_id, parent_id) est une clé aussi
            # une fille 1-0..1 (comm_email → comm) référence par sa propre clé : c'est une clé étrangère aussi
            attendues += 1
            assert ('CONSTRAINT "fk_%s_%s" FOREIGN KEY' % (ent, c["nom"])) in sql, "%s.%s → %s" % (ent, c["nom"], cible)
    assert manifest["fks"] == attendues

def test_le_rapport_du_generateur_est_vide(manifest):
    """un champ ref sans cible, une entité sans clé, une relation sans porteur : le générateur
    le dit, et le test refuse — le dictionnaire se corrige, le schéma ne se devine pas"""
    assert manifest["rapport"] == [], "\n".join(manifest["rapport"])

def test_comm_porte_le_canal_et_son_check(sql):
    assert re.search(r'"ck_comm_type" CHECK \("type" IN \(\'email\'', sql)
    assert '"comm_id" uuid NOT NULL' in sql

@pytest.fixture(scope="module")
def base_jetable():
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent : pas de base pour appliquer le schéma")
    psycopg = pytest.importorskip("psycopg")
    nom = "atombox_test_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True)
    admin.execute('CREATE DATABASE "%s"' % nom)
    base = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    yield base
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()

def test_le_schema_s_applique(base_jetable, sql, manifest):
    import psycopg
    with psycopg.connect(base_jetable) as cnx:
        cnx.execute(sql)
        n = cnx.execute("select count(*) from information_schema.tables where table_schema='public'").fetchone()[0]
        assert n == len(manifest["tables"])
        fk = cnx.execute("select count(*) from information_schema.table_constraints where constraint_type='FOREIGN KEY'").fetchone()[0]
        assert fk == manifest["fks"]
        # une ligne dans comm : les colonnes obligatoires et le check du canal
        cnx.execute("insert into comm (comm_id, type, date_recue, date_ingestion, sens, nature, from_adresse, taille, nb_pieces_jointes, est_chiffre, est_signe) values (gen_random_uuid(), 'email', now(), now(), 'in', 'humain', 'a@b.fr', 1, 0, false, false)")
        with pytest.raises(psycopg.errors.CheckViolation):
            cnx.execute("insert into comm (comm_id, type, date_recue, date_ingestion, sens, nature, from_adresse, taille, nb_pieces_jointes, est_chiffre, est_signe) values (gen_random_uuid(), 'fax', now(), now(), 'in', 'humain', 'a@b.fr', 1, 0, false, false)")
