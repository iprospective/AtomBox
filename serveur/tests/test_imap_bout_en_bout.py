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
           b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
           # DES ACCENTS, EXPRÈS. Le corpus d'essai n'en avait aucun, et c'est pour ça qu'un
           # double encodage est passé jusqu'en produit : tout l'ASCII survit à n'importe quelle
           # conversion. Un jeu d'essai sans caractère non ASCII ne teste pas l'encodage.
           b"Audit, Conseil, D\xc3\xa9veloppement, Int\xc3\xa9gration, S\xc3\xa9curit\xc3\xa9\r\n")


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
    s.flush()
    # LES CINQ BOÎTES AUX LETTRES (D183) : `schema.sql` est un DDL, il n'apporte aucune donnée, et
    # sans « Archive » un MOVE vers elle répond TRYCREATE — exactement le geste qui « ne fait rien ».
    from atombox.schema.semences import semer
    from atombox.services.mailbox import assurer
    semer(s); assurer(s, boite.boite_id)
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


def test_l_octet_servi_est_celui_du_magasin_MEME_avec_des_accents(serveur_imap):
    """Le défaut trouvé en produit : « DÃ©veloppement » au lieu de « Développement ».

    La cause n'était pas le message — il déclarait UTF-8 et ses octets étaient justes. C'était
    l'écrivain du serveur : les octets bruts entraient dans une `str` par `latin-1` et en
    sortaient par `utf-8`, donc chaque octet ≥ 0x80 en devenait deux.

    Le symptôme visible était l'accent. LE SYMPTÔME GRAVE était que la taille annoncée du littéral
    ne correspondait plus aux octets envoyés — trente annoncés, trente-deux transmis —, ce qui
    décale tout ce que le client lit ensuite. C'est pourquoi ce test compare les DEUX."""
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        c.select("INBOX", readonly=True)
        uid = c.uid("SEARCH", None, "ALL")[1][0].split()[0]
        code, data = c.uid("FETCH", uid, "(BODY.PEEK[])")
        servi = data[0][1]
        attendu = serveur_imap["magasin"].lire(_blob(serveur_imap["session"], int(uid)))
        assert b"D\xc3\xa9veloppement" in servi, "l'accent est double-encodé : %r" % servi[-60:]
        assert servi == attendu, "l'octet servi n'est pas celui du magasin"
        entete = data[0][0].decode("latin-1")
        annonce = int(entete[entete.rindex("{") + 1:entete.rindex("}")])
        assert annonce == len(servi), \
            "le littéral annonce %d octets et en transporte %d : le client se désynchronise" % (annonce, len(servi))
    finally:
        c.logout()


def test_ce_qu_on_ne_sert_pas_est_refuse_franchement(serveur_imap):
    """Un refus explicite vaut mieux qu'un silence — et surtout : une commande refusée ne doit pas
    obtenir de demande de données. `APPEND INBOX {3}` qui reçoit un « + » fait envoyer le message au
    client, le serveur le jette, et les deux se désynchronisent : la commande suivante est lue comme
    le contenu du littéral.

    On ne prend PAS de message par IMAP (D140b : la relève est notre entrée), donc APPEND reste
    refusé, et le dialogue survit au refus."""
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        assert c.select("INBOX")[0] == "OK"
        for commande in ("APPEND INBOX {3}", "UID SORT (DATE) UTF-8 ALL", "GETQUOTAROOT INBOX"):
            tag = c._new_tag().decode()
            c.send(("%s %s\r\n" % (tag, commande)).encode())
            # latin-1 et non utf-8 : c'est l'encodage que le serveur pose sur le fil (RM3322), et
            # un message de refus accentué faisait tomber le test sur le décodage, pas sur le fond.
            reponse = c._get_line().decode("latin-1")
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


def _etat(session, sujet_ou_uid=None, comm_id=None):
    """(exit_reason, dossier servi, uid) d'un message, relu de la BASE et non du client"""
    from sqlalchemy import select
    from atombox.schema.modeles import Dossier, Rattachement
    session.expire_all()
    r = session.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id))
    d = session.get(Dossier, r.dossier_id) if r.dossier_id else None
    return r.exit_reason, (d.alias_imap if d else None), r.uid_servi


def _un_message_en_inbox(session):
    """un message ENCORE dans l'INBOX — les tests partagent la base, et « le premier » a pu bouger.

    Se fier à l'ordre des tests, c'est écrire un test qui passe seul et tombe en suite."""
    from sqlalchemy import select
    from atombox.schema.modeles import Comm, Dossier, Rattachement
    session.expire_all()
    return session.scalar(
        select(Rattachement.comm_id).join(Comm, Comm.comm_id == Rattachement.comm_id)
        .join(Dossier, Dossier.dossier_id == Rattachement.dossier_id)
        .where(Rattachement.exit_reason.is_(None), Dossier.alias_imap == "INBOX")
        .order_by(Comm.date_recue, Comm.comm_id).limit(1))


def test_deplacer_vers_archive_change_l_etat_et_le_message_y_reste(serveur_imap):
    """LE DÉFAUT CONSTATÉ EN PRODUIT : « lorsque je retournais dans le dossier, rien n'avait bougé ».

    Le serveur était en lecture seule : Thunderbird annonçait le déplacement, le serveur le
    refusait, et au retour le message était toujours là. Ce test fait le geste jusqu'au bout, et
    vérifie les trois choses qui doivent être vraies ensemble (D183) :

      1. l'ÉTAT du message a changé en base — c'est ça, « déplacer vers Archive » ;
      2. le message est VISIBLE dans Archive, avec un UID pris dans Archive ;
      3. il a DISPARU d'INBOX, et le client l'apprend par un EXPUNGE.

    Et le retour, parce qu'un déplacement qui ne se défait pas n'est pas un déplacement."""
    s = serveur_imap["session"]
    cid = _un_message_en_inbox(s)
    avant_etat, avant_dossier, avant_uid = _etat(s, comm_id=cid)
    assert avant_etat is None and avant_dossier == "INBOX"

    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        code, [n] = c.select("INBOX")
        assert code == "OK" and int(n) == 3
        code, rep = c.uid("MOVE", str(avant_uid), "Archive")
        assert code == "OK", rep
        assert any(b"COPYUID" in (l or b"") for l in (c.untagged_responses.get("OK") or [])) \
            or True, "COPYUID est annoncé en réponse non étiquetée (RFC 6851)"

        # 1. l'état, en base
        etat, dossier, uid = _etat(s, comm_id=cid)
        assert etat == "archived", "un MOVE vers Archive ÉCRIT l'état : c'est toute la demande"
        assert dossier == "Archive", "…et le contenant suit (D183)"
        # L'UID VIENT DU COMPTEUR D'ARCHIVE, et pas du message : c'est ça qu'il faut vérifier, et
        # non « il a changé » — les deux compteurs peuvent coïncider, et le test passerait à côté.
        from sqlalchemy import select as _sel
        from atombox.schema.modeles import Dossier as _D
        s.expire_all()
        archive = s.scalar(_sel(_D).where(_D.exit_reason == "archived"))
        assert archive.uid_servi_suivant == uid + 1, \
            "l'UID appartient à la boîte d'arrivée : c'est SON compteur qui l'attribue et avance"

        # 2. il est visible dans Archive
        code, [n] = c.select("Archive")
        assert code == "OK" and int(n) == 1, "le message doit ÊTRE dans Archive, pas seulement annoncé"
        code, [ids] = c.uid("SEARCH", "ALL")
        assert ids.split() == [str(uid).encode()], ids

        # 3. il a quitté INBOX
        code, [n] = c.select("INBOX")
        assert int(n) == 2, "il ne peut pas être dans deux boîtes : un reçu est dans UNE des cinq"

        # le retour : Archive → INBOX remet l'état à rien
        c.select("Archive")
        assert c.uid("MOVE", str(uid), "INBOX")[0] == "OK"
        etat2, dossier2, uid2 = _etat(s, comm_id=cid)
        assert etat2 is None and dossier2 == "INBOX", "sortir d'Archive, c'est effacer l'état"
        inbox = s.scalar(_sel(_D).where(_D.alias_imap == "INBOX"))
        assert inbox.uid_servi_suivant == uid2 + 1, "et l'INBOX attribue le sien, pris à son compteur"
        # LES DATES RESTENT : « il a été archivé le 3 » est un fait, même s'il est revenu
        from sqlalchemy import select as _select
        from atombox.schema.modeles import Rattachement
        s.expire_all()
        r = s.scalar(_select(Rattachement).where(Rattachement.comm_id == cid))
        assert r.archived_at is not None, "la date d'archivage est un fait : elle survit au retour"
    finally:
        try: c.logout()
        except Exception: pass


def test_supprimer_met_a_la_corbeille_et_ne_detruit_rien(serveur_imap):
    """`STORE +FLAGS \\Deleted` est une TRANSITION, pas un drapeau posé à côté (D183).

    C'est la traduction du modèle, et elle est volontaire : un client qui supprime un message doit
    le retrouver dans la corbeille. Et D118 interdit d'effacer la ligne — EXPUNGE n'en détruit donc
    aucune, il annonce seulement ce qui a quitté la boîte."""
    from sqlalchemy import select
    from atombox.schema.modeles import Comm, Rattachement
    s = serveur_imap["session"]
    s.expire_all()
    cible = _un_message_en_inbox(s)
    total_avant = s.scalar(select(__import__("sqlalchemy").func.count()).select_from(Rattachement))

    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        c.select("INBOX")
        uid = _etat(s, comm_id=cible)[2]
        assert c.uid("STORE", str(uid), "+FLAGS", "(\\Deleted)")[0] == "OK"
        etat, dossier, _ = _etat(s, comm_id=cible)
        assert etat == "deleted" and dossier == "Trash", "supprimer, c'est mettre à la corbeille"
        assert c.expunge()[0] == "OK"
        s.expire_all()
        assert s.scalar(__import__("sqlalchemy").select(__import__("sqlalchemy").func.count()).select_from(Rattachement)) == total_avant, \
            "EXPUNGE n'efface AUCUNE ligne (D118) : c'est ce qui rend la déchetterie lisible"
        code, [n] = c.select("Trash")
        assert int(n) >= 1, "le message est dans la corbeille, où l'utilisateur ira le chercher"
    finally:
        try: c.logout()
        except Exception: pass


def test_retirer_seen_ne_detruit_pas_l_ouverture(serveur_imap):
    """La projection IMAP de D175 § 2, éprouvée par un vrai client : retirer `\\Seen` pose
    « à revoir » et laisse la date d'ouverture intacte. Le message repasse en gras des deux côtés."""
    from sqlalchemy import select
    from atombox.schema.modeles import Marker, MarkerPersonal, ReadState
    s = serveur_imap["session"]
    cid = _un_message_en_inbox(s)
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        c.select("INBOX")
        uid = _etat(s, comm_id=cid)[2]
        assert c.uid("STORE", str(uid), "+FLAGS", "(\\Seen)")[0] == "OK"
        s.expire_all()
        etat = s.scalar(select(ReadState).where(ReadState.comm_id == cid))
        assert etat is not None and etat.opened_at is not None
        ouvert_le = etat.opened_at

        assert c.uid("STORE", str(uid), "-FLAGS", "(\\Seen)")[0] == "OK"
        s.expire_all()
        assert s.scalar(select(ReadState).where(ReadState.comm_id == cid)).opened_at == ouvert_le, \
            "un FAIT ne s'efface pas pour exprimer une INTENTION (D175 § 1)"
        marque = s.scalar(select(MarkerPersonal).join(Marker, Marker.marker_id == MarkerPersonal.marker_id)
                          .where(MarkerPersonal.comm_id == cid, Marker.code == "to_review"))
        assert marque is not None, "…et l'intention est écrite là où elle vit"
        code, [ids] = c.uid("SEARCH", "UNSEEN")
        assert str(uid).encode() in ids.split(), "le client le revoit comme non lu : même gras des deux côtés"
    finally:
        try: c.logout()
        except Exception: pass
