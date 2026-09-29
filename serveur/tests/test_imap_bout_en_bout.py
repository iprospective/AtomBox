"""D180 — le serveur IMAP sur un VRAI socket, contre une VRAIE base, avec le client de la
bibliothèque standard (`imaplib`).

Le test de protocole (`test_imap_serveur.py`) éprouve le dialogue sans rien brancher. Celui-ci
éprouve ce que l'autre ne peut pas : que le socket parle, que la base répond, que le magasin rend
l'octet exact, et qu'un client qui n'est pas le nôtre s'y retrouve. `imaplib` est un client
indépendant, écrit sans rien savoir de nous — c'est ce qui en fait un juge.
"""
from __future__ import annotations
import asyncio
import imaplib
import os
import re
import socket
import threading
import uuid
from datetime import datetime, timezone
import pytest

MESSAGE = (b"From: Fournisseur <achats@fournisseur.example>\r\nTo: contact@exemple.fr\r\n"
           b"Subject: Commande 4412\r\nDate: Fri, 18 Sep 2026 10:00:00 +0200\r\n"
           b"Message-ID: <c4412@fournisseur.example>\r\nMIME-Version: 1.0\r\n"
           b"Content-Type: text/plain; charset=utf-8\r\n\r\nBonjour,\r\nci-joint le devis.\r\n")


@pytest.fixture(scope="module")
def serveur_imap(tmp_path_factory):
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    import psycopg, re as _re
    from atombox.db import session as ouvrir
    from atombox.magasin import Magasin
    from atombox.api.securite import hacher_mot_de_passe
    from atombox.ingestion.ingestion import adresse, ingerer
    from atombox.schema.modeles import Acces, Boite, Compte, Dossier
    from atombox.uuid7 import uuid7

    nom = "atombox_imap_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = _re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c:
        c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    magasin = Magasin(str(tmp_path_factory.mktemp("magasin")))
    s = ouvrir(u)
    a = adresse(s, "contact@exemple.fr")
    boite = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(boite)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True,
                    cree_le=datetime.now(timezone.utc), mot_de_passe_empreinte=hacher_mot_de_passe("secret")); s.add(compte)
    s.add(Acces(compte_id=compte.compte_id, boite_id=boite.boite_id, role="membre",
                debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
    inbox = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(inbox)
    for alias in ("Sent", "Trash"):
        s.add(Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=alias, alias_imap=alias, protege=True))
    s.commit()
    for i in range(3):
        ingerer(s, magasin, boite.boite_id, MESSAGE.replace(b"<c4412@", b"<c%d@" % i), dossier_id=inbox.dossier_id)

    port = _port_libre()
    pret = threading.Event()
    boucle = {}

    def tourner():
        async def demarrer():
            from atombox.imap.serveur import Ecouteur
            e = Ecouteur(lambda: ouvrir(u), magasin)
            srv = await asyncio.start_server(e.client, "127.0.0.1", port)
            boucle["serveur"] = srv
            pret.set()
            async with srv: await srv.serve_forever()
        # `asyncio.run` dans un fil DÉMON : il meurt avec le processus. Arrêter la boucle à la
        # main depuis un autre fil a sa part de pièges, et on n'a rien à sauver ici.
        try: asyncio.run(demarrer())
        except (asyncio.CancelledError, RuntimeError): pass

    fil = threading.Thread(target=tourner, daemon=True); fil.start()
    assert pret.wait(10), "le serveur IMAP n'a pas démarré"
    yield {"port": port, "magasin": magasin, "session": s}
    s.close()
    import atombox.db as db, asyncio as aio
    db.moteur(u).dispose(); db._sync.clear()
    for m in list(db._async.values()):
        try: aio.run(m.dispose())
        except Exception: pass
    db._async.clear()
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def test_un_vrai_client_se_connecte_liste_et_lit(serveur_imap):
    """imaplib n'a jamais entendu parler d'AtomBox : c'est ce qui en fait un juge."""
    # UN CLIENT SANS DÉLAI PEND POUR TOUJOURS. `imaplib` n'en pose aucun par défaut : au premier
    # défaut du serveur, le test ne rougit pas, il se fige — et l'on croit à une boucle infinie
    # dans le code alors que c'est le harnais qui attend. C'est ce qui est arrivé ici.
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        assert b"IMAP4rev1" in c.welcome, c.welcome
        with pytest.raises(imaplib.IMAP4.error):
            c.login("mathieu", "PAS LE BON")
        assert c.login("mathieu", "secret")[0] == "OK"

        code, boites = c.list()
        assert code == "OK"
        noms = " ".join(b.decode() for b in boites)
        assert '"INBOX"' in noms, noms
        assert '"Trash"' in noms, "les autres dossiers sont là aussi"

        code, n = c.select("INBOX", readonly=True)
        assert code == "OK" and int(n[0]) == 3, n
        assert c.untagged_responses.get("OK"), "la sélection porte UIDVALIDITY et UIDNEXT"

        code, uids = c.uid("SEARCH", None, "ALL")
        liste = uids[0].split()
        assert code == "OK" and len(liste) == 3, uids

        code, data = c.uid("FETCH", liste[0], "(BODY.PEEK[])")
        brut = data[0][1]
        attendu = serveur_imap["magasin"].lire(_blob(serveur_imap["session"], int(liste[0])))
        assert brut == attendu, "l'octet servi est CELUI DU MAGASIN, pas une reconstruction (D025, RM3213)"

        code, data = c.uid("FETCH", liste[0], "(FLAGS RFC822.SIZE ENVELOPE)")
        rendu = data[0].decode() if isinstance(data[0], bytes) else " ".join(map(str, data[0]))
        assert "RFC822.SIZE %d" % len(attendu) in rendu, rendu
        assert "Commande 4412" in rendu, "l'enveloppe porte le sujet"
    finally:
        c.logout()


def test_l_ecriture_est_refusee_franchement(serveur_imap):
    """Un refus explicite vaut mieux qu'un silence : le client doit savoir qu'il ne peut pas."""
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        code, _ = c.select("INBOX", readonly=True)
        assert code == "OK"
        for commande in ("STORE 1 +FLAGS (\\Seen)", "EXPUNGE", "COPY 1 Trash", "APPEND INBOX {3}"):
            tag = c._new_tag().decode()
            c.send(("%s %s\r\n" % (tag, commande)).encode())
            reponse = c._get_line().decode()
            assert " BAD " in reponse or " NO " in reponse, "%s a été accepté : %r" % (commande, reponse)
            assert not reponse.startswith("+ "), \
                "%s a obtenu une demande de données pour une commande refusée — le dialogue se désynchronise" % commande
        assert c.noop()[0] == "OK", "après ces refus, le dialogue est intact"
    finally:
        try: c.logout()
        except Exception: pass


def _blob(session, uid):
    from sqlalchemy import select
    from atombox.schema.modeles import CommEmail, Rattachement
    r = session.scalar(select(Rattachement).where(Rattachement.uid_servi == uid))
    return session.get(CommEmail, r.comm_id).blob_ref
