"""La FILE des migrations mène au schéma courant : chaque colonne de manifest.json est dans la
copie figée 0001 ou ajoutée par une révision postérieure. Sans base, par lecture des fichiers."""
import os, re, json, glob

ICI = os.path.dirname(os.path.abspath(__file__))
VERS = os.path.join(ICI, "..", "atombox", "schema", "migrations", "versions")

def test_toutes_les_colonnes_sont_migrees():
    manifest = json.load(open(os.path.join(ICI, "..", "atombox", "schema", "manifest.json"), encoding="utf-8"))
    fige = open(os.path.join(VERS, "0001_schema.sql"), encoding="utf-8").read()
    ajouts = "\n".join(open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(VERS, "0*.py"))))
    manquent = []
    for table, t in manifest["tables"].items():
        m = re.search(r'CREATE TABLE "%s" \((.*?)\n\)' % table, fige + "\n" + ajouts, re.S)
        colonnes_figees = set(re.findall(r'^\s*"(\w+)" ', m.group(1), re.M)) if m else set()
        for c in t["colonnes"]:
            # Une colonne peut aussi apparaître par RENOMMAGE (`statut` → `status`, migration 0011) :
            # sans ce troisième motif, une migration correcte était rapportée comme manquante — et le
            # contrôle poussait à ajouter la colonne une seconde fois pour faire taire le test.
            if c["nom"] not in colonnes_figees and not re.search(r'ALTER TABLE "%s" ADD COLUMN "%s"' % (table, c["nom"]), ajouts) \
               and not re.search(r'ADD COLUMN "%s"[^;]*' % c["nom"], ajouts) \
               and not re.search(r'RENAME COLUMN "\w+" TO "%s"' % c["nom"], ajouts):
                manquent.append(table + "." + c["nom"])
    assert not manquent, "colonnes du schéma courant sans migration : " + ", ".join(manquent)

def test_les_revisions_se_suivent():
    revs = {}
    for f in sorted(glob.glob(os.path.join(VERS, "0*.py"))):
        s = open(f, encoding="utf-8").read()
        revs[re.search(r'^revision = "(\w+)"', s, re.M).group(1)] = re.search(r'^down_revision = (None|"(\w+)")', s, re.M).group(2)
    assert list(revs)[0] and revs[list(revs)[0]] is None
    for i, r in enumerate(list(revs)[1:], 1): assert revs[r] == list(revs)[i - 1], r


# ── la file des migrations s'APPLIQUE-t-elle vraiment ? ─────────────────────────────────────────
# Les deux tests ci-dessus LISENT les fichiers. Ils ne les exécutent pas, et c'est un angle mort qui
# a coûté : la reprise de 0011 appelait `min(compte_id)`, or PostgreSQL n'a pas de `min()` sur uuid.
# Tout était vert, parce que les bases de test sont montées de `schema.sql` — elles ne passent JAMAIS
# par les migrations. Trouvé en rejouant la migration sur une copie des données réelles.
#
# D'où ce test : on monte une base VIDE par la file complète, on y met des données AU CRAN D'AVANT,
# on applique la dernière, et on vérifie ce qu'elle a repris. C'est le seul endroit où le code de
# reprise est exécuté par le harnais.
import os, uuid as _uuid, pytest


def _alembic(url, cible):
    from alembic import command
    from alembic.config import Config
    avant = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    cfg = Config(os.path.join(ICI, "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ICI, "..", "atombox", "schema", "migrations"))
    try:
        if cible == "base": command.downgrade(cfg, "base")
        elif cible.startswith("-"): command.downgrade(cfg, cible[1:])
        else: command.upgrade(cfg, cible)
    finally:
        if avant is None: os.environ.pop("DATABASE_URL", None)
        else: os.environ["DATABASE_URL"] = avant


@pytest.fixture
def base_vide():
    if not os.environ.get("DATABASE_URL"): pytest.skip("DATABASE_URL absent")
    import psycopg, re as _re
    nom = "atombox_mig_" + _uuid.uuid4().hex[:8]
    admin = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    admin.execute('CREATE DATABASE "%s"' % nom)
    u = _re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", os.environ["DATABASE_URL"], count=1)
    try:
        yield u
    finally:
        admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
        admin.execute('DROP DATABASE "%s"' % nom); admin.close()


def test_la_file_s_applique_et_reprend_les_donnees(base_vide):
    """Toute la file, sur une base vide, puis la DERNIÈRE migration sur des données réalistes.

    Ce que ça prouve, et que la lecture des fichiers ne prouvait pas : le SQL de reprise s'exécute.
    Ce que ça garde : qu'un message de la Corbeille devienne `deleted`, un des Indésirables `junk`,
    qu'une lecture aille sur le SEUL membre de la boîte, et qu'une boîte à plusieurs n'impute rien."""
    import psycopg
    u = base_vide
    _alembic(u, "0010")                      # l'état d'avant : c'est là que vivent les données
    with psycopg.connect(u, autocommit=True) as c:
        c.execute("""
INSERT INTO domaine (domaine_id, nom_ascii, nom_unicode, heberge_par_nous)
VALUES ('11111111-0000-7000-8000-000000000001', 'exemple.fr', 'exemple.fr', true);
INSERT INTO adresse (adresse_id, local, local_cmp, domaine_id, adresse_complete)
VALUES ('11111111-0000-7000-8000-000000000002', 'boite', 'boite', '11111111-0000-7000-8000-000000000001', 'boite@exemple.fr'),
       ('11111111-0000-7000-8000-000000000012', 'part', 'part', '11111111-0000-7000-8000-000000000001', 'part@exemple.fr');
INSERT INTO compte (compte_id, login, nom, actif, cree_le)
VALUES ('11111111-0000-7000-8000-000000000003', 'seul', 'Seul', true, now()),
       ('11111111-0000-7000-8000-000000000013', 'deux', 'Deux', true, now());
INSERT INTO boite (boite_id, adresse_id, domaine_id, type)
VALUES ('11111111-0000-7000-8000-000000000004', '11111111-0000-7000-8000-000000000002', '11111111-0000-7000-8000-000000000001', 'personnelle'),
       ('11111111-0000-7000-8000-000000000014', '11111111-0000-7000-8000-000000000012', '11111111-0000-7000-8000-000000000001', 'partagee');
INSERT INTO acces (compte_id, boite_id, role, debut, accorde_par) VALUES
  ('11111111-0000-7000-8000-000000000003', '11111111-0000-7000-8000-000000000004', 'gestionnaire', now(), '11111111-0000-7000-8000-000000000003'),
  ('11111111-0000-7000-8000-000000000003', '11111111-0000-7000-8000-000000000014', 'membre', now(), '11111111-0000-7000-8000-000000000003'),
  ('11111111-0000-7000-8000-000000000013', '11111111-0000-7000-8000-000000000014', 'membre', now(), '11111111-0000-7000-8000-000000000013');
INSERT INTO dossier (dossier_id, boite_id, nom, alias_imap, protege) VALUES
  ('11111111-0000-7000-8000-000000000005', '11111111-0000-7000-8000-000000000004', 'INBOX', 'INBOX', true),
  ('11111111-0000-7000-8000-000000000006', '11111111-0000-7000-8000-000000000004', 'Corbeille', 'Trash', true),
  ('11111111-0000-7000-8000-000000000007', '11111111-0000-7000-8000-000000000004', 'Indésirables', 'Junk', true),
  ('11111111-0000-7000-8000-000000000017', '11111111-0000-7000-8000-000000000014', 'INBOX', 'INBOX', true);
INSERT INTO comm (comm_id, type, date_recue, date_ingestion, sens, nature, from_adresse, taille,
                  nb_pieces_jointes, est_chiffre, est_signe)
SELECT ('11111111-0000-7000-8000-00000000001' || n)::uuid, 'email', now(), now(), 'in', 'humain',
       'x@y.fr', 1, 0, false, false FROM generate_series(1, 5) n;
-- 1 : lu, dans l'INBOX d'une boîte à UN membre → la lecture doit lui être imputée
INSERT INTO rattachement (comm_id, boite_id, statut, personnel, gele, dossier_id, lu_le, drapeau, reveil_le)
VALUES ('11111111-0000-7000-8000-000000000011', '11111111-0000-7000-8000-000000000004', 'a_faire', false, false,
        '11111111-0000-7000-8000-000000000005', now() - interval '1 day', true, now() + interval '3 days'),
-- 2 : dans la Corbeille SANS motif de sortie → doit devenir `deleted`
       ('11111111-0000-7000-8000-000000000012', '11111111-0000-7000-8000-000000000004', 'nouveau', false, false,
        '11111111-0000-7000-8000-000000000006', null, false, null),
-- 3 : dans les Indésirables → doit devenir `junk`
       ('11111111-0000-7000-8000-000000000013', '11111111-0000-7000-8000-000000000004', 'nouveau', false, false,
        '11111111-0000-7000-8000-000000000007', null, false, null),
-- 4 : traité PUIS archivé avant la migration : une seule case portait la date. `processed_at` doit
--     être reconstitué depuis le statut, sinon l'archivage automatique (D014) n'a plus de clé
       ('11111111-0000-7000-8000-000000000014', '11111111-0000-7000-8000-000000000004', 'traite', false, false,
        '11111111-0000-7000-8000-000000000005', null, false, null),
-- 5 : lu sur une boîte à DEUX membres → on ne sait pas qui, donc on n'écrit rien
       ('11111111-0000-7000-8000-000000000015', '11111111-0000-7000-8000-000000000014', 'nouveau', false, false,
        '11111111-0000-7000-8000-000000000017', now(), false, null);
UPDATE rattachement SET motif_sortie = 'archive', sorti_le = now() - interval '400 days'
 WHERE comm_id = '11111111-0000-7000-8000-000000000014';
""")

    _alembic(u, "head")

    with psycopg.connect(u) as c:
        etat = dict(c.execute("select comm_id::text, exit_reason from rattachement").fetchall())
        assert etat["11111111-0000-7000-8000-000000000012"] == "deleted", \
            "un message de la Corbeille devient un ÉTAT, il ne reste pas un simple dossier"
        assert etat["11111111-0000-7000-8000-000000000013"] == "junk", \
            "Indésirables cesse d'être un dossier (D175 § 4)"
        assert etat["11111111-0000-7000-8000-000000000011"] is None, "l'INBOX, c'est l'absence d'état"

        (proc, arch) = c.execute("""select processed_at, archived_at from rattachement
                                     where comm_id = '11111111-0000-7000-8000-000000000014'""").fetchone()
        assert arch is not None and proc is not None, \
            "traité PUIS archivé : la date de traitement est reconstituée, c'est la clé d'archivage (D014)"

        lignes = dict(c.execute("select comm_id::text, compte_id::text from read_state").fetchall())
        assert lignes.get("11111111-0000-7000-8000-000000000011") == "11111111-0000-7000-8000-000000000003", \
            "la lecture va au SEUL membre de la boîte"
        assert "11111111-0000-7000-8000-000000000015" not in lignes, \
            "à plusieurs, l'ancien lu_le ne dit pas QUI : on n'écrit pas un fait qu'on n'a pas observé"

        assert c.execute("""select count(*) from marker_personal m join marker k using (marker_id)
                             where k.code = 'snooze'""").fetchone()[0] == 1, \
            "reveil_le devient un marqueur, et quitte le chemin chaud"
        assert c.execute("select count(*) from marker where integre").fetchone()[0] == 2, \
            "les deux marqueurs livrés d'office sont posés par la migration"

    # ET LE RETOUR : une migration qu'on ne sait pas défaire est une porte à sens unique.
    _alembic(u, "-0010")
    with psycopg.connect(u) as c:
        # UNE seule, pas deux : la lecture de la boîte à deux membres n'avait pas été écrite à la
        # montée, faute de savoir QUI. Le retour ne l'invente pas davantage. Une migration ne
        # restitue pas ce qu'elle a refusé d'inventer, et c'est le comportement qu'on veut garder.
        assert c.execute("select count(*) from rattachement where lu_le is not null").fetchone()[0] == 1, \
            "le retour recolle ce qu'il sait recoller, et rien de plus"
        assert c.execute("select count(*) from information_schema.tables where table_name = 'read_state'").fetchone()[0] == 0
