"""LES APPLICATIONS CONNECTÉES (F048 — D019, D108 ; RM3517).

Le module Dolibarr appelle l'API avec un jeton d'APPLICATION : il lit dans sa portée (un domaine),
étiquette sur ses axes déclarés, et rien d'autre. Chaque règle a sa contre-épreuve : hors portée,
axe d'autrui, route d'écriture, jeton révoqué."""
import os, re, uuid, pytest
from datetime import datetime, timezone

F = os.path.join(os.path.dirname(__file__), "fixtures")
def read(n): return open(os.path.join(F, n), "rb").read()


@pytest.fixture(scope="module")
def monde(tmp_path_factory):
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    import psycopg
    from atombox.db import session as ouvrir
    from atombox.schema.models import Acces, Boite, Compte, Dossier
    from atombox.ingestion.ingestion import address_of, ingest
    from atombox.api.security import hash_password
    from atombox.store import Store
    from atombox.uuid7 import uuid7
    from atombox.schema.seeds import seed_builtins
    from atombox.services.mailbox import ensure_mailboxes
    from atombox import settings, applications
    nom = "atombox_test_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c: c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    coupees = ["ATOMBOX_IMAP_HOST"]; coupees += [v for k, v in settings.FORMER_NAMES.items() if k in coupees]
    before = {k: os.environ.get(k) for k in ["DATABASE_URL", "ATOMBOX_STORE"] + coupees}
    for k in coupees: os.environ.pop(k, None)
    os.environ["DATABASE_URL"] = u; os.environ["ATOMBOX_STORE"] = str(tmp_path_factory.mktemp("magasin"))
    s = ouvrir(u); m = Store(os.environ["ATOMBOX_STORE"])
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True, cree_le=datetime.now(timezone.utc),
                    mot_de_passe_empreinte=hash_password("secret")); s.add(compte)
    seed_builtins(s)
    ids = {}
    for adresse, fichier in (("contact@exemple.fr", "simple.eml"), ("ventes@ailleurs.example", "pieces.eml")):
        a = address_of(s, adresse)
        b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(b)
        s.add(Acces(compte_id=compte.compte_id, boite_id=b.boite_id, role="lecteur", debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
        inbox = Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(inbox)
        for alias in ("Sent", "Drafts", "Trash", "Junk"): s.add(Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom=alias, alias_imap=alias, protege=True))
        s.flush(); ensure_mailboxes(s, b.boite_id); s.commit()
        ids[adresse] = str(ingest(s, m, b.boite_id, read(fichier), dossier_id=inbox.dossier_id)["comm_id"])
    s.commit()
    app, jeton = applications.create(s, "dolibarr-demo", "dolibarr", domaines=["exemple.fr"], axes=["propal", "commande"])
    yield {"session": s, "ids": ids, "jeton": jeton, "app": app}
    s.close()
    for k, v in before.items():
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    import atombox.db as db, asyncio
    db.engine(u).dispose(); db._sync.clear()
    for x in list(db._async.values()):
        try: asyncio.run(x.dispose())
        except Exception: pass
    db._async.clear()
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()


@pytest.fixture(scope="module")
def api(monde):
    from fastapi.testclient import TestClient
    from atombox.api.app import create_app
    import atombox.db as db; db._async.clear(); db._sync.clear()
    c = TestClient(create_app())
    humain = {"Authorization": "Bearer " + c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"}).json()["jeton"]}
    appli = {"Authorization": "Bearer " + monde["jeton"]}
    return c, humain, appli


def test_le_jeton_n_est_garde_que_par_son_empreinte(monde):
    from sqlalchemy import select, text
    from atombox.schema.models import Application
    assert monde["jeton"].startswith("abxapp_")
    s = monde["session"]
    dump = " ".join(str(v) for v in s.execute(text("select * from application")).one())
    assert monde["jeton"] not in dump, "le jeton en clair ne doit être nulle part en base"


def test_l_application_lit_dans_sa_portee_seulement(api, monde):
    c, humain, appli = api
    l = c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=appli).json()
    assert {m["boite"] for m in l["messages"]} == {"contact@exemple.fr"}, "sa portée : le domaine exemple.fr"
    assert c.get("/api/v1/messages/" + monde["ids"]["contact@exemple.fr"], headers=appli).status_code == 200
    # contre-épreuve : la personne voit les deux boîtes, l'application une seule
    assert len(c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=humain).json()["messages"]) == 2
    assert c.get("/api/v1/messages/" + monde["ids"]["ventes@ailleurs.example"], headers=appli).status_code == 404, \
        "hors portée = 404, jamais 403 (D108)"


def test_l_application_etiquette_sur_ses_axes(api, monde):
    c, humain, appli = api
    cid = monde["ids"]["contact@exemple.fr"]
    r = c.post("/api/v1/messages/%s/tags" % cid, json={"axe": "propal", "val": "123"}, headers=appli)
    assert r.status_code == 200 and ("propal", "123", "dolibarr") in [(x["axe"], x["val"], x["source"]) for x in r.json()["tags"]], r.text
    # contre-épreuves : un axe qu'elle ne déclare pas, un message hors portée
    assert c.post("/api/v1/messages/%s/tags" % cid, json={"axe": "client", "val": "9"}, headers=appli).status_code == 404
    hors = monde["ids"]["ventes@ailleurs.example"]
    assert c.post("/api/v1/messages/%s/tags" % hors, json={"axe": "propal", "val": "123"}, headers=appli).status_code == 404
    # une personne garde le geste « rattacher à… » sur l'axe de l'application (D187 § 2)
    r = c.post("/api/v1/messages/%s/tags" % cid, json={"axe": "propal", "val": "124"}, headers=humain)
    assert ("propal", "124", "manuel") in [(x["axe"], x["val"], x["source"]) for x in r.json()["tags"]]
    # et l'application retire le sien
    assert c.delete("/api/v1/messages/%s/tags/propal=123" % cid, headers=appli).status_code == 200


def test_les_routes_d_ecriture_restent_aux_personnes(api, monde):
    c, humain, appli = api
    cid = monde["ids"]["contact@exemple.fr"]
    assert c.patch("/api/v1/messages/%s/rattachement" % cid, json={"motif_sortie": "archived"}, headers=appli).status_code == 401
    assert c.post("/api/v1/messages", json={"boite": "contact@exemple.fr", "a": "x@y.fr", "sujet": "s"}, headers=appli).status_code == 401
    assert c.delete("/api/v1/messages/%s/rattachement" % cid, headers=appli).status_code == 401
    assert c.get("/api/v1/arborescence", headers=appli).status_code == 401


def test_le_dernier_appel_se_voit_et_la_revocation_coupe(api, monde):
    c, humain, appli = api
    from atombox import applications
    from atombox.schema.models import Application
    s = monde["session"]; s.expire_all()
    assert s.get(Application, monde["app"].application_id).dernier_appel is not None
    assert applications.revoke(s, "dolibarr-demo")
    assert c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=appli).status_code == 401
    assert c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=humain).status_code == 200


def test_les_echanges_d_un_tiers_par_ses_adresses(api, monde):
    """D108, RM3523 — l'onglet « Échanges » d'une fiche tiers : tout le courrier avec ses adresses, dans
    les deux sens, quel que soit le dossier ; jamais tout quand la liste est vide"""
    from atombox.ingestion.ingestion import ingest
    from atombox.schema.models import Dossier
    from atombox.store import Store
    from sqlalchemy import select
    c, humain, appli = api
    s = monde["session"]
    inbox = s.scalar(select(Dossier).where(Dossier.alias_imap == "INBOX").order_by(Dossier.boite_id).limit(1))
    ingest(s, Store(os.environ["ATOMBOX_STORE"]), inbox.boite_id, read("reponse.eml"), dossier_id=inbox.dossier_id)
    def sujets(**p):
        r = c.get("/api/v1/messages", params=dict({"dossier": "tous", "filtre": "tous"}, **p), headers=humain)
        assert r.status_code == 200, r.text
        return sorted(m["sujet"] for m in r.json()["messages"])
    tessier = sujets(adresses="Jean.Tessier@tessier-industries.example")
    assert len(tessier) == 2, "reçu de lui ET envoyé à lui : %s" % tessier
    assert sujets(adresses="personne@nulle-part.example") == []
    assert sujets(adresses="") == [], "une liste vide ne montre rien, jamais tout"
    assert len(sujets(adresses="jean.tessier@tessier-industries.example,compta@fournisseur.example")) == 3
