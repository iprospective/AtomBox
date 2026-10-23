"""LA BOÎTE DE CHAQUE MESSAGE, VISIBLE ET FILTRABLE (F147 — D176 § 3 et 4, RM3514).

Un compte, deux boîtes à lui, une troisième qui n'est pas à lui. Le filtre en amont (`boites=`)
restreint la liste, la recherche ET les compteurs de dossiers — un filtre sur la liste seule
rouvrirait l'écart que D166 interdit. Le compteur de chaque boîte est « non traité / total »,
et il ne dépend pas des cases cochées."""
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
    from atombox import settings
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
    boites = {}
    for adresse, a_moi in (("contact@exemple.fr", True), ("ventes@exemple.fr", True), ("autre@exemple.fr", False)):
        a = address_of(s, adresse)
        b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(b)
        if a_moi:
            s.add(Acces(compte_id=compte.compte_id, boite_id=b.boite_id, role="lecteur", debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
        inbox = Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(inbox)
        sent = Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="Sent", alias_imap="Sent", protege=True); s.add(sent)
        for alias in ("Drafts", "Trash", "Junk"): s.add(Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom=alias, alias_imap=alias, protege=True))
        s.flush(); ensure_mailboxes(s, b.boite_id)
        boites[adresse] = (b.boite_id, inbox.dossier_id, sent.dossier_id)
    s.commit()
    c_, ci, _ = boites["contact@exemple.fr"]; v_, vi, vs = boites["ventes@exemple.fr"]; a_, ai, _ = boites["autre@exemple.fr"]
    ids = {"contact": [ingest(s, m, c_, read(f), dossier_id=ci)["comm_id"] for f in ("simple.eml", "reponse.eml")],
           "ventes": [ingest(s, m, v_, read("pieces.eml"), dossier_id=vi)["comm_id"]],
           "ventes_out": [ingest(s, m, v_, read("liste.eml"), dossier_id=vs, sens="out")["comm_id"]],
           "autre": [ingest(s, m, a_, read("liste.eml"), dossier_id=ai)["comm_id"]]}
    s.commit()
    yield {"session": s, "boites": {k: str(v[0]) for k, v in boites.items()}, "ids": ids}
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
    jeton = c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"}).json()["jeton"]
    h = {"Authorization": "Bearer " + jeton}
    get = lambda chemin, **p: c.get("/api/v1" + chemin, params=p, headers=h).json()
    return get, c, h


def _boites(l): return sorted({m["boite"] for m in l["messages"]})


def test_chaque_ligne_porte_sa_boite(api, monde):
    get, *_ = api
    l = get("/messages", dossier="inbox")
    assert l["total"] == 3 and _boites(l) == ["contact@exemple.fr", "ventes@exemple.fr"]
    assert {b["adresse"] for b in get("/referentiels")["moi"]["boites"]} == {"contact@exemple.fr", "ventes@exemple.fr"}


def test_le_filtre_restreint_la_liste_et_les_compteurs(api, monde):
    get, *_ = api
    b = monde["boites"]
    tout = get("/arborescence")
    assert tout["compteurs"]["inbox"]["t"] == 3

    l = get("/messages", dossier="inbox", boites=b["contact@exemple.fr"])
    assert l["total"] == 2 and _boites(l) == ["contact@exemple.fr"]
    arbo = get("/arborescence", boites=b["contact@exemple.fr"])
    assert arbo["compteurs"]["inbox"]["t"] == 2, "le compteur dit ce que la liste montre (D166)"
    assert "sent" not in arbo["compteurs"], "l'envoyé de ventes@ ne se compte plus"

    deux = ",".join([b["contact@exemple.fr"], b["ventes@exemple.fr"]])
    assert get("/messages", dossier="inbox", boites=deux)["total"] == 3
    assert get("/arborescence", boites=deux)["compteurs"]["inbox"]["t"] == 3


def test_le_compteur_de_boite_est_non_traite_sur_total(api, monde):
    get, c, h = api
    b = monde["boites"]
    par_boite = get("/arborescence")["boites"]
    assert set(par_boite) == {b["contact@exemple.fr"], b["ventes@exemple.fr"]}, "une boîte sans accès n'a pas de compteur"
    assert par_boite[b["contact@exemple.fr"]] == {"t": 2, "n": 2, "u": 2}
    # ventes@ : un reçu en file, un envoyé — l'envoyé est dans le total, il n'attend rien
    assert par_boite[b["ventes@exemple.fr"]]["t"] == 2 and par_boite[b["ventes@exemple.fr"]]["n"] == 1

    # traiter : sort de « non traité », reste dans le total ; archiver : sort des deux
    cid = str(monde["ids"]["contact"][0]); cid2 = str(monde["ids"]["contact"][1])
    assert c.patch("/api/v1/messages/" + cid + "/rattachement", json={"motif_sortie": "processed"}, headers=h).json()["ok"]
    assert c.patch("/api/v1/messages/" + cid2 + "/rattachement", json={"motif_sortie": "archived"}, headers=h).json()["ok"]
    x = get("/arborescence")["boites"][b["contact@exemple.fr"]]
    assert (x["t"], x["n"]) == (1, 0), x
    # indépendant des cases cochées : décocher contact@ ne l'efface pas de son propre compteur
    assert get("/arborescence", boites=b["ventes@exemple.fr"])["boites"][b["contact@exemple.fr"]] == x


def test_une_boite_sans_acces_citee_dans_l_url_est_ignoree(api, monde):
    """la contre-épreuve : le paramètre ne doit jamais ÉLARGIR la portée"""
    get, *_ = api
    b = monde["boites"]
    assert get("/messages", dossier="inbox", boites=b["autre@exemple.fr"])["total"] == 0
    assert get("/arborescence", boites=b["autre@exemple.fr"])["compteurs"] == {}
    mixte = get("/messages", dossier="inbox", boites=b["contact@exemple.fr"] + "," + b["autre@exemple.fr"] + ",pas-un-uuid")
    assert _boites(mixte) in ([], ["contact@exemple.fr"]) and "autre@exemple.fr" not in _boites(mixte)
    assert get("/recherche", q="liste", boites=b["autre@exemple.fr"])["total"] == 0
