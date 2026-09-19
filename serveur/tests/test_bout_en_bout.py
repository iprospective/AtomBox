"""LES TESTS DE BOUT EN BOUT (RM3188) — trois histoires qui traversent tout, avec les VRAIS démons.

Les pièces sont testées, la chaîne ne l'était pas. Les cinq défauts du 15 septembre vivaient tous
ENTRE deux morceaux corrects : une route déclarée mais non écrite, une sérialisation qui rendait
`[]`, un compteur qui ne parlait pas à sa liste, un JSON `null` qui n'est pas un NULL SQL, un NOTIFY
jamais attendu. Aucun test unitaire ne pouvait les voir.

Ce qui tourne ici, pour de vrai :
  - le DÉMON D'INGESTION (`python -m atombox.ingestion.demon`), en sous-processus, contre un IMAP
    simulé (tests/doublures.py) — il relève, il se met en IDLE, il se réveille ;
  - le PROCESSUS DES TÂCHES (`python -m atombox.taches`), en sous-processus — il écoute NOTIFY,
    remet au relais SMTP simulé, pousse les états vers IMAP ;
  - l'API, dans le processus du test (TestClient) : c'est elle qu'on pilote comme le webmail.

LES DÉLAIS SONT DES ASSERTIONS. Le processus des tâches ne se réveille seul que toutes les 30 s
(`ATOMBOX_TACHES_PAS`), le démon ne sort d'IDLE seul que toutes les 30 s (`ATOMBOX_IDLE_SECONDES`).
Chaque attente ci-dessous est bien plus courte : si elle aboutit, c'est qu'un NOTIFY ou un IDLE a
réellement réveillé le bon processus. Un NOTIFY muet fait échouer le test au lieu de le ralentir.

Rapidité : une base jetable, deux sous-processus, aucune attente fixe — on sonde, on ne dort pas.
"""
import os, re, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path
import pytest
from doublures import FauxImap, FauxRelais

RACINE = Path(__file__).resolve().parent.parent
REVEIL = 6.0          # secondes : largement assez pour un NOTIFY ou un IDLE, cinq fois moins qu'un réveil spontané


def message(sujet: str, de: str = "Fournisseur <achats@fournisseur.example>", corps: str = "Bonjour,\r\nci-joint.\r\n",
            mid: str | None = None) -> bytes:
    mid = mid or "<%s@fournisseur.example>" % uuid.uuid4().hex
    return ("From: %s\r\nTo: contact@exemple.fr\r\nSubject: %s\r\nDate: Fri, 18 Sep 2026 10:00:00 +0200\r\n"
            "Message-ID: %s\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n%s"
            % (de, sujet, mid, corps)).encode()


class Chaine:
    """ce qu'une histoire manipule : l'API, les doublures, et de quoi attendre sans dormir"""

    def __init__(self, client, entetes, imap, relais, logs, procs):
        self.c, self.h, self.imap, self.relais, self.logs, self.procs = client, entetes, imap, relais, logs, procs

    def get(self, chemin, **p): return self.c.get("/api/v1" + chemin, params=p or None, headers=self.h)
    def post(self, chemin, corps): return self.c.post("/api/v1" + chemin, json=corps, headers=self.h)
    def patch(self, chemin, corps): return self.c.patch("/api/v1" + chemin, json=corps, headers=self.h)
    def delete(self, chemin): return self.c.delete("/api/v1" + chemin, headers=self.h)

    def journaux(self) -> str:
        out = []
        for nom, p in self.procs.items():
            etat = "vivant" if p.poll() is None else "MORT (code %s)" % p.returncode
            out.append("── %s : %s" % (nom, etat))
            f = self.logs / (nom + ".out")
            if f.exists(): out.append(f.read_text(errors="replace")[-3000:])
        f = self.logs / "erreurs.log"
        if f.exists(): out.append("── erreurs.log\n" + f.read_text(errors="replace")[-3000:])
        return "\n".join(out)

    def attendre(self, condition, quoi: str, delai: float = REVEIL):
        """sonde toutes les 50 ms ; échoue avec les journaux des démons, qui disent POURQUOI"""
        fin, derniere = time.monotonic() + delai, None
        while time.monotonic() < fin:
            for nom, p in self.procs.items():
                if p.poll() is not None: pytest.fail("le processus « %s » est mort en attendant : %s\n%s" % (nom, quoi, self.journaux()))
            try:
                derniere = condition()
                if derniere: return derniere
            except Exception as e:
                derniere = e
            time.sleep(0.05)
        pytest.fail("pas en %.0f s : %s (dernière valeur : %r)\n%s" % (delai, quoi, derniere, self.journaux()))

    def liste(self, dossier: str, **p) -> list[dict]:
        """comme le webmail (api.http.js) : un dossier virtuel s'ouvre avec kind=perso"""
        if dossier.startswith("perso:"): p.setdefault("kind", "perso")
        return self.get("/messages", dossier=dossier, **p).json()["messages"]

    def compteur(self, dossier: str) -> dict:
        return self.get("/arborescence").json()["compteurs"].get(dossier) or {}


@pytest.fixture(scope="module")
def chaine(tmp_path_factory):
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    import psycopg
    from atombox.db import session as ouvrir
    from atombox.schema.modeles import Acces, Boite, Compte, Dossier
    from atombox.ingestion.ingestion import adresse
    from atombox.api.securite import hacher_mot_de_passe
    from atombox.uuid7 import uuid7

    nom = "atombox_e2e_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    with psycopg.connect(u) as cnx:
        cnx.execute((RACINE / "atombox" / "schema" / "schema.sql").read_text(encoding="utf-8")); cnx.commit()
    magasin, logs = tmp_path_factory.mktemp("magasin"), tmp_path_factory.mktemp("journaux")

    # le monde : un compte, une boîte, ses dossiers — ce qu'un administrateur pose avant la première relève
    s = ouvrir(u)
    a = adresse(s, "contact@exemple.fr")
    boite = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(boite)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True, cree_le=datetime.now(timezone.utc),
                    mot_de_passe_empreinte=hacher_mot_de_passe("secret")); s.add(compte)
    s.add(Acces(compte_id=compte.compte_id, boite_id=boite.boite_id, role="lecteur", debut=datetime.now(timezone.utc),
                accorde_par=compte.compte_id))
    for alias in ("INBOX", "Sent", "Drafts", "Trash", "Junk"):
        s.add(Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=alias, alias_imap=alias, protege=True))
    s.commit(); s.close()

    imap, relais = FauxImap(), FauxRelais(); imap.start(); relais.start()
    # JAMAIS le vrai relais ni le vrai IMAP : tout est forcé sur les doublures, quoi que dise l'environnement
    env = dict(os.environ, DATABASE_URL=u, ATOMBOX_MAGASIN=str(magasin), ATOMBOX_LOGS=str(logs),
               ATOMBOX_IMAP_HOTE="127.0.0.1", ATOMBOX_IMAP_PORT=str(imap.port), ATOMBOX_IMAP_TLS="aucun",
               ATOMBOX_IMAP_MASTER="", ATOMBOX_IMAP_MOT_DE_PASSE="x",
               ATOMBOX_SMTP_HOTE="127.0.0.1", ATOMBOX_SMTP_PORT=str(relais.port), ATOMBOX_SMTP_TLS="aucun",
               ATOMBOX_SMTP_UTILISATEUR="", ATOMBOX_SMTP_MOT_DE_PASSE="",
               ATOMBOX_TACHES_PAS="30", ATOMBOX_IDLE_SECONDES="30",
               PYTHONPATH=str(RACINE))
    # le piège de RM3189 : un venv installé en `pip install -e` importe le code du worktree d'à côté
    vu = subprocess.run([sys.executable, "-c", "import atombox; print(atombox.__file__)"], cwd=RACINE, env=env,
                        capture_output=True, text=True).stdout.strip()
    assert vu.startswith(str(RACINE)), "les démons importeraient %s, pas le code de ce worktree" % vu

    procs = {n: subprocess.Popen([sys.executable, "-m", mod], cwd=RACINE, env=env,
                                 stdout=open(logs / (n + ".out"), "wb"), stderr=subprocess.STDOUT)
             for n, mod in (("ingestion", "atombox.ingestion.demon"), ("taches", "atombox.taches"))}

    avant = {k: os.environ.get(k) for k in ("DATABASE_URL", "ATOMBOX_MAGASIN", "ATOMBOX_LOGS")}
    os.environ.update(DATABASE_URL=u, ATOMBOX_MAGASIN=str(magasin), ATOMBOX_LOGS=str(logs))
    import atombox.db as db
    db._async.clear(); db._sync.clear()
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    client = TestClient(creer_app())
    r = client.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"})
    assert r.status_code == 200, r.text
    ch = Chaine(client, {"Authorization": "Bearer " + r.json()["jeton"]}, imap, relais, logs, procs)
    ch.boite = str(boite.boite_id)

    # le démon a fait sa première relève quand chaque dossier IMAP a son UIDVALIDITY
    def releve():
        with psycopg.connect(u) as cnx:
            return cnx.execute("select count(*) from dossier where uid_validity is not null").fetchone()[0] >= 5
    ch.attendre(releve, "la première relève du démon d'ingestion", delai=20)
    try:
        yield ch
    finally:
        for p in procs.values():
            p.terminate()
            try: p.wait(5)
            except subprocess.TimeoutExpired: p.kill()
        imap.arreter(); relais.arreter()
        for k, v in avant.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        import asyncio
        db.moteur(u).dispose(); db._sync.clear()
        for m in list(db._async.values()):
            try: asyncio.run(m.dispose())
            except Exception: pass
        db._async.clear()
        admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
        admin.execute('DROP DATABASE "%s"' % nom); admin.close()


# ------------------------------------------------------------------------------------------------
def test_1_un_courrier_arrive_et_se_traite(chaine):
    """ingestion IMAP → une règle le marque → il apparaît au bon compteur → on le lit, l'ordre
    remonte à IMAP → on répond, l'envoi part → la relève suivante ne défait rien."""
    ch = chaine
    # la règle, telle que l'ÉCRAN des règles la crée (webmail/…/administration/controleur.js)
    f = ch.post("/filtres", {"nom": "Fournisseur à traiter", "portee": "boite",
                             "predicat": {"mode": "et", "criteres": [{"champ": "from", "operateur": "contient", "valeur": "fournisseur.example"}]},
                             "action": {"type": "drapeau"}}).json()
    assert f["ok"], f

    uid = ch.imap.deposer(message("Commande 4412"))
    # IDLE doit réveiller le démon : sans lui, il dormirait 30 s
    m = ch.attendre(lambda: next((x for x in ch.liste("inbox") if x["sujet"] == "Commande 4412"), None),
                    "le message déposé dans IMAP apparaît dans la boîte de réception (IDLE a réveillé le démon)")
    assert m["lu"] is False
    assert ch.compteur("inbox").get("u", 0) >= 1, "le compteur de non-lus suit la liste"

    regles = ch.get("/filtres").json()["filtres"]
    assert regles[0]["nb_declenchements"] == 1, \
        "la règle créée depuis l'écran s'applique au courrier entrant (D171 : une règle qui agit est une règle de boîte)"
    # …et ce qu'elle a posé PART VERS IMAP. Sans cet ordre, la synchronisation descendante — qui
    # tourne dans la même relève — lisait un IMAP sans \\Flagged et défaisait la règle 50 ms plus
    # tard. Lire le drapeau en base ne le prouve pas (on le lit avant qu'il soit défait) ; IMAP
    # qui le reçoit, si : c'est impossible sans l'ordre montant.
    ch.attendre(lambda: "\\Flagged" in ch.imap.drapeaux("INBOX", uid),
                "le drapeau posé par la règle remonte à IMAP — sinon la relève suivante le défait")
    assert ch.get("/messages/" + m["id"]).json()["drapeau"] is True

    # on le lit : l'état part vers IMAP par l'événement, et le processus des tâches le pousse
    assert ch.patch("/messages/%s/rattachement" % m["id"], {"lu": True}).json()["ok"]
    ch.attendre(lambda: "\\Seen" in ch.imap.drapeaux("INBOX", uid),
                "« lu » remonte à IMAP (\\Seen) — le NOTIFY a réveillé le processus des tâches")

    # on répond, avec un Cc : l'envoi part, et les DEUX destinataires sont dans l'enveloppe (RM3214)
    r = ch.post("/messages", {"destinataires": ["achats@fournisseur.example"], "cc": "collegue@exemple.fr",
                              "sujet": "Re: Commande 4412", "corps": "Bien reçu."}).json()
    assert r["ok"], r
    remises = ch.relais.attendre(1, REVEIL)
    assert remises, "la réponse n'est jamais arrivée au relais\n" + ch.journaux()
    assert set(remises[-1]["pour"]) == {"achats@fournisseur.example", "collegue@exemple.fr"}, remises[-1]["pour"]
    assert b"Bien re" in remises[-1]["octets"]
    e = ch.attendre(lambda: (lambda x: x if x.get("etat") == "remis" else None)(ch.get("/envois/" + r["message"]["id"]).json()),
                    "le suivi d'envoi passe à « remis »")
    assert {d["etat"] for d in e["destinataires"]} == {"remis"}

    # D140c — l'envoi est COPIÉ dans « Sent » côté IMAP, marqué lu : sinon le téléphone ne voit aucun
    # message envoyé depuis AtomBox, et l'utilisateur croit que rien n'est parti
    copies = lambda: [x for x in ch.imap.boites["Sent"]["messages"] if b"Re: Commande 4412" in x["octets"]]
    ch.attendre(lambda: copies() and "\\Seen" in copies()[0]["flags"],
                "l'envoi est copié dans « Sent » côté IMAP, marqué lu (D140c)")
    assert copies()[0]["octets"].replace(b"\r\n", b"\n") == remises[-1]["octets"].replace(b"\r\n", b"\n"), \
        "ce qui est copié est ce qui est parti — les mêmes octets"

    # un AUTRE client (Thunderbird, le téléphone) RETIRE le drapeau : le retrait descend…
    ch.imap.retirer("INBOX", uid, "\\Flagged")
    ch.imap.poser("INBOX", uid, "\\Answered")      # un mot-clé qu'AtomBox ne traduit pas : il ne doit pas gêner
    ch.attendre(lambda: ch.get("/messages/" + m["id"]).json()["drapeau"] is False,
                "un drapeau retiré dans un autre client descend dans AtomBox (F113) — IDLE a signalé le FETCH")
    # …et dans l'autre sens : posé dans AtomBox (RM3244), il arrive sur le téléphone
    assert ch.patch("/messages/%s/rattachement" % m["id"], {"drapeau": True}).json()["ok"]
    ch.attendre(lambda: "\\Flagged" in ch.imap.drapeaux("INBOX", uid),
                "un drapeau posé dans AtomBox remonte à IMAP — le téléphone le voit (D140c)")
    # …et la relève n'a PAS défait ce qu'on a fait ici
    assert ch.get("/messages/" + m["id"]).json()["lu"] is True, "la synchronisation descendante a défait « lu »"

    # la relève suivante voit la copie dans « Sent » : elle ne doit PAS en faire un second message
    ch.imap.deposer(message("Réveil"))
    ch.attendre(lambda: any(x["sujet"] == "Réveil" for x in ch.liste("inbox", filtre="tous")), "une relève complète a eu lieu")
    assert len([x for x in ch.liste("sent", filtre="tous") if x["sujet"] == "Re: Commande 4412"]) == 1, \
        "la copie IMAP de l'envoi a été réingérée comme un second message"
    assert len(copies()) == 1, "l'envoi n'est copié qu'UNE fois dans IMAP"

    # « au moins une fois » (D161) : une tâche peut être REJOUÉE — IMAP a reçu la copie, puis le
    # processus est tombé avant d'enregistrer l'UID. Rejouée, elle doit retrouver sa copie par le
    # Message-ID, pas en faire une seconde.
    import psycopg
    from atombox.modules import evenements
    from atombox.db import session as ouvrir
    with psycopg.connect(os.environ["DATABASE_URL"]) as cnx:
        cnx.execute("update rattachement set uid_imap = null where comm_id = %s", (r["message"]["id"],)); cnx.commit()
    with ouvrir(os.environ["DATABASE_URL"]) as s:
        evenements.emettre(s, "message.envoye", {"comm_id": r["message"]["id"], "boite_id": ch.boite, "refuses": []}); s.commit()
    def uid_repose():
        with psycopg.connect(os.environ["DATABASE_URL"]) as cnx:
            return cnx.execute("select uid_imap from rattachement where comm_id = %s", (r["message"]["id"],)).fetchone()[0]
    ch.attendre(uid_repose, "la tâche rejouée retrouve la copie et repose l'UID")
    assert len(copies()) == 1, "une tâche rejouée a copié l'envoi une SECONDE fois dans IMAP"


def test_2_un_brouillon_vit(chaine):
    """composer → enregistrer → reprendre → réenregistrer → envoyer : le brouillon disparaît, le
    message est dans « envoyés » avec ses destinataires en base, et il part au relais."""
    ch = chaine
    avant = len(ch.relais.remises)
    br = ch.post("/messages", {"destinataires": ["client@exemple.org"], "sujet": "Devis",
                               "corps": "première version", "composition": {"a": "client@exemple.org"}}).json()["message"]
    assert br["dossier_origine"] == "drafts"
    assert any(x["id"] == br["id"] for x in ch.liste("drafts", filtre="tous")), "le brouillon est dans « brouillons »"

    repris = ch.get("/messages/" + br["id"]).json()["composition"]
    assert repris and repris["a"] == "client@exemple.org", "un brouillon se reprend : sa composition est reconstruite"

    maj = ch.c.put("/api/v1/messages/" + br["id"], json={"destinataires": ["client@exemple.org"], "cc": "patron@exemple.org",
                                                          "sujet": "Devis révisé", "corps": "seconde version"}, headers=ch.h).json()
    assert maj["message"]["id"] == br["id"], "réenregistré, il garde son identité (D089)"
    assert ch.get("/messages/" + br["id"]).json()["composition"]["cc"] == "patron@exemple.org"

    # envoyer, comme le fait le webmail : le message part, puis le brouillon est détaché
    env = ch.post("/messages", {"destinataires": ["client@exemple.org"], "cc": "patron@exemple.org",
                                "sujet": "Devis révisé", "corps": "seconde version"}).json()["message"]
    assert ch.delete("/messages/%s/rattachement" % br["id"]).json().get("ok")
    assert not any(x["id"] == br["id"] for x in ch.liste("drafts", filtre="tous")), \
        "le brouillon a disparu de « Brouillons », même avec la puce « Tout »"
    assert not any(x["id"] == br["id"] for x in ch.liste("drafts", filtre="sortis")), \
        "et « traités / archivés » ne montre pas la corbeille"
    envoye = next(x for x in ch.liste("sent", filtre="tous") if x["id"] == env["id"])
    relu = ch.get("/messages/" + envoye["id"]).json()
    assert relu["destinataires"] == ["client@exemple.org", "patron@exemple.org"], "les destinataires sont en BASE"

    remises = ch.relais.attendre(avant + 1, REVEIL)
    assert len(remises) == avant + 1, "l'envoi n'est jamais parti au relais\n" + ch.journaux()
    assert set(remises[-1]["pour"]) == {"client@exemple.org", "patron@exemple.org"}
    assert len(ch.relais.remises) == avant + 1, "le brouillon, lui, n'est JAMAIS parti"


def test_3_un_tag_remplit_un_dossier(chaine):
    """poser un tag → le dossier virtuel se remplit, son compteur suit → retirer le tag → les deux
    redescendent."""
    ch = chaine
    ch.imap.deposer(message("Relance chantier Dupont"))
    m = ch.attendre(lambda: next((x for x in ch.liste("inbox", filtre="tous") if x["sujet"] == "Relance chantier Dupont"), None),
                    "le message arrive")
    v = ch.post("/dossiers-virtuels", {"label": "Chantier Dupont", "criteres": [{"axe": "projet", "val": "dupont"}]}).json()
    assert v["ok"], v
    vid = v["dossier"]["id"]
    assert ch.liste(vid, filtre="tous") == [], "vide tant que rien ne porte le tag"

    t = ch.post("/messages/%s/tags" % m["id"], {"axe": "projet", "val": "dupont"}).json()
    assert t["ok"], t
    assert [x["id"] for x in ch.liste(vid, filtre="tous")] == [m["id"]], "le dossier virtuel se remplit"
    assert ch.compteur(vid).get("t") == 1, "et son compteur suit (%r)" % ch.compteur(vid)
    assert ch.compteur("projet:dupont").get("t") == 1 or ch.compteur("axe:projet").get("t") == 1, \
        "la branche d'axe compte ce qu'elle liste (D166)"

    assert ch.delete("/messages/%s/tags/projet=dupont" % m["id"]).json()["ok"]
    assert ch.liste(vid, filtre="tous") == [], "retirer le tag vide le dossier"
    assert (ch.compteur(vid).get("t") or 0) == 0, "et son compteur redescend"
