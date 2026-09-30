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
    r = Rattachement(comm_id=c.comm_id, boite_id=uuid.uuid4(), status="new", dossier_id=trash.dossier_id, dossier_origine_id=did, exit_reason=None)
    # `etat` non passé = personne n'y a touché : c'est le cas de la très grande majorité des lignes,
    # et c'est ce qui rend la table des faits de lecture CREUSE (D175 § 5).
    o = svc.serialiser(r, c, ds, "contact@exemple.fr")
    assert o["id"] == str(c.comm_id) and o["date_recue"] == "2026-09-04T09:12:00+00:00" and o["lu"] is False
    assert o["a_revoir"] is False and o["drapeau"] is False
    assert o["dossier_origine"] == "inbox" and o["dossier"] == "trash", "déplacé en corbeille : origine gardée (D088)"
    for k in ("sujet", "from_nom", "from_adresse", "date_recue", "thread_id", "nb_pieces_jointes", "taille", "sorti_le", "motif_sortie", "dossier_origine", "destinataires", "reponse_possible", "list_id", "lu", "sens", "nature", "snippet", "boite", "dossier", "statut", "tags",
              "a_revoir", "drapeau", "sommeil", "marqueurs", "traite_le", "archive_le", "statut_le"):
        assert k in o, k

def _transfert_de(brut: bytes):
    import email.policy
    from atombox.ingestion.analyse import analyser

    class FauxCompte:
        nom, login = "Mathieu", "mathieu"
    octets = svc._composer(FauxCompte(), "contact@exemple.fr",
                           {"destinataires": ["jean@x.fr"], "sujet": "Tr: essai", "corps": "voir dessous"},
                           uuid.uuid4(), datetime.now(timezone.utc), None, brut)
    return octets, analyser(octets)


def test_l_encapsule_porte_l_octet_exact_du_magasin():
    """RM3213 (D025, D148, D168) — le message transmis était RE-SÉRIALISÉ par la bibliothèque : 265
    octets en entrée, 254 en sortie. Sa signature DKIM ne se vérifiait plus chez le destinataire, et
    la déduplication ne retrouvait pas le blob de l'original, stocké une seconde fois.

    Trois cas, parce que l'encodage de transport dépend du contenu : un message en ASCII 7 bits (le
    cas courant — MIME encode déjà l'intérieur), un message avec de l'UTF-8 brut, et un message à
    lignes trop longues pour SMTP. Dans les trois, l'octet extrait est l'octet déposé."""
    import email.policy
    en_tetes = (b"From: Client <client@exemple.fr>\r\nTo: contact@exemple.fr\r\n"
                b"Subject: Devis 2026\r\nMessage-ID: <abc@exemple.fr>\r\n"
                b"DKIM-Signature: v=1; a=rsa-sha256; d=exemple.fr; s=k1;\r\n\tbh=abc; b=def\r\n"
                b"MIME-Version: 1.0\r\n")
    cas = {
        "7bit": en_tetes + b"Content-Type: text/plain; charset=us-ascii\r\n\r\nBonjour,\r\n  deux espaces en tete.\r\n",
        "8bit": en_tetes + b"Content-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: 8bit\r\n\r\n"
                           + "Réponse attendue : 1 200 €\r\n".encode("utf-8"),
        "base64": en_tetes + b"Content-Type: text/plain\r\n\r\n" + b"x" * 1200 + b"\r\n",
    }
    for attendu, brut in cas.items():
        octets, a = _transfert_de(brut)
        assert len(a.pieces) == 1 and a.pieces[0].type_declare == "message/rfc822", (attendu, a.structure_mime)
        assert a.pieces[0].octets == brut, "%s : l'octet encapsulé n'est plus celui du magasin" % attendu
        assert ("Content-Transfer-Encoding: " + attendu).encode() in octets, \
            "%s : l'encodage de transport choisi n'est pas le bon" % attendu
        assert a.corps_texte.strip() == "voir dessous", "le commentaire reste le seul texte indexé (D163)"


def test_une_adresse_est_parsee_avant_d_entrer_en_base():
    """RM3214 — « Florian HENRY <florian.henry@scopen.fr> » est entré TEL QUEL en base, avec le nom
    dans la partie locale. smtplib parsait à la remise, donc le courrier partait : seul le suivi
    d'envoi et le carnet gardaient un fantôme."""
    from atombox.ingestion.ingestion import normaliser_adresse
    assert normaliser_adresse("Florian HENRY <florian.henry@scopen.fr>") == "florian.henry@scopen.fr"
    assert normaliser_adresse("  jean@x.fr  ") == "jean@x.fr"
    assert normaliser_adresse('"Nom, Prénom" <a@b.fr>') == "a@b.fr"
    assert normaliser_adresse("n'importe quoi") == "", "sans @, il n'y a pas d'adresse"


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

def test_transfert_encapsule_le_source_et_ne_marque_pas_le_message():
    """D167/D066/D067 — le message transféré part INTACT dans une partie message/rfc822 ; le corps
    indexé est le commentaire seul (D163) ; et aucun en-tête ne porte le lien : la provenance est
    une relation en base. Un marqueur dans le message partirait chez le destinataire, ne
    s'indexerait pas, et rendrait le message non reconstructible à l'octet (D025)."""
    import email, email.policy
    from atombox.ingestion.analyse import analyser

    class FauxCompte:
        nom, login = "Mathieu", "mathieu"

    src = email.message.EmailMessage(policy=email.policy.SMTP)
    src["From"] = "Client <client@exemple.fr>"; src["To"] = "contact@exemple.fr"
    src["Subject"] = "Devis 2026 / travaux"; src["Message-ID"] = "<abc@exemple.fr>"
    src.set_content("Bonjour,\nvoici le devis.")
    src.add_attachment(b"%PDF-1.4 devis", maintype="application", subtype="pdf", filename="devis.pdf")
    brut = src.as_bytes()

    octets = svc._composer(FauxCompte(), "contact@exemple.fr",
                           {"destinataires": ["jean@x.fr"], "sujet": "Tr: Devis 2026 / travaux",
                            "corps": "tu peux regarder ?", "reference": "peu-importe"},
                           uuid.uuid4(), datetime.now(timezone.utc), None, brut)
    a = analyser(octets)
    assert a.corps_texte.strip() == "tu peux regarder ?", "l'index ne voit que le commentaire (D163)"
    assert len(a.pieces) == 1 and a.pieces[0].type_declare == "message/rfc822", a.structure_mime
    assert a.pieces[0].nom_declare.endswith(".eml"), "la pièce porte le sujet du message transmis"
    # le PDF du message transmis est DEDANS, il n'est pas une pièce du transfert (D066) : compter
    # les deux annoncerait « 2 pièces jointes » à qui n'en a joint qu'une.
    assert a.pieces[0].octets, "une partie message/rfc822 n'a pas de charge décodable : sans le cas " \
                               "particulier, toutes les pièces encapsulées pesaient zéro octet"
    assert b"X-AtomBox-Reference" not in octets, "la provenance vit en base, jamais dans le message (D067)"
    interne = email.message_from_bytes(octets, policy=email.policy.SMTP).get_payload(1).get_payload(0)
    assert interne["Subject"] == "Devis 2026 / travaux" and interne["Message-ID"] == "<abc@exemple.fr>", \
        "le message transféré part tel qu'il a été reçu"

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
    # LE HARNAIS NE PARLE PAS À UN VRAI SERVEUR IMAP. Sans cela, ce test échouait dès que
    # /etc/atombox/env était chargé : créer un dossier utilisateur envoie un ordre au fournisseur
    # (D140b), et le test dépendait alors d'une machine tierce et d'un mot de passe. On coupe le
    # réglage et son nom d'hier — demandé à settings, jamais recopié (D181).
    from atombox import settings
    coupees = ["ATOMBOX_IMAP_HOST"]
    coupees += [v for k, v in settings.FORMER_NAMES.items() if k in coupees]
    avant = {k: os.environ.get(k) for k in ["DATABASE_URL", "ATOMBOX_STORE"] + coupees}
    for k in coupees: os.environ.pop(k, None)
    os.environ["DATABASE_URL"] = u; os.environ["ATOMBOX_STORE"] = str(tmp_path_factory.mktemp("magasin"))
    s = ouvrir(u); m = Magasin(os.environ["ATOMBOX_STORE"])
    a = adresse(s, "contact@exemple.fr")
    boite = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(boite)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True, cree_le=datetime.now(timezone.utc), mot_de_passe_empreinte=hacher_mot_de_passe("secret")); s.add(compte)
    s.add(Acces(compte_id=compte.compte_id, boite_id=boite.boite_id, role="lecteur", debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
    inbox = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(inbox)
    for alias in ("Sent", "Drafts", "Trash", "Junk"): s.add(Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=alias, alias_imap=alias, protege=True))
    from atombox.schema.seeds import seed_builtins
    from atombox.services.mailbox import ensure_mailboxes
    s.flush()
    seed_builtins(s)                      # schema.sql est un DDL : il n'apporte aucune donnée
    ensure_mailboxes(s, boite.boite_id)    # …et sans les boîtes d'état, « archiver » n'a nulle part où aller
    s.commit()
    ids = [ingerer(s, m, boite.boite_id, lire(f), dossier_id=inbox.dossier_id)["comm_id"] for f in ("simple.eml", "reponse.eml", "pieces.eml", "liste.eml")]
    yield {"session": s, "ids": ids, "url": u}
    s.close()
    for k, v in avant.items():   # ne jamais laisser l'environnement pointer sur une base détruite
        if v is None: os.environ.pop(k, None)
        else: os.environ[k] = v
    import atombox.db as db, asyncio
    db.moteur(u).dispose(); db._sync.clear()
    for m in list(db._async.values()):
        try: asyncio.run(m.dispose())
        except Exception: pass
    db._async.clear()
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()

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
    p = c.patch("/api/v1/messages/" + str(monde["ids"][3]) + "/rattachement", json={"motif_sortie": "archived"}, headers=h).json()
    assert p["message"]["motif_sortie"] == "archived" and c.get("/api/v1/messages", params={"dossier": "archives"}, headers=h).json()["total"] == 1
    # LA DATE SUIT LA TRANSITION : on ne la passe plus, et pourtant elle est là. Sans elle,
    # l'archivage automatique (D014) n'aurait aucune clé.
    assert p["message"]["archive_le"] and p["message"]["sorti_le"] == p["message"]["archive_le"]
    n = c.post("/api/v1/messages", json={"boite": "contact@exemple.fr", "destinataires": ["jean@x.fr"], "sujet": "Test", "corps": "Bonjour", "composition": None}, headers=h).json()
    assert n["ok"] and n["crees"] == 1 and n["message"]["sens"] == "out" and n["message"]["dossier_origine"] == "sent"
    assert c.get("/api/v1/messages", params={"dossier": "sent"}, headers=h).json()["total"] == 1
    # le suivi d'envoi (D099) : le message est en base, l'événement est en file, rien n'est encore remis
    envoye = n["message"]["id"]
    e = c.get("/api/v1/envois/" + envoye, headers=h).json()
    assert e["etat"] == "en_attente" and e["relancable"] and e["destinataires"] == [], e
    assert c.get("/api/v1/envois", headers=h).json()["total"] == 1
    r = c.post("/api/v1/envois/%s/relancer" % envoye, headers=h).json()
    assert r["ok"] and r["relance"] == 1 and r["destinataires"] == ["jean@x.fr"], r
    assert c.post("/api/v1/envois/%s/relancer" % envoye, headers=h).json()["ok"], "relancer deux fois ne casse rien"
    assert c.get("/api/v1/envois/" + str(monde["ids"][0]), headers=h).status_code == 404, "un message reçu n'a pas d'envoi"

    # F013 — un dossier utilisateur, créé ici (et côté IMAP quand il est configuré)
    d = c.post("/api/v1/dossiers", json={"nom": "Devis 2026"}, headers=h).json()
    assert d["ok"] and d["dossier"]["nom"] == "Devis 2026" and not d["dossier"]["protege"]
    did = d["dossier"]["id"]
    assert c.post("/api/v1/dossiers", json={"nom": "Devis 2026"}, headers=h).status_code == 400, "deux fois le même : refusé"
    assert c.patch("/api/v1/dossiers/" + did, json={"nom": "Devis"}, headers=h).json()["dossier"]["nom"] == "Devis"
    assert c.get("/api/v1/referentiels", headers=h).json()["util"][0]["label"] == "Devis", "il apparaît dans l'arborescence"
    proteges = [x for x in c.get("/api/v1/referentiels", headers=h).json()["speciaux"]]
    assert proteges, "les spéciaux restent"
    assert c.delete("/api/v1/dossiers/" + did, headers=h).json()["supprimes"] == 1

    # F032 — les identités d'expédition
    premiere = c.post("/api/v1/identites", json={"nom_affiche": "Mathieu", "par_defaut": True}, headers=h).json()
    assert premiere["ok"] and premiere["identite"]["par_defaut"] is True
    i = c.post("/api/v1/identites", json={"nom_affiche": "Service commercial", "signature": "-- \nL'équipe", "par_defaut": True}, headers=h).json()
    assert i["ok"] and i["identite"]["signature"].endswith("L'équipe")
    apres = c.get("/api/v1/identites", headers=h).json()["identites"]
    assert len(apres) == 2 and sum(1 for x in apres if x["par_defaut"]) == 1, "une seule identité par défaut"
    autre = next(x for x in apres if not x["par_defaut"])
    assert c.delete("/api/v1/identites/" + autre["id"], headers=h).json()["supprimes"] == 1
    seule = c.get("/api/v1/identites", headers=h).json()["identites"][0]
    assert c.delete("/api/v1/identites/" + seule["id"], headers=h).status_code == 409, "jamais la dernière"

    # F106 — un brouillon garde son identité quand on le réenregistre (D089)
    br = c.post("/api/v1/messages", json={"destinataires": ["jean@x.fr"], "sujet": "Ébauche",
                                          "corps": "début", "composition": {"a": "jean@x.fr"}}, headers=h).json()["message"]
    assert br["dossier_origine"] == "drafts"
    maj = c.put("/api/v1/messages/" + br["id"], json={"destinataires": ["jean@x.fr", "paul@x.fr"],
                                                      "sujet": "Ébauche revue", "corps": "suite"}, headers=h).json()
    assert maj["ok"] and maj["message"]["id"] == br["id"], "le brouillon garde son identifiant"
    relu = c.get("/api/v1/messages/" + br["id"], headers=h).json()
    assert relu["sujet"] == "Ébauche revue" and "suite" in relu["corps"] and len(relu["destinataires"]) == 2
    assert c.put("/api/v1/messages/" + str(monde["ids"][0]), json={"sujet": "x"}, headers=h).status_code == 404, \
        "un message reçu n'est pas un brouillon : il ne se réécrit pas (D029)"

    # F106 (suite) — un brouillon se REPREND : sa composition est reconstruite du message,
    # et les destinataires d'un message ÉCRIT ICI sont en base, pas seulement en écho du POST.
    br2 = c.post("/api/v1/messages", json={"destinataires": ["jean@x.fr"], "cc": "paul@x.fr",
                                           "sujet": "Avec copie", "corps": "texte",
                                           "composition": {"a": "jean@x.fr"}}, headers=h).json()["message"]
    relu2 = c.get("/api/v1/messages/" + br2["id"], headers=h).json()
    compo = relu2["composition"]
    assert compo, "un brouillon relu porte sa composition — sinon on ne peut pas le reprendre"
    assert compo["a"] == "jean@x.fr" and compo["cc"] == "paul@x.fr", "le Cc survit à la relecture"
    assert compo["sujet"] == "Avec copie" and "texte" in compo["corps"]
    # RM3246 — ENVOYER un brouillon le CONSOMME : c'est le MÊME message qui part (D089).
    # Le webmail créait un second message puis « détachait » le brouillon, ce qui le mettait à la
    # corbeille : l'utilisateur retrouvait chacun de ses brouillons envoyés dans sa Corbeille.
    br3 = c.post("/api/v1/messages", json={"destinataires": ["jean@x.fr"], "sujet": "À finir",
                                           "corps": "ébauche", "composition": {"a": "jean@x.fr"}},
                 headers=h).json()["message"]
    reenr = c.put("/api/v1/messages/" + br3["id"], json={"destinataires": ["jean@x.fr"], "sujet": "À finir",
                                                         "corps": "ébauche"}, headers=h).json()
    assert reenr["message"]["dossier_origine"] == "drafts", \
        "réenregistrer n'envoie PAS : une action qui expédie du courrier ne se devine pas"
    envoi = c.post("/api/v1/messages/" + br3["id"] + "/envoyer",
                   json={"destinataires": ["jean@x.fr", "paul@x.fr"], "sujet": "Fini", "corps": "voilà"},
                   headers=h).json()
    assert envoi["ok"] and envoi["message"]["id"] == br3["id"], "envoyé, le brouillon garde son identité"
    assert envoi["message"]["dossier_origine"] == "sent", "il est passé dans « Envoyés »"
    parti = c.get("/api/v1/messages/" + br3["id"], headers=h).json()
    assert parti["composition"] is None, "ce n'est plus un brouillon : il ne se rouvre plus en composition"
    assert parti["suppr"] is False and parti["motif_sortie"] is None, "et il n'est PAS à la corbeille"
    assert parti["destinataires"] == ["jean@x.fr", "paul@x.fr"], "ses destinataires sont en base"
    liste = lambda d, f: [x["id"] for x in c.get("/api/v1/messages", params={"dossier": d, "filtre": f}, headers=h).json()["messages"]]
    assert br3["id"] not in liste("drafts", "tous"), "il a quitté « Brouillons », même avec la puce « Tout »"
    assert br3["id"] in liste("sent", "tous"), "et il est dans « Envoyés »"
    assert br3["id"] not in liste("trash", "tous"), "la Corbeille ne le contient pas"

    # F132 — TRANSFÉRER : le source encapsulé, la provenance en base, le commentaire à part (D167)
    source = str(monde["ids"][2])                      # pieces.eml — avec ses propres pièces jointes
    tr = c.post("/api/v1/messages", json={"destinataires": ["jean@x.fr"], "sujet": "Tr: Devis",
                                          "corps": "tu peux regarder ?", "reference": source}, headers=h).json()["message"]
    assert tr["reference"] == source, "le transfert rapporte sa provenance"
    relu_tr = c.get("/api/v1/messages/" + tr["id"], headers=h).json()
    assert relu_tr["corps"].strip() == "tu peux regarder ?", "le corps stocké est le COMMENTAIRE seul (D163)"
    assert len(relu_tr["pieces_jointes"]) == 1, relu_tr["pieces_jointes"]
    assert relu_tr["pieces_jointes"][0]["mime_detecte"] == "message/rfc822", "l'original part encapsulé (D066)"
    assert relu_tr["pieces_jointes"][0]["octets"] > 0, "et il pèse ses octets : la pièce n'est pas vide"
    assert relu_tr["reference"] == source, "la provenance se relit — c'est une relation, pas un en-tête (D067)"
    hors = c.post("/api/v1/messages", json={"destinataires": ["jean@x.fr"], "sujet": "Tr: rien",
                                            "corps": "?", "reference": str(uuid.uuid4())}, headers=h).json()["message"]
    assert hors["reference"] is None, "on ne transfère pas ce qu'on n'a pas le droit de lire (D036)"

    # F137 — l'encapsulé qu'on POSSÈDE est résolu vers son message (D168), et n'est plus un fichier
    pj = relu_tr["pieces_jointes"][0]
    assert pj["comm_id"] == source, "la pièce message/rfc822 pointe le message AtomBox d'origine"
    # RM3213 — l'encapsulé EST le blob de l'original : même octet, même empreinte, donc dédupliqué
    from atombox.schema.modeles import CommEmail
    monde["session"].expire_all()
    blob_source = monde["session"].get(CommEmail, uuid.UUID(source)).blob_ref
    assert pj["sha256"] == blob_source, "le message transmis est stocké une seconde fois (D066)"
    from atombox.schema.modeles import Blob
    assert monde["session"].get(Blob, blob_source).nb_references >= 2, \
        "UN fichier au magasin, deux porteurs : l'original (comme message) et son transfert (comme pièce)"
    # F136 — et les octets d'une pièce se servent enfin : sans cette route, aucun clic n'aboutit
    rr = c.get("/api/v1/messages/%s/pieces-jointes/%s" % (tr["id"], pj["pj_id"]), headers=h)
    assert rr.status_code == 200 and rr.headers["content-type"].startswith("message/rfc822"), rr.headers
    assert len(rr.content) == pj["octets"] and "attachment" in rr.headers["content-disposition"]
    d2 = c.get("/api/v1/messages/" + source, headers=h).json()
    pdf = next(x for x in d2["pieces_jointes"] if x["mime_detecte"] == "application/pdf")
    assert pdf["comm_id"] is None, "un PDF n'est pas un message : rien à résoudre"
    r2 = c.get("/api/v1/messages/%s/pieces-jointes/%s" % (source, pdf["pj_id"]), headers=h)
    assert r2.status_code == 200 and r2.content[:4] == b"%PDF", "le type servi est le type DÉTECTÉ (D032)"
    assert c.get("/api/v1/messages/%s/pieces-jointes/%s" % (str(monde["ids"][0]), pdf["pj_id"]),
                 headers=h).status_code == 404, "une pièce ne se sert pas depuis un autre message"

    # RM3214 — un Cc EST un destinataire : il doit être dans l'enveloppe, pas seulement dans l'en-tête
    avec_cc = c.post("/api/v1/messages", json={"destinataires": ["Jean Valjean <jean@x.fr>"], "cc": "copie@x.fr",
                                               "sujet": "Avec copie", "corps": "bonjour"}, headers=h).json()["message"]
    rl = c.post("/api/v1/envois/%s/relancer" % avec_cc["id"], headers=h).json()
    assert rl["destinataires"] == ["jean@x.fr", "copie@x.fr"], rl
    relu_cc = c.get("/api/v1/messages/" + avec_cc["id"], headers=h).json()
    assert relu_cc["destinataires"] == ["jean@x.fr", "copie@x.fr"], relu_cc["destinataires"]
    assert all("<" not in d for d in relu_cc["destinataires"]), "le nom d'affichage n'entre pas dans l'adresse"

    envoye = c.post("/api/v1/messages", json={"destinataires": ["jean@x.fr"], "sujet": "Parti",
                                              "corps": "voilà"}, headers=h).json()["message"]
    assert envoye["dossier_origine"] == "sent"
    relu3 = c.get("/api/v1/messages/" + envoye["id"], headers=h).json()
    assert relu3["destinataires"] == ["jean@x.fr"], "un message envoyé garde ses destinataires en base"
    assert relu3["composition"] is None, "un message parti n'est plus un brouillon"

    # F108 — le carnet auto-collecté
    carnet = c.get("/api/v1/carnet", headers=h).json()["carnet"]
    assert any(x["adresse"] == "jean@x.fr" for x in carnet), "les destinataires écrits nourrissent le carnet (D109)"
    assert c.get("/api/v1/carnet", params={"q": "paul"}, headers=h).json()["carnet"][0]["adresse"] == "paul@x.fr"

    # F016 — une règle qui classe, et son compteur
    f = c.post("/api/v1/filtres", json={"nom": "Tessier au dossier", "portee": "compte",
                                        "predicat": {"mode": "et", "criteres": [{"champ": "from", "operateur": "contient", "valeur": "tessier"}]},
                                        "action": {"type": "drapeau"}}, headers=h).json()
    assert f["ok"] and f["filtre"]["muette"] is True, "une règle neuve n'a jamais servi"
    assert f["filtre"]["portee"] == "boite", \
        "une règle qui agit est une règle de BOÎTE (D171) : en portée « compte », l'ingestion ne la voyait jamais"
    l = c.get("/api/v1/filtres", headers=h).json()
    assert l["total"] == 1 and "contient" in l["operateurs"] and "classer" in l["actions"]
    assert c.patch("/api/v1/filtres/" + f["filtre"]["id"], json={"actif": False}, headers=h).json()["filtre"]["actif"] is False
    assert c.delete("/api/v1/filtres/" + f["filtre"]["id"], headers=h).json()["supprimes"] == 1
    assert c.delete("/api/v1/messages/" + mid + "/rattachement", headers=h).json()["detache"]
    assert c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=h).json()["total"] == 2
    assert c.get("/api/v1/messages/" + str(uuid.uuid4()), headers=h).status_code == 404
    assert c.get("/api/v1/messages", headers={}).status_code == 401
