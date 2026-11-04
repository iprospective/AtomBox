"""RM3499 — le serveur IMAP chiffre, ou refuse de servir sur le réseau.

Le 20/10, mesuré : l'écouteur servait 10.0.3.11:1143 EN CLAIR, et la session, qui se croyait sous
TLS, acceptait LOGIN et AUTH=PLAIN sans rien annoncer. Ces tests éprouvent les trois morceaux qui
le rendent impossible : le transport (TLS implicite, avec un vrai client `imaplib`), la garde de
démarrage, et l'honnêteté de CAPABILITY.

Ils ne demandent pas de base : la poignée de main, l'accueil et CAPABILITY ne la touchent pas.
"""
from __future__ import annotations
import asyncio
import imaplib
import pathlib
import socket
import ssl
import threading

import pytest

from atombox.imap.server import Listener, check_transport, tls_context

ICI = pathlib.Path(__file__).resolve().parent
CERT = ICI / "fixtures" / "tls" / "test-only.crt"
KEY = ICI / "fixtures" / "tls" / "test-only.key"


def _port_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def ecouteur_tls():
    port = _port_libre()
    pret = threading.Event()

    def tourner():
        async def start():
            ctx = tls_context(str(CERT), str(KEY))
            # pas de base : rien de ce qu'on éprouve ici ne la touche
            e = Listener(lambda: None, None, tls=True)
            srv = await asyncio.start_server(e.client, "127.0.0.1", port, ssl=ctx)
            pret.set()
            async with srv: await srv.serve_forever()
        try: asyncio.run(start())
        except (asyncio.CancelledError, RuntimeError): pass

    threading.Thread(target=tourner, daemon=True).start()
    assert pret.wait(10), "l'écouteur TLS n'a pas démarré"
    return port


def _client_qui_fait_confiance():
    """un client qui fait confiance au certificat de TEST — et à lui seul"""
    ctx = ssl.create_default_context(cafile=str(CERT))
    return ctx


def test_un_vrai_client_parle_tls_au_serveur(ecouteur_tls):
    c = imaplib.IMAP4_SSL("127.0.0.1", ecouteur_tls, ssl_context=_client_qui_fait_confiance(), timeout=10)
    try:
        assert c.sock.version() in ("TLSv1.2", "TLSv1.3"), c.sock.version()
        typ, caps = c.capability()
        assert typ == "OK"
        annoncees = caps[0].decode().split()
        assert "AUTH=PLAIN" in annoncees
        # rien à négocier : le chiffrement est déjà là, et STARTTLS n'est servi par aucune commande
        assert "STARTTLS" not in annoncees and "LOGINDISABLED" not in annoncees
    finally:
        c.logout()


def test_un_client_en_clair_n_obtient_rien_du_port_tls(ecouteur_tls):
    """le port TLS ne répond JAMAIS en clair : pas d'accueil lisible, donc pas de mot de passe envoyé"""
    with socket.create_connection(("127.0.0.1", ecouteur_tls), timeout=5) as s:
        s.sendall(b"a1 CAPABILITY\r\n")
        s.settimeout(3)
        try:
            recu = s.recv(4096)
        except (socket.timeout, ConnectionResetError):
            recu = b""
    assert b"* OK" not in recu and b"CAPABILITY" not in recu, recu[:80]


def test_un_client_qui_ne_connait_pas_le_certificat_refuse():
    """auto-signé ne veut pas dire « accepté partout » : un client par défaut REFUSE, et c'est ce
    qui oblige à vérifier l'empreinte une fois (tools/make-imapd-cert.sh l'affiche)"""
    port = _port_libre()
    pret = threading.Event()

    def tourner():
        async def start():
            srv = await asyncio.start_server(Listener(lambda: None, None, tls=True).client, "127.0.0.1", port,
                                             ssl=tls_context(str(CERT), str(KEY)))
            pret.set()
            async with srv: await srv.serve_forever()
        try: asyncio.run(start())
        except (asyncio.CancelledError, RuntimeError): pass

    threading.Thread(target=tourner, daemon=True).start()
    assert pret.wait(10)
    with pytest.raises(ssl.SSLCertVerificationError):
        imaplib.IMAP4_SSL("127.0.0.1", port, ssl_context=ssl.create_default_context(), timeout=10)


# ── la garde de démarrage ──────────────────────────────────────────────────────────────────────
def test_le_clair_sur_le_reseau_est_refuse_au_demarrage():
    """exactement la configuration servie le 20/10 : 10.0.3.11, sans certificat"""
    with pytest.raises(SystemExit) as e:
        check_transport("10.0.3.11", tls=False)
    assert "ATOMBOX_IMAPD_CERT" in str(e.value), "le refus dit comment en sortir"


def test_le_clair_reste_permis_sur_la_boucle_locale_et_sur_decision():
    check_transport("127.0.0.1", tls=False)              # le développement, les tests
    check_transport("localhost", tls=False)
    check_transport("10.0.3.11", tls=False, allow_clear=True)   # une décision, écrite dans l'env
    check_transport("10.0.3.11", tls=True)


def test_un_certificat_sans_sa_cle_n_est_pas_un_repli_sur_le_clair():
    with pytest.raises(SystemExit):
        tls_context(str(CERT), "")
    with pytest.raises(SystemExit):
        tls_context("", str(KEY))
    assert tls_context("", "") is None


# ── ce qu'on annonce, on le tient ──────────────────────────────────────────────────────────────
# Chaque capacité annoncée, et le code qui la sert. Une capacité ajoutée à CAPABILITIES sans entrée
# ici fait rougir : c'est le moment de dire ce qui la tient. `STARTTLS` a été annoncé hors TLS
# pendant des semaines sans que `_c_starttls` existe — ce test l'aurait refusé le premier jour.
CE_QUI_LES_TIENT = {
    # IMAP4rev1 n'est pas un mot, c'est un CONTRAT : les commandes de la RFC 3501 § 6 que tout
    # serveur rev1 doit servir. L'annoncer en en servant une partie, c'est mentir sur la plus grosse
    # des capacités — et c'est l'état actuel, d'où la liste des manques ci-dessous.
    "IMAP4rev1":   ("_c_capability", "_c_noop", "_c_logout", "_c_login", "_c_authenticate",
                    "_c_select", "_c_examine", "_c_create", "_c_delete", "_c_rename",
                    "_c_subscribe", "_c_unsubscribe", "_c_list", "_c_lsub", "_c_status",
                    "_c_append", "_c_check", "_c_close", "_c_expunge", "_c_search", "_c_fetch",
                    "_c_store", "_c_copy", "_c_uid"),
    "AUTH=PLAIN":  ("_c_authenticate",),
    "UIDPLUS":     ("_c_uid", "_move"),            # COPYUID dans la réponse de MOVE / COPY
    "MOVE":        ("_c_move",),
    "SPECIAL-USE": ("_c_list",),                   # les attributs \\Trash, \\Archive… dans LIST
    "NAMESPACE":   ("_c_namespace",),
    "ID":          ("_c_id",),
    "STARTTLS":    ("_c_starttls",),
    "IDLE":        ("_c_idle",),
}

# CE QUI MANQUE, ÉCRIT. Un cliquet : servir une de ces commandes sans la retirer d'ici fait rougir,
# donc la liste ne peut que décroître, et elle dit à tout moment où en est RM3499.
MANQUES_CONNUS: set = set()


def test_chaque_capacite_annoncee_a_son_code():
    from atombox.imap.session import CAPABILITIES, Session
    inconnues = [c for c in CAPABILITIES if c not in CE_QUI_LES_TIENT]
    assert not inconnues, "capacité annoncée sans entrée dans CE_QUI_LES_TIENT : %s" % inconnues
    manquantes = {m for c in CAPABILITIES for m in CE_QUI_LES_TIENT[c] if not hasattr(Session, m)}
    imprevues = manquantes - MANQUES_CONNUS
    assert not imprevues, "annoncé, et rien ne le sert : " + ", ".join(sorted(imprevues))
    servies = MANQUES_CONNUS - manquantes
    assert not servies, ("désormais servies — à retirer de MANQUES_CONNUS : " + ", ".join(sorted(servies)))


def test_l_outil_pose_un_certificat_de_serveur_et_pas_une_autorite(tmp_path):
    """Le 21/10, la demande d'exception de Thunderbird tournait dans le vide : le certificat portait
    `CA:TRUE`, la valeur par défaut d'`openssl req -x509`. OpenSSL et Python l'acceptent en serveur,
    et c'est pour ça que les tests ci-dessus passaient ; Thunderbird (NSS) refuse une autorité
    utilisée comme certificat de serveur. On éprouve donc l'OUTIL, sur le fichier qu'il produit."""
    import shutil, subprocess
    if not shutil.which("openssl"):
        pytest.skip("binaire openssl absent : l'outil ne peut pas tourner ici (il le vérifie lui-même)")
    outil = ICI.parent / "tools" / "make-imapd-cert.sh"
    r = subprocess.run(["bash", str(outil)], env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                                  "ATOMBOX_IMAPD_CERT_DIR": str(tmp_path / "imapd")},
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    texte = subprocess.run(["openssl", "x509", "-in", str(tmp_path / "imapd" / "imapd.crt"), "-noout", "-text"],
                           capture_output=True, text=True).stdout
    assert "CA:FALSE" in texte, "un certificat de serveur n'est pas une autorité de certification"
    assert "TLS Web Server Authentication" in texte and "IP Address:127.0.0.1" in texte
    assert oct((tmp_path / "imapd" / "imapd.key").stat().st_mode & 0o777) == "0o600"
    # et il refuse d'écraser sans --force : chaque client qui a accepté l'exception serait refusé
    r2 = subprocess.run(["bash", str(outil)], env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path),
                                                   "ATOMBOX_IMAPD_CERT_DIR": str(tmp_path / "imapd")},
                        capture_output=True, text=True, timeout=60)
    assert r2.returncode == 2 and "--force" in r2.stdout


# ── RM3516 : l'accueil d'un client strict, et l'IPv6 ───────────────────────────────────────────────
# Le 04/11, Thunderbird se connectait à mmi mais l'application mail d'Android disait « impossible
# d'établir une connexion ». Deux causes, chacune suffisante : le nom a une adresse IPv6 et
# l'écouteur n'écoutait qu'en IPv4 ; et l'accueil disait « AtomBox prêt » — un octet 0xEA dans un
# texte que la RFC 3501 veut en ASCII 7 bits (resp-text = TEXT-CHAR).

def test_l_accueil_et_les_reponses_d_etat_sont_en_ascii(ecouteur_tls):
    """les OCTETS reçus, pas la chaîne : c'est sur eux qu'un client strict s'arrête"""
    raw = socket.create_connection(("127.0.0.1", ecouteur_tls), timeout=10)
    s = _client_qui_fait_confiance().wrap_socket(raw, server_hostname="localhost")
    try:
        accueil = s.recv(4096)
        assert accueil.startswith(b"* OK"), accueil
        assert all(b < 128 for b in accueil), accueil
        s.sendall(b"a1 LOGIN x\r\n")              # une erreur, dont le texte est en français
        rep = s.recv(4096)
        assert rep.startswith(b"a1 BAD") and all(b < 128 for b in rep), rep
    finally:
        s.close()


def test_le_texte_d_etat_est_ramene_a_l_ascii_mais_jamais_les_donnees():
    from atombox.imap.server import ascii_status
    assert ascii_status("* OK [CAPABILITY IMAP4rev1] AtomBox prêt") == "* OK [CAPABILITY IMAP4rev1] AtomBox pret"
    assert ascii_status("a2 NO [INUSE] la boîte est ouverte — la fermer d'abord") == \
        "a2 NO [INUSE] la boite est ouverte - la fermer d'abord"
    # une réponse de DONNÉES n'est jamais touchée : ses octets sont ceux du message (latin-1 = octets)
    fetch = '* 1 FETCH (ENVELOPE ("Sujet é" NIL))'
    assert ascii_status(fetch) == fetch
    litteral = "* 2 FETCH (BODY[] {3}\r\né\r\n)"
    assert ascii_status(litteral) == litteral


def test_l_ecoute_accepte_plusieurs_adresses():
    from atombox.imap.server import listen_hosts
    assert listen_hosts("0.0.0.0,::") == ["0.0.0.0", "::"]
    assert listen_hosts(" 0.0.0.0 , :: ") == ["0.0.0.0", "::"]
    assert listen_hosts("127.0.0.1") == ["127.0.0.1"]
    assert listen_hosts("") == ["127.0.0.1"]


def test_le_clair_est_refuse_si_une_seule_des_adresses_est_sur_le_reseau():
    from atombox.imap.server import listen_hosts
    with pytest.raises(SystemExit):
        for h in listen_hosts("127.0.0.1,::"):
            check_transport(h, tls=False)


def test_l_installation_ecoute_en_ipv4_et_en_ipv6():
    script = (ICI.parent / "tools" / "install-host.sh").read_text(encoding="utf-8")
    assert "ATOMBOX_IMAPD_LISTEN=0.0.0.0,::" in script
