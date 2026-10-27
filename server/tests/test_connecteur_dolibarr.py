"""LE CONNECTEUR DOLIBARR (D187, RM3518) — la réponse d'un client à un envoi Dolibarr arrive
étiquetée sur l'objet, sans geste humain ; le module pousse ses libellés ; rien d'un autre Dolibarr.

Les Message-ID sont ceux que Dolibarr écrit (CMailFile) : `<temps>.SMTPs-dolibarr-<trackid>@<hôte>`,
où le trackid est le code d'objet suivi de son id (`pro123`, `proj12`, `sinv7`…)."""
import os, re, uuid, pytest
from datetime import datetime, timezone

HOTE = "doli.exemple.fr"


def courrier(sujet, message_id, in_reply_to=None, references=None, de="client@tiers.example", a="contact@exemple.fr"):
    h = ["From: %s" % de, "To: %s" % a, "Subject: %s" % sujet, "Date: Fri, 23 Oct 2026 10:00:00 +0200",
         "Message-ID: <%s>" % message_id]
    if in_reply_to: h.append("In-Reply-To: <%s>" % in_reply_to)
    if references: h.append("References: " + " ".join("<%s>" % r for r in references))
    return ("\r\n".join(h + ["Content-Type: text/plain; charset=utf-8", "", "corps de %s" % sujet, ""])).encode()


@pytest.fixture(scope="module")
def monde(tmp_path_factory):
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    import psycopg
    from atombox.db import session as ouvrir
    from atombox.schema.models import Acces, Boite, Compte, Dossier
    from atombox.ingestion.ingestion import address_of
    from atombox.api.security import hash_password
    from atombox.uuid7 import uuid7
    from atombox.schema.seeds import seed_builtins
    from atombox.services.mailbox import ensure_mailboxes
    from atombox.store import Store
    from atombox import settings, applications
    from atombox.connectors import declaration
    nom = "atombox_test_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c: c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    coupees = ["ATOMBOX_IMAP_HOST"]; coupees += [v for k, v in settings.FORMER_NAMES.items() if k in coupees]
    before = {k: os.environ.get(k) for k in ["DATABASE_URL", "ATOMBOX_STORE"] + coupees}
    for k in coupees: os.environ.pop(k, None)
    os.environ["DATABASE_URL"] = u; os.environ["ATOMBOX_STORE"] = str(tmp_path_factory.mktemp("magasin"))
    s = ouvrir(u)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True, cree_le=datetime.now(timezone.utc),
                    mot_de_passe_empreinte=hash_password("secret")); s.add(compte)
    seed_builtins(s)
    inbox = {}
    for adresse in ("contact@exemple.fr", "ventes@ailleurs.example"):
        a = address_of(s, adresse)
        b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(b)
        s.add(Acces(compte_id=compte.compte_id, boite_id=b.boite_id, role="lecteur", debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
        d = Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(d)
        for alias in ("Sent", "Drafts", "Trash", "Junk"): s.add(Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom=alias, alias_imap=alias, protege=True))
        s.flush(); ensure_mailboxes(s, b.boite_id); s.commit()
        inbox[adresse] = (b.boite_id, d.dossier_id)
    axes = list(declaration("dolibarr")["axes"])
    app, jeton = applications.create(s, "dolibarr-demo", "dolibarr", domaines=["exemple.fr"], axes=axes, parametres={"hotes": [HOTE]})
    yield {"session": s, "store": Store(os.environ["ATOMBOX_STORE"]), "inbox": inbox, "jeton": jeton, "app": app}
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


def recevoir(monde, raw, boite="contact@exemple.fr", sens=None):
    from atombox.ingestion.ingestion import ingest
    b, d = monde["inbox"][boite]
    kw = {"sens": sens} if sens else {}
    return str(ingest(monde["session"], monde["store"], b, raw, dossier_id=d, **kw)["comm_id"])


def tags(monde, cid):
    import asyncio
    from atombox.services.tags import tags_of
    from atombox.db import async_session_factory
    async def lire():
        async with async_session_factory()() as s: return (await tags_of(s, [uuid.UUID(cid)])).get(uuid.UUID(cid), [])
    return {(t["axe"], t["val"]) for t in asyncio.run(lire())}


@pytest.fixture(scope="module")
def api(monde):
    from fastapi.testclient import TestClient
    from atombox.api.app import create_app
    import atombox.db as db; db._async.clear(); db._sync.clear()
    c = TestClient(create_app())
    humain = {"Authorization": "Bearer " + c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"}).json()["jeton"]}
    return c, humain, {"Authorization": "Bearer " + monde["jeton"]}


def test_la_reponse_du_client_arrive_etiquetee(monde):
    envoi = "1761206400.SMTPs-dolibarr-pro123@" + HOTE
    cid = recevoir(monde, courrier("Re: Votre proposition PR2610-0012", "abc@tiers.example", in_reply_to=envoi, references=[envoi]))
    assert tags(monde, cid) == {("propal", "123")}


def test_chaque_code_va_a_son_axe(monde):
    """`pro` et `proj` partagent un préfixe : `proj12` est le projet 12, pas la proposition « j12 »"""
    refs = ["1.SMTPs-dolibarr-proj12@" + HOTE, "2.swiftmailer-dolibarr-sinv7@" + HOTE, "3.phpmail-dolibarr-sord8@" + HOTE,
            "4.SMTPs-dolibarr-ord5@" + HOTE, "5.SMTPs-dolibarr-inv45@" + HOTE]
    cid = recevoir(monde, courrier("Re: plusieurs objets", "def@tiers.example", references=refs))
    assert tags(monde, cid) == {("projet", "12"), ("facture_fournisseur", "7"), ("commande_fournisseur", "8"),
                                ("commande", "5"), ("facture", "45")}


def test_un_autre_dolibarr_ne_pose_rien(monde):
    """la contre-épreuve de D187 § 3 : la facture 45 d'un fournisseur sous Dolibarr n'est pas la nôtre"""
    cid = recevoir(monde, courrier("Votre facture", "1.SMTPs-dolibarr-inv45@dolibarr.fournisseur.example", de="compta@fournisseur.example"))
    assert tags(monde, cid) == set()


def test_hors_de_la_portee_rien_n_est_pose(monde):
    envoi = "9.SMTPs-dolibarr-pro123@" + HOTE
    cid = recevoir(monde, courrier("Re: hors portée", "ghi@tiers.example", in_reply_to=envoi, a="ventes@ailleurs.example"),
                   boite="ventes@ailleurs.example")
    assert tags(monde, cid) == set(), "ventes@ailleurs.example n'est pas dans la portée de l'application"


def test_le_module_pousse_ses_libelles(api, monde):
    c, humain, appli = api
    moi = c.get("/api/v1/application", headers=appli).json()
    assert moi["type"] == "dolibarr" and {"id": "propal", "libelle": "Propositions commerciales"} in moi["axes"]
    r = c.put("/api/v1/axes/propal/valeurs", json={"valeurs": [{"valeur": "123", "libelle": "PR2610-0012 — Tiers SA"},
                                                              {"valeur": "124", "libelle": "PR2610-0013 — Autre"}]}, headers=appli)
    assert r.json() == {"ok": True, "crees": 1, "modifies": 1}, "123 existait (posé par la règle), 124 est neuf"
    l = c.get("/api/v1/messages", params={"dossier": "propal:123"}, headers=appli).json()["messages"]
    assert len(l) == 1 and [t["libelle"] for t in l[0]["tags"] if t["axe"] == "propal"] == ["PR2610-0012 — Tiers SA"]
    # contre-épreuves : un axe qui n'est pas le sien, une personne sur une route d'application
    assert c.put("/api/v1/axes/client/valeurs", json={"valeurs": []}, headers=appli).status_code == 404
    assert c.get("/api/v1/application", headers=humain).status_code == 404


def test_les_hotes_se_declarent_et_l_historique_se_rattrape(api, monde):
    c, humain, appli = api
    from atombox import applications
    envoi = "7.SMTPs-dolibarr-pro200@doli2.exemple.fr"
    cid = recevoir(monde, courrier("Re: avant la déclaration", "jkl@tiers.example", in_reply_to=envoi))
    assert tags(monde, cid) == set(), "hôte pas encore déclaré"
    r = c.patch("/api/v1/application", json={"hotes": [HOTE, "doli2.exemple.fr"]}, headers=appli)
    assert r.json()["parametres"]["hotes"] == ["doli.exemple.fr", "doli2.exemple.fr"]
    assert c.patch("/api/v1/application", json={"hotes": "pas une liste"}, headers=appli).status_code == 422
    s = monde["session"]; s.expire_all()
    assert applications.rescan(s, "dolibarr-demo") >= 1
    assert tags(monde, cid) == {("propal", "200")}
    assert applications.rescan(s, "dolibarr-demo") == 0, "idempotent"


def test_le_webmail_recoit_libelles_et_cles(api, monde):
    """RM3519 — la navigation et la complétion lisent le LIBELLÉ, et posent la CLÉ"""
    c, humain, appli = api
    ref = c.get("/api/v1/referentiels", headers=humain).json()
    assert {"id": "propal", "label": "Propositions commerciales", "derive": False, "famille": "dolibarr", "lien": None} in ref["axes"]
    v = [x for x in ref["valeurs"]["propal"] if x["val"] == "123"]
    assert v == [{"id": "propal:123", "label": "PR2610-0012 — Tiers SA", "val": "123", "axe": "propal"}], v
    # un axe posé à la main, sans application, garde un nom lisible
    cid = c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=humain).json()["messages"][0]["id"]
    c.post("/api/v1/messages/%s/tags" % cid, json={"axe": "dossier_client", "val": "x"}, headers=humain)
    assert {"id": "dossier_client", "label": "Dossier client", "derive": False, "famille": None, "lien": None} in c.get("/api/v1/referentiels", headers=humain).json()["axes"]



def test_la_famille_range_les_axes(api, monde):
    """D188 — une famille, plusieurs axes ; un axe dans une famille au plus ; configurable par axe"""
    c, humain, appli = api
    ref = c.get("/api/v1/referentiels", headers=humain).json()
    assert {"id": "dolibarr", "label": "Dolibarr"} in ref["familles"]
    dolibarr = sorted(a["id"] for a in ref["axes"] if a["famille"] == "dolibarr")
    assert dolibarr == ["commande", "commande_fournisseur", "facture", "facture_fournisseur", "projet", "propal", "tiers"], \
        "le connecteur range ses sept axes dans sa famille (le tiers depuis D189)"
    # ranger à la main un axe sans famille, avec un libellé ; puis l'en sortir
    r = c.patch("/api/v1/axes/dossier_client", json={"famille": "interne", "famille_libelle": "Suivi interne"}, headers=humain)
    assert r.json() == {"ok": True, "axe": "dossier_client", "famille": "interne"}
    ref = c.get("/api/v1/referentiels", headers=humain).json()
    assert {"id": "interne", "label": "Suivi interne"} in ref["familles"]
    assert [a["famille"] for a in ref["axes"] if a["id"] == "dossier_client"] == ["interne"]
    c.patch("/api/v1/axes/dossier_client", json={"famille": None}, headers=humain)
    assert [a["famille"] for a in c.get("/api/v1/referentiels", headers=humain).json()["axes"] if a["id"] == "dossier_client"] == [None]
    # contre-épreuves : axe inconnu, corps sans famille, et une application ne range pas
    assert c.patch("/api/v1/axes/inconnu", json={"famille": "x"}, headers=humain).status_code == 404
    assert c.patch("/api/v1/axes/propal", json={}, headers=humain).status_code == 422
    assert c.patch("/api/v1/axes/propal", json={"famille": "x"}, headers=appli).status_code == 401



# ---- D189 : le tiers devient un axe, posé par une règle d'adresse (RM3547) --------------------------

def _tiers(api, *valeurs):
    c, humain, appli = api
    r = c.put("/api/v1/axes/tiers/valeurs", json={"valeurs": list(valeurs)}, headers=appli)
    assert r.status_code == 200, r.text
    return r.json()


def test_le_message_d_un_contact_se_range_sur_son_tiers(api, monde):
    _tiers(api, {"valeur": "7", "libelle": "Tessier Industries", "adresses": ["Jean.Tessier@tessier.example", "compta@tessier.example"]})
    recu = recevoir(monde, courrier("Question", "t1@tessier.example", de="jean.tessier@tessier.example"))
    assert ("tiers", "7") in tags(monde, recu), "reçu d'un contact du tiers"
    envoye = recevoir(monde, courrier("Réponse", "t2@exemple.fr", de="contact@exemple.fr", a="compta@tessier.example"), sens="out")
    assert ("tiers", "7") in tags(monde, envoye), "un envoi se range chez celui à qui il est adressé"
    inconnu = recevoir(monde, courrier("Bonjour", "t3@nouveau.example", de="quelquun@nouveau.example"))
    assert not [t for t in tags(monde, inconnu) if t[0] == "tiers"], "l'inconnu n'a pas de tiers"


def test_une_adresse_partagee_donne_deux_tiers(api, monde):
    _tiers(api, {"valeur": "8", "libelle": "Atelier A", "adresses": ["cabinet@expert.example"]},
                {"valeur": "9", "libelle": "Atelier B", "adresses": ["cabinet@expert.example"]})
    cid = recevoir(monde, courrier("Bilans", "t4@expert.example", de="cabinet@expert.example"))
    assert {("tiers", "8"), ("tiers", "9")} <= tags(monde, cid), "multi-classement (D017)"


def test_hors_portee_la_regle_d_adresse_ne_pose_rien(api, monde):
    cid = recevoir(monde, courrier("Ailleurs", "t5@tessier.example", de="jean.tessier@tessier.example", a="ventes@ailleurs.example"),
                   boite="ventes@ailleurs.example")
    assert not [t for t in tags(monde, cid) if t[0] == "tiers"]


def test_le_tiers_cree_apres_coup_range_son_historique(api, monde):
    from atombox import applications
    cid = recevoir(monde, courrier("Premier contact", "t6@neuf.example", de="direction@neuf.example"))
    assert not [t for t in tags(monde, cid) if t[0] == "tiers"]
    _tiers(api, {"valeur": "10", "libelle": "Neuf SARL", "adresses": ["direction@neuf.example"]})
    s = monde["session"]; s.expire_all()
    assert applications.rescan(s, "dolibarr-demo") >= 1
    assert ("tiers", "10") in tags(monde, cid)


def test_le_webmail_sait_ou_creer_un_inconnu(api, monde):
    c, humain, appli = api
    assert c.get("/api/v1/referentiels", headers=humain).json()["applications"] == [], "sans adresse déclarée : pas de lien cassé"
    assert c.patch("/api/v1/application", json={"url": "pas une url"}, headers=appli).status_code == 422
    assert c.patch("/api/v1/application", json={"url": "https://doli.exemple.fr/"}, headers=appli).status_code == 200
    (app,) = c.get("/api/v1/referentiels", headers=humain).json()["applications"]
    assert app["axe_tiers"] == "tiers" and app["url"] == "https://doli.exemple.fr"
    assert app["creation"]["tiers"].startswith("https://doli.exemple.fr/societe/card.php?action=create&name={nom}")
    assert "{adresse}" in app["creation"]["contact"]


def test_une_application_ancienne_recoit_les_axes_nouveaux(monde):
    """l'application de mmi est née avec les six axes de D187 ; l'axe tiers (D189) lui manque"""
    from atombox import applications
    from atombox.schema.models import Application
    from sqlalchemy import select
    s = monde["session"]; s.expire_all()
    app = s.scalar(select(Application).where(Application.nom == "dolibarr-demo"))
    app.axes = [a for a in app.axes if a != "tiers"]; s.commit()
    assert applications.declare_axes(s, "dolibarr-demo") == ["tiers"]
    assert "tiers" in s.scalar(select(Application).where(Application.nom == "dolibarr-demo")).axes
    assert applications.declare_axes(s, "dolibarr-demo") == [], "idempotent"


def test_les_tags_renvoient_aux_fiches_dolibarr(api, monde):
    """F149 (RM3546) — une fois l'adresse de Dolibarr déclarée, chaque axe de l'application porte le
    modèle de sa fiche ; un axe sans application (posé à la main) n'en porte pas"""
    c, humain, appli = api
    c.patch("/api/v1/application", json={"url": "https://doli.exemple.fr"}, headers=appli)
    liens = {a["id"]: a["lien"] for a in c.get("/api/v1/referentiels", headers=humain).json()["axes"]}
    assert liens["propal"] == "https://doli.exemple.fr/comm/propal/card.php?id={id}"
    assert liens["tiers"] == "https://doli.exemple.fr/societe/card.php?socid={id}"
    assert liens["facture"] == "https://doli.exemple.fr/compta/facture/card.php?facid={id}"
    assert liens["dossier_client"] is None


# ---- F148 : la session déléguée et le cadre (RM3545) ------------------------------------------------

def test_la_session_deleguee(api, monde):
    from datetime import datetime, timezone
    from atombox import applications
    from atombox.api.security import hash_password
    from atombox.schema.models import Compte, Session as SessionModele
    from atombox.uuid7 import uuid7
    from sqlalchemy import select
    c, humain, appli = api
    s = monde["session"]
    ouvrir = lambda login, h=appli: c.post("/api/v1/application/sessions", json={"login": login}, headers=h)
    assert ouvrir("mathieu").status_code == 404, "non délégué : le compte n'existe pas pour l'application (D108)"
    applications.delegate(s, "dolibarr-demo", "mathieu")
    r = ouvrir("mathieu")
    assert r.status_code == 200 and r.json()["compte"] == "mathieu", r.text
    jeton = r.json()["jeton"]
    assert c.get("/api/v1/referentiels", headers={"Authorization": "Bearer " + jeton}).json()["moi"]["login"] == "mathieu"
    s.expire_all()
    assert s.scalar(select(SessionModele.agent).order_by(SessionModele.cree_le.desc()).limit(1)) == "délégation:dolibarr-demo"
    # contre-épreuves : un compte délégué SANS boîte dans la portée ; une personne à la place de l'application
    s.add(Compte(compte_id=uuid7(), login="intrus", nom="Intrus", actif=True, cree_le=datetime.now(timezone.utc),
                 mot_de_passe_empreinte=hash_password("x"))); s.commit()
    applications.delegate(s, "dolibarr-demo", "intrus")
    assert ouvrir("intrus").status_code == 404, "délégué mais hors portée : refusé"
    assert ouvrir("mathieu", humain).status_code == 404, "une session n'est pas une application"
    applications.delegate(s, "dolibarr-demo", "mathieu", retirer=True)
    assert ouvrir("mathieu").status_code == 404, "la délégation retirée coupe"
    applications.delegate(s, "dolibarr-demo", "mathieu")


def test_seuls_atombox_et_les_applications_deleguees_encadrent_le_webmail(api, monde):
    from atombox import applications
    c, humain, appli = api
    applications.delegate(monde["session"], "dolibarr-demo", "mathieu")      # autonome : ne compte sur aucun test d'avant
    c.patch("/api/v1/application", json={"url": "https://doli.exemple.fr/sous/chemin"}, headers=appli)
    r = c.get("/")
    if r.status_code == 404: pytest.skip("webmail non servi dans ce harnais")
    csp = r.headers.get("content-security-policy", "")
    assert csp.startswith("frame-ancestors 'self'"), csp
    assert "https://doli.exemple.fr" in csp and "/sous/chemin" not in csp, "l'ORIGINE, pas le chemin : %s" % csp
    assert "content-security-policy" not in {k.lower() for k in c.get("/api/v1/referentiels", headers=humain).headers}, \
        "l'API n'en a pas besoin"
