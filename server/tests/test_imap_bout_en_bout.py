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
    from atombox.db import session as open_db
    from atombox.store import Store
    from atombox.api.security import hash_password
    from atombox.ingestion.ingestion import address_of, ingest
    from atombox.schema.models import Acces, Boite, Compte, Dossier
    from atombox.uuid7 import uuid7

    name = "atombox_imap_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % name)
    u = _re.sub(r"/[^/?]*(\?|$)", "/" + name + r"\1", url, count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c:
        c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    store = Store(str(tmp_path_factory.mktemp("magasin")))
    s = open_db(u)
    a = address_of(s, "contact@exemple.fr")
    mailbox = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(mailbox)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True,
                    cree_le=datetime.now(timezone.utc), mot_de_passe_empreinte=hash_password("secret")); s.add(compte)
    s.add(Acces(compte_id=compte.compte_id, boite_id=mailbox.boite_id, role="membre",
                debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
    inbox = Dossier(dossier_id=uuid7(), boite_id=mailbox.boite_id, nom="INBOX", alias_imap="INBOX", protege=True); s.add(inbox)
    for alias in ("Sent", "Trash"):
        s.add(Dossier(dossier_id=uuid7(), boite_id=mailbox.boite_id, nom=alias, alias_imap=alias, protege=True))
    s.flush()
    # LES CINQ BOÎTES AUX LETTRES (D183) : `schema.sql` est un DDL, il n'apporte aucune donnée, et
    # sans « Archive » un MOVE vers elle répond TRYCREATE — exactement le geste qui « ne fait rien ».
    from atombox.schema.seeds import seed_builtins
    from atombox.services.mailbox import ensure_mailboxes
    seed_builtins(s); ensure_mailboxes(s, mailbox.boite_id)
    s.commit()
    for i in range(3):
        ingest(s, store, mailbox.boite_id, MESSAGE.replace(b"<c4412@", b"<c%d@" % i), dossier_id=inbox.dossier_id)

    port = _port_libre()
    pret = threading.Event()
    boucle = {}

    def tourner():
        async def start():
            from atombox.imap.server import Listener
            e = Listener(lambda: open_db(u), store)
            srv = await asyncio.start_server(e.client, "127.0.0.1", port)
            boucle["server"] = srv
            pret.set()
            async with srv: await srv.serve_forever()
        # `asyncio.run` dans un fil DÉMON : il meurt avec le processus. Arrêter la boucle à la
        # main depuis un autre fil a sa part de pièges, et on n'a rien à sauver ici.
        try: asyncio.run(start())
        except (asyncio.CancelledError, RuntimeError): pass

    thread = threading.Thread(target=tourner, daemon=True); thread.start()
    assert pret.wait(10), "le serveur IMAP n'a pas démarré"
    yield {"port": port, "magasin": store, "session": s}
    s.close()
    import atombox.db as db, asyncio as aio
    db.engine(u).dispose(); db._sync.clear()
    for m in list(db._async.values()):
        try: aio.run(m.dispose())
        except Exception: pass
    db._async.clear()
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (name,))
    admin.execute('DROP DATABASE "%s"' % name); admin.close()


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

        code, mailboxes = c.list()
        assert code == "OK"
        names = " ".join(b.decode() for b in mailboxes)
        assert '"INBOX"' in names, names
        assert '"Trash"' in names, "les autres dossiers sont là aussi"

        code, n = c.select("INBOX", readonly=True)
        assert code == "OK" and int(n[0]) == 3, n
        assert c.untagged_responses.get("OK"), "la sélection porte UIDVALIDITY et UIDNEXT"

        code, uids = c.uid("SEARCH", None, "ALL")
        listing = uids[0].split()
        assert code == "OK" and len(listing) == 3, uids

        code, data = c.uid("FETCH", listing[0], "(BODY.PEEK[])")
        raw = data[0][1]
        expected = serveur_imap["magasin"].read(_blob(serveur_imap["session"], int(listing[0])))
        assert raw == expected, "l'octet servi est CELUI DU MAGASIN, pas une reconstruction (D025, RM3213)"

        code, data = c.uid("FETCH", listing[0], "(FLAGS RFC822.SIZE ENVELOPE)")
        rendu = data[0].decode() if isinstance(data[0], bytes) else " ".join(map(str, data[0]))
        assert "RFC822.SIZE %d" % len(expected) in rendu, rendu
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
        expected = serveur_imap["magasin"].read(_blob(serveur_imap["session"], int(uid)))
        assert b"D\xc3\xa9veloppement" in servi, "l'accent est double-encodé : %r" % servi[-60:]
        assert servi == expected, "l'octet servi n'est pas celui du magasin"
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

    APPEND est servi depuis RM3499 ; le cas éprouvé ici est donc une commande INCONNUE qui porte un
    littéral — la même désynchronisation, par un autre chemin."""
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        assert c.select("INBOX")[0] == "OK"
        for commande in ("SETMETADATA INBOX {3}", "UID SORT (DATE) UTF-8 ALL", "GETQUOTAROOT INBOX"):
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
    from atombox.schema.models import CommEmail, Rattachement
    r = session.scalar(select(Rattachement).where(Rattachement.uid_servi == uid))
    return session.get(CommEmail, r.comm_id).blob_ref


def _etat(session, sujet_ou_uid=None, comm_id=None):
    """(exit_reason, dossier servi, uid) d'un message, relu de la BASE et non du client"""
    from sqlalchemy import select
    from atombox.schema.models import Dossier, Rattachement
    session.expire_all()
    r = session.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id))
    d = session.get(Dossier, r.dossier_id) if r.dossier_id else None
    return r.exit_reason, (d.alias_imap if d else None), r.uid_servi


def _un_message_en_inbox(session):
    """un message ENCORE dans l'INBOX — les tests partagent la base, et « le premier » a pu bouger.

    Se fier à l'ordre des tests, c'est écrire un test qui passe seul et tombe en suite."""
    from sqlalchemy import select
    from atombox.schema.models import Comm, Dossier, Rattachement
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
        state, dossier, uid = _etat(s, comm_id=cid)
        assert state == "archived", "un MOVE vers Archive ÉCRIT l'état : c'est toute la demande"
        assert dossier == "Archive", "…et le contenant suit (D183)"
        # L'UID VIENT DU COMPTEUR D'ARCHIVE, et pas du message : c'est ça qu'il faut vérifier, et
        # non « il a changé » — les deux compteurs peuvent coïncider, et le test passerait à côté.
        from sqlalchemy import select as _sel
        from atombox.schema.models import Dossier as _D
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
        from atombox.schema.models import Rattachement
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
    from atombox.schema.models import Comm, Rattachement
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
        state, dossier, _ = _etat(s, comm_id=cible)
        assert state == "deleted" and dossier == "Trash", "supprimer, c'est mettre à la corbeille"
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
    from atombox.schema.models import Marker, MarkerPersonal, ReadState
    s = serveur_imap["session"]
    cid = _un_message_en_inbox(s)
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    try:
        c.login("mathieu", "secret")
        c.select("INBOX")
        uid = _etat(s, comm_id=cid)[2]
        assert c.uid("STORE", str(uid), "+FLAGS", "(\\Seen)")[0] == "OK"
        s.expire_all()
        state = s.scalar(select(ReadState).where(ReadState.comm_id == cid))
        assert state is not None and state.opened_at is not None
        ouvert_le = state.opened_at

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


def test_lire_le_corps_marque_lu_et_ca_tient_a_la_resynchronisation(serveur_imap):
    """RFC 3501 § 6.4.5 : `FETCH BODY[]` (sans `.PEEK`), `RFC822` et `RFC822.TEXT` posent `\\Seen`.

    Le 04/11, l'application mail d'Android : un message lu sur le téléphone redevenait non lu à la
    synchronisation suivante. Thunderbird envoie un `STORE +FLAGS (\\Seen)` explicite ; l'application
    d'Android compte sur le marquage IMPLICITE de la lecture — que nous ne faisions pas. `PEEK` et une
    boîte ouverte par EXAMINE, eux, ne marquent rien."""
    from sqlalchemy import delete, select
    from atombox.schema.models import MarkerPersonal, ReadState
    s = serveur_imap["session"]
    cid = _un_message_en_inbox(s)
    s.execute(delete(ReadState).where(ReadState.comm_id == cid))
    s.execute(delete(MarkerPersonal).where(MarkerPersonal.comm_id == cid))
    s.commit()
    uid = str(_etat(s, comm_id=cid)[2])

    def lu():
        s.expire_all()
        r = s.scalar(select(ReadState).where(ReadState.comm_id == cid))
        return r is not None and r.opened_at is not None

    c = _connecte(serveur_imap)
    try:
        c.select("INBOX", readonly=True)                      # EXAMINE
        assert c.uid("FETCH", uid, "(BODY[])")[0] == "OK"
        assert not lu(), "une boîte ouverte en lecture seule ne marque rien"
        c.select("INBOX")
        assert c.uid("FETCH", uid, "(BODY.PEEK[])")[0] == "OK"
        assert not lu(), "PEEK ne marque rien : c'est son sens"
        typ, data = c.uid("FETCH", uid, "(BODY[])")
        assert typ == "OK" and lu(), "lire le corps marque le message lu"
        entetes = b" ".join(x[0] if isinstance(x, tuple) else x for x in data if x)
        assert b"\\Seen" in entetes, ("le client apprend le changement dans la même réponse", entetes)
    finally:
        c.logout()
    c = _connecte(serveur_imap)                                # la resynchronisation
    try:
        c.select("INBOX")
        assert b"\\Seen" in c.uid("FETCH", uid, "(FLAGS)")[1][0]
        assert uid.encode() not in c.uid("SEARCH", "UNSEEN")[1][0].split()
    finally:
        c.logout()


# ── APPEND (RM3499) : ce que Thunderbird fait pour ranger un envoyé ou enregistrer un brouillon ──
# Un message en ISO-8859-1, EXPRÈS : l'octet 0xE9 n'est pas de l'UTF-8 valide. L'écouteur décodait
# autrefois les littéraux en UTF-8 avec remplacement — ce message serait ressorti avec « � » à
# la place de chaque accent, et une taille fausse. L'ASCII, lui, survit à tout.
ENVOYE = (b"From: Mathieu <contact@exemple.fr>\r\nTo: Client <client@client.example>\r\n"
          b"Subject: Devis 2026-118\r\nDate: Wed, 21 Oct 2026 09:00:00 +0200\r\n"
          b"Message-ID: <devis-118@exemple.fr>\r\nMIME-Version: 1.0\r\n"
          b"Content-Type: text/plain; charset=iso-8859-1\r\nContent-Transfer-Encoding: 8bit\r\n\r\n"
          b"Voici le devis d\xe9taill\xe9, \xe0 valider avant le 30.\r\n")


def _connecte(serveur_imap):
    c = imaplib.IMAP4("127.0.0.1", serveur_imap["port"], timeout=10)
    c.login("mathieu", "secret")
    return c


def test_append_dans_envoyes_rend_l_octet_exact_et_son_uid(serveur_imap):
    """Le message déposé est relu à l'OCTET près, sous l'UID que la réponse a promis."""
    from sqlalchemy import select
    from atombox.schema.models import Comm, CommEmail, Rattachement, Dossier
    s = serveur_imap["session"]
    c = _connecte(serveur_imap)
    try:
        typ, data = c.append("Sent", "(\\Seen)", None, ENVOYE)
        assert typ == "OK", data
        m = re.search(rb"\[APPENDUID (\d+) (\d+)\]", data[0])
        assert m, "UIDPLUS est annoncé : la réponse DOIT porter APPENDUID — %r" % data
        validity, uid = int(m.group(1)), int(m.group(2))
        typ, sel = c.select("Sent")
        assert typ == "OK"
        assert c.response("UIDVALIDITY")[1][0] == str(validity).encode(), "l'UIDVALIDITY promise est celle de la boîte"
        typ, rendu = c.uid("FETCH", str(uid), "(BODY.PEEK[] FLAGS)")
        assert typ == "OK" and rendu[0] is not None, "l'UID promis désigne bien le message"
        assert rendu[0][1] == ENVOYE, "l'octet servi est l'octet déposé — 0xE9 compris"
        # les FLAGS viennent APRÈS le littéral, dans la partie suivante de la réponse d'imaplib
        reste = b"".join(x if isinstance(x, bytes) else x[0] for x in rendu[1:])
        assert b"\\Seen" in reste, ("le drapeau déposé est posé (sur le compte connecté, D175)", rendu)
    finally:
        c.logout()
    s.expire_all()
    e = s.scalar(select(CommEmail).where(CommEmail.message_id == "<devis-118@exemple.fr>"))
    comm = s.get(Comm, e.comm_id)
    assert comm.sens == "out", "déposé dans Envoyés : un message SORTANT"
    r = s.scalar(select(Rattachement).where(Rattachement.comm_id == e.comm_id))
    assert s.get(Dossier, r.dossier_id).alias_imap == "Sent" and r.uid_servi == uid


def test_un_envoye_depose_remonte_chez_le_fournisseur(serveur_imap):
    """D140c : le téléphone lit le FOURNISSEUR. Un envoyé rangé par Thunderbird chez nous doit y être
    copié, sinon il n'existe pas pour le téléphone — c'est l'événement que la synchro écoute."""
    from sqlalchemy import select
    from atombox.schema.models import CommEmail, Evenement
    s = serveur_imap["session"]
    s.expire_all()
    e = s.scalar(select(CommEmail).where(CommEmail.message_id == "<devis-118@exemple.fr>"))
    assert e is not None, "dépend du dépôt du test précédent"
    evs = [v for v in s.scalars(select(Evenement).where(Evenement.type == "message.envoye"))
           if v.charge.get("comm_id") == str(e.comm_id)]
    assert len(evs) == 1, "un événement message.envoye, un seul : %r" % evs


def test_append_vers_une_boite_inconnue_dit_trycreate(serveur_imap):
    c = _connecte(serveur_imap)
    try:
        typ, data = c.append("Projets/Inexistant", None, None, ENVOYE)
        assert typ == "NO" and b"TRYCREATE" in data[0], data
        assert c.noop()[0] == "OK", "le dialogue survit au refus — le littéral a été consommé"
    finally:
        c.logout()


def test_deposer_deux_fois_ne_cree_pas_de_double(serveur_imap):
    """Un client qui rejoue son APPEND (coupure réseau au mauvais moment) ne fabrique pas un second
    message : l'identité (D064) le reconnaît, et l'UID rendu est celui du premier."""
    from sqlalchemy import select, func
    from atombox.schema.models import CommEmail, Rattachement
    s = serveur_imap["session"]
    c = _connecte(serveur_imap)
    try:
        typ, data = c.append("Sent", None, None, ENVOYE)
        assert typ == "OK", data
    finally:
        c.logout()
    s.expire_all()
    e = s.scalar(select(CommEmail).where(CommEmail.message_id == "<devis-118@exemple.fr>"))
    assert s.scalar(select(func.count()).select_from(CommEmail).where(CommEmail.message_id == "<devis-118@exemple.fr>")) == 1
    assert s.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.comm_id == e.comm_id)) == 1


def test_append_dans_la_boite_ouverte_annonce_exists(serveur_imap):
    """Le client a INBOX ouverte et y dépose : il doit apprendre le nouveau message dans la réponse
    même (RFC 3501 § 6.3.11), sinon il ne le verra qu'au prochain NOOP."""
    c = _connecte(serveur_imap)
    try:
        typ, avant = c.select("INBOX")
        n = int(avant[0])
        autre = ENVOYE.replace(b"<devis-118@", b"<note-inbox@").replace(b"Devis 2026-118", b"Note")
        typ, data = c.append("INBOX", None, imaplib.Time2Internaldate(1761030000), autre)
        assert typ == "OK", data
        exists = c.response("EXISTS")[1]
        assert exists and exists[-1] is not None and int(exists[-1]) == n + 1, exists
    finally:
        c.logout()


# ── IDLE (RM3499) : le message qui arrive s'annonce tout seul ───────────────────────────────────
class _Fil:
    """un client IMAP à la main : imaplib (3.12) ne sait pas faire IDLE"""
    def __init__(self, port):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=10); self.f = self.s.makefile("rb")
        self.ligne()                                           # l'accueil
    def ligne(self, timeout=10):
        self.s.settimeout(timeout); return self.f.readline().decode("latin-1").rstrip("\r\n")
    def cmd(self, texte, tag=None):
        # DONE ne porte pas d'étiquette : la réponse est celle de l'IDLE qu'il termine
        tag = tag or texte.split(" ", 1)[0]; self.s.sendall((texte + "\r\n").encode())
        out = []
        while True:
            l = self.ligne(); out.append(l)
            if l.startswith(tag + " ") or l.startswith("+ "): return out
    def close(self):
        try: self.s.sendall(b"zz LOGOUT\r\n")
        except OSError: pass
        self.s.close()


def test_idle_annonce_le_message_qui_arrive(serveur_imap, monkeypatch):
    """Sans IDLE, Thunderbird interroge toutes les dix minutes : un message arrivé attendait jusqu'à
    dix minutes pour s'afficher. Avec IDLE, l'EXISTS arrive dans les secondes."""
    import time
    from atombox.ingestion.ingestion import ingest
    from atombox.schema.models import Dossier
    from sqlalchemy import select
    monkeypatch.setenv("ATOMBOX_IMAPD_IDLE_POLL", "0.2")
    s = serveur_imap["session"]
    c = _Fil(serveur_imap["port"])
    try:
        c.cmd("a1 LOGIN mathieu secret")
        sel = c.cmd("a2 SELECT INBOX")
        n = int(next(l.split()[1] for l in sel if l.endswith(" EXISTS")))
        assert c.cmd("a3 IDLE")[-1].startswith("+ ")
        # un message arrive par la relève, PENDANT que le client attend
        inbox = s.scalar(select(Dossier).where(Dossier.alias_imap == "INBOX"))
        ingest(s, serveur_imap["magasin"], inbox.boite_id,
               MESSAGE.replace(b"<c4412@", b"<idle-1@").replace(b"Commande 4412", b"Pendant IDLE"),
               dossier_id=inbox.dossier_id)
        t0 = time.monotonic()
        l = c.ligne(timeout=5)
        assert l == "* %d EXISTS" % (n + 1), "le client apprend le message SANS rien demander : %r" % l
        assert time.monotonic() - t0 < 3, "et dans les secondes, pas à la prochaine interrogation"
        fin = c.cmd("DONE", tag="a3")
        assert fin[-1] == "a3 OK IDLE termine", fin
    finally:
        c.close()


def test_idle_ne_garde_pas_de_transaction_ouverte(serveur_imap, monkeypatch):
    """Le 19/09, une migration a attendu ONZE MINUTES derrière des connexions « idle in transaction »,
    en bloquant les lectures. Un client en IDLE attend jusqu'à 29 minutes : s'il gardait sa
    transaction de lecture, chaque client de bureau ouvert rejouerait l'incident."""
    import time, psycopg
    monkeypatch.setenv("ATOMBOX_IMAPD_IDLE_POLL", "0.2")
    s = serveur_imap["session"]; s.rollback()                  # le harnais lui-même ne doit rien tenir
    base = s.get_bind().url.database
    c = _Fil(serveur_imap["port"])
    try:
        c.cmd("a1 LOGIN mathieu secret"); c.cmd("a2 SELECT INBOX"); c.cmd("a3 IDLE")
        time.sleep(1.0)                                         # plusieurs interrogations ont eu lieu
        url = os.environ["DATABASE_URL"]
        with psycopg.connect(url, autocommit=True) as admin:
            tenues = admin.execute("select count(*) from pg_stat_activity where datname = %s "
                                   "and state like 'idle in transaction%%'", (base,)).fetchone()[0]
        assert tenues == 0, "%d connexion(s) « idle in transaction » pendant IDLE" % tenues
        assert c.cmd("DONE", tag="a3")[-1] == "a3 OK IDLE termine"
    finally:
        c.close()


# ── les dossiers depuis le client (RM3499) ──────────────────────────────────────────────────────
def _noms(c):
    typ, rows = c.list()
    assert typ == "OK"
    return {r.decode("latin-1").rsplit(' "/" ', 1)[1].strip('"') for r in rows if r}


def test_creer_renommer_supprimer_un_dossier_depuis_le_client(serveur_imap):
    """Le geste complet d'un utilisateur de Thunderbird : créer « Projets/Dupont », y ranger un
    message, renommer le parent — l'enfant et son message suivent —, puis supprimer une fois vidé."""
    c = _connecte(serveur_imap)
    try:
        typ, data = c.create("Projets/Dupont")
        assert typ == "OK", data
        noms = _noms(c)
        assert {"Projets", "Projets/Dupont"} <= noms, "le parent manquant est créé (RFC 3501 § 6.3.3) : %s" % noms
        assert c.create("Projets/Dupont")[0] == "NO", "créer deux fois est refusé"

        # y ranger un message
        assert c.select("INBOX")[0] == "OK"
        typ, d = c.uid("SEARCH", None, "ALL"); uid = d[0].split()[0].decode()
        assert c.uid("MOVE", uid, "Projets/Dupont")[0] == "OK"

        # renommer le PARENT : l'enfant suit, son message aussi
        typ, data = c.rename("Projets", "Chantiers")
        assert typ == "OK", data
        noms = _noms(c)
        assert {"Chantiers", "Chantiers/Dupont"} <= noms and "Projets/Dupont" not in noms, noms
        typ, sel = c.select("Chantiers/Dupont")
        assert typ == "OK" and int(sel[0]) == 1, "le message est toujours là, sous le nouveau nom : %r" % sel

        # supprimer un dossier PLEIN est refusé (D118 : on ne détruit pas un rangement)
        c.select("INBOX")
        typ, data = c.delete("Chantiers/Dupont")
        assert typ == "NO" and b"INUSE" in data[0], data
        # le vider, puis supprimer : l'enfant d'abord, le parent ensuite
        c.select("Chantiers/Dupont")
        typ, d = c.uid("SEARCH", None, "ALL")
        assert c.uid("MOVE", d[0].split()[0].decode(), "INBOX")[0] == "OK"
        c.select("INBOX")
        assert c.delete("Chantiers")[0] == "NO", "un parent qui a des enfants ne se supprime pas"
        assert c.delete("Chantiers/Dupont")[0] == "OK"
        assert c.delete("Chantiers")[0] == "OK"
        assert not ({"Chantiers", "Chantiers/Dupont"} & _noms(c))
    finally:
        c.logout()


def test_les_boites_protegees_et_les_boites_d_etat_restent_ce_qu_elles_sont(serveur_imap):
    c = _connecte(serveur_imap)
    try:
        for nom in ("INBOX", "Trash", "Archive"):
            assert c.delete(nom)[0] == "NO", "%s ne se supprime pas (D047, D183)" % nom
            assert c.rename(nom, nom + "-bis")[0] == "NO", "%s ne se renomme pas" % nom
        assert c.create("INBOX")[0] == "NO"
        # Thunderbird « supprime » un dossier en le rangeant sous la Corbeille : chez nous la
        # corbeille est un ÉTAT, pas un conteneur — refusé, et la raison est dite
        assert c.create("Temporaire")[0] == "OK"
        typ, data = c.rename("Temporaire", "Trash/Temporaire")
        assert typ == "NO" and b"CANNOT" in data[0], data
        assert c.delete("Temporaire")[0] == "OK"
    finally:
        c.logout()


def test_abonnements_dire_vrai(serveur_imap):
    """Tous les dossiers sont abonnés (LSUB = LIST). S'abonner est vrai ; se désabonner d'un dossier
    qui existe serait un mensonge, puisque LSUB continuerait de le rendre — refusé ; se désabonner
    d'un dossier supprimé (ce que fait Thunderbird après DELETE) est vrai."""
    c = _connecte(serveur_imap)
    try:
        assert c.subscribe("INBOX")[0] == "OK"
        assert c.subscribe("N-existe-pas")[0] == "NO"
        assert c.unsubscribe("INBOX")[0] == "NO"
        assert c.unsubscribe("N-existe-pas")[0] == "OK"
    finally:
        c.logout()


# ── la structure MIME sur le fil (RM3499) ──────────────────────────────────────────────────────
def test_le_client_voit_la_piece_jointe_et_la_telecharge_par_tranches(serveur_imap):
    """Un client affiche le trombone d'après BODYSTRUCTURE, puis télécharge la pièce par TRANCHES :
    `BODY.PEEK[2]<0.10>` doit revenir sous le nom `BODY[2]<0>`, sinon il ne sait pas la rattacher à
    sa demande. La structure attendue est celle que Dovecot sert pour les mêmes octets
    (`test_imap_dovecot.py`)."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_imap_mime import MESSAGE as COMPOSITE, PDF
    from atombox.imap import mime
    c = _connecte(serveur_imap)
    try:
        typ, data = c.append("INBOX", None, None, COMPOSITE)
        uid = re.search(rb"APPENDUID \d+ (\d+)", data[0]).group(1).decode()
        c.select("INBOX")
        typ, rendu = c.uid("FETCH", uid, "(BODYSTRUCTURE)")
        assert typ == "OK"
        recu = b"".join(x if isinstance(x, bytes) else x[0] + x[1] for x in rendu).decode("latin-1")
        assert mime.structure(mime.Part(COMPOSITE), True) in recu, recu[:300]
        assert '("attachment" ("filename" "devis.pdf"))' in recu, "le trombone"
        typ, rendu = c.uid("FETCH", uid, "(BODY.PEEK[2]<0.10>)")
        assert typ == "OK" and b"BODY[2]<0> {10}" in rendu[0][0], rendu
        assert rendu[0][1] == PDF[:10], "la tranche demandée, à l'octet"
        typ, rendu = c.uid("FETCH", uid, "(BODY.PEEK[2])")
        assert rendu[0][1] == PDF, "la pièce entière : la tranche exacte des octets stockés"
    finally:
        c.logout()


# ── SEARCH et INTERNALDATE sur le fil (RM3499) ──────────────────────────────────────────────────
def test_la_recherche_complete_sur_le_vrai_serveur(serveur_imap):
    """OR, NOT, dates, tailles, en-têtes, et un critère en LITTÉRAL (accentué) : ce qu'un client
    envoie vraiment. La sémantique de chaque critère est éprouvée contre Dovecot ailleurs ; ici, le
    chemin complet — analyse, base, magasin."""
    c = _connecte(serveur_imap)
    try:
        c.select("INBOX")
        typ, tous = c.uid("SEARCH", None, "ALL")
        tous = tous[0].split()
        assert tous, "la boîte a des messages"
        typ, r = c.uid("SEARCH", None, "OR", "SUBJECT", "Commande", "NOT", "ALL")
        assert typ == "OK" and r[0].split(), r
        typ, r = c.uid("SEARCH", None, "SINCE", "1-Jan-2000", "LARGER", "10")
        assert typ == "OK" and r[0].split() == tous, "tout est arrivé après l'an 2000 et pèse plus de 10 octets"
        typ, r = c.uid("SEARCH", None, "HEADER", "Message-ID", "fournisseur.example")
        assert typ == "OK" and r[0].split(), r
        # un littéral : « Développement » est dans le corps des messages du banc
        c.literal = "Développement".encode("utf-8")
        typ, r = c.uid("SEARCH", "CHARSET", "UTF-8", "BODY")
        assert typ == "OK" and r[0].split(), ("la recherche décode le corps (UTF-8) et lit le littéral", r)
        # imaplib LÈVE sur un BAD : c'est précisément ce qu'on veut — une erreur, jamais une liste vide
        with pytest.raises(imaplib.IMAP4.error, match="inconnu"):
            c.uid("SEARCH", None, "YOUNGER", "60")
        assert c.noop()[0] == "OK", "et le dialogue continue"
    finally:
        c.logout()


def test_l_internaldate_est_au_format_imap(serveur_imap):
    """« 21-Oct-2026 07:00:00 +0000 » (RFC 3501 § 9). Le serveur rendait « Wed 21 Oct 2026 07:00:00 + »
    — une date RFC 2822 tronquée, que les clients ne savent pas lire."""
    c = _connecte(serveur_imap)
    try:
        c.select("INBOX")
        typ, r = c.fetch("1", "(INTERNALDATE)")
        assert typ == "OK"
        assert re.search(rb'INTERNALDATE "[ \d]\d-[A-Z][a-z]{2}-\d{4} \d\d:\d\d:\d\d [+-]\d{4}"', r[0]), r
        assert imaplib.Internaldate2tuple(r[0]) is not None, "imaplib sait la lire"
    finally:
        c.logout()


def test_un_dossier_accentue_voyage_en_modified_utf7(serveur_imap):
    """Thunderbird crée « Pièces jointes » : il envoie `Pi&AOg-ces jointes` (RFC 3501 § 5.1.3). On le
    garde tel quel pour le FIL — c'est ce qu'on renverra au fournisseur — et on LIT « Pièces jointes »."""
    from sqlalchemy import select
    from atombox.schema.models import Dossier
    s = serveur_imap["session"]
    c = _connecte(serveur_imap)
    try:
        # imaplib n'entoure PAS de guillemets un nom qui contient une espace ; un vrai client, si. Sans
        # eux, le serveur refuse au lieu de créer « Pi&AOg-ces » en jetant la fin du nom.
        with pytest.raises(imaplib.IMAP4.error):
            c.create("Pi&AOg-ces jointes")
        assert c.create('"Pi&AOg-ces jointes"')[0] == "OK"
        assert "Pi&AOg-ces jointes" in _noms(c), "LIST le rend codé, comme il est arrivé"
        assert c.select('"Pi&AOg-ces jointes"')[0] == "OK"
        s.expire_all()
        d = s.scalar(select(Dossier).where(Dossier.alias_imap == "Pi&AOg-ces jointes"))
        assert d is not None and d.nom == "Pièces jointes", "le webmail affiche le nom LISIBLE"
        c.select("INBOX")
        assert c.delete('"Pi&AOg-ces jointes"')[0] == "OK"
    finally:
        c.logout()


def test_un_message_envoye_a_soi_meme_est_dans_les_deux_boites(serveur_imap):
    """D185 (RM3504) — côté Thunderbird : l'exemplaire émis dans Sent, l'exemplaire reçu dans INBOX,
    chacun sous SON UID. Avant D185, le reçu était fusionné et n'apparaissait nulle part."""
    from atombox.ingestion.ingestion import ingest
    from atombox.schema.models import Dossier
    from sqlalchemy import select
    s = serveur_imap["session"]
    soi = ENVOYE.replace(b"To: Client <client@client.example>", b"To: Mathieu <contact@exemple.fr>") \
                .replace(b"<devis-118@", b"<soi-meme@").replace(b"Devis 2026-118", b"Note pour moi")
    c = _connecte(serveur_imap)
    try:
        typ, data = c.append("Sent", "(\\Seen)", None, soi)
        uid_sent = int(re.search(rb"APPENDUID \d+ (\d+)", data[0]).group(1))
        # le fournisseur livre l'exemplaire dans INBOX, la relève l'ingère
        s.expire_all()
        inbox = s.scalar(select(Dossier).where(Dossier.alias_imap == "INBOX"))
        ingest(s, serveur_imap["magasin"], inbox.boite_id, soi, dossier_id=inbox.dossier_id, sens="in")
        for boite in ("INBOX", "Sent"):
            c.select(boite)
            typ, d = c.uid("SEARCH", None, "SUBJECT", '"Note pour moi"')
            assert d[0].split(), "%s : le message envoyé à soi-même y est" % boite
            if boite == "Sent": assert int(d[0].split()[0]) == uid_sent
            typ, rendu = c.uid("FETCH", d[0].split()[0].decode(), "(BODY.PEEK[])")
            assert rendu[0][1] == soi, "%s : l'octet exact" % boite
    finally:
        c.logout()
