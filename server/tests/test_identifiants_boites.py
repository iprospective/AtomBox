"""LES IDENTIFIANTS PAR BOÎTE (credentials.py) — la deuxième boîte d'une instance SANS compte master.

La forme de la production : `ATOMBOX_IMAP_MASTER` vaut l'adresse de la PREMIÈRE boîte, et le mot de
passe est le sien. La deuxième boîte se connectait alors en « b*a » avec le mot de passe de a — et
le fournisseur répondait AUTHENTICATIONFAILED toutes les minutes, sans fin. Les doublures vérifient
ici les identifiants comme le vrai fournisseur et le vrai relais.
"""
from __future__ import annotations
import imaplib, pathlib, re, smtplib
import pytest
from doublures import FauxImap, FauxRelais
from atombox import credentials
from atombox.ingestion.imap import open_mailbox
from atombox.sending.smtp import deliver

RACINE = pathlib.Path(__file__).resolve().parents[1]
COMPTES = {"a@exemple.fr": "mdp de a", "b@exemple.fr": "mdp de b"}
MESSAGE = b"From: b@exemple.fr\r\nTo: z@ailleurs.example\r\nSubject: essai\r\n\r\ncorps\r\n"


@pytest.fixture
def fichier(tmp_path, monkeypatch):
    f = tmp_path / "boxes"
    monkeypatch.setenv("ATOMBOX_BOXES_FILE", str(f))
    return f


@pytest.fixture
def fournisseur(monkeypatch, fichier):
    imap = FauxImap(comptes=COMPTES); imap.start()
    monkeypatch.setenv("ATOMBOX_IMAP_HOST", "127.0.0.1"); monkeypatch.setenv("ATOMBOX_IMAP_PORT", str(imap.port))
    monkeypatch.setenv("ATOMBOX_IMAP_TLS", "aucun")
    monkeypatch.setenv("ATOMBOX_IMAP_MASTER", "a@exemple.fr"); monkeypatch.setenv("ATOMBOX_IMAP_PASSWORD", "mdp de a")
    yield imap
    imap.arreter()


@pytest.fixture
def relais(monkeypatch, fichier):
    r = FauxRelais(comptes=COMPTES); r.start()
    monkeypatch.setenv("ATOMBOX_SMTP_HOST", "127.0.0.1"); monkeypatch.setenv("ATOMBOX_SMTP_PORT", str(r.port))
    monkeypatch.setenv("ATOMBOX_SMTP_TLS", "aucun")
    monkeypatch.setenv("ATOMBOX_SMTP_USER", "a@exemple.fr"); monkeypatch.setenv("ATOMBOX_SMTP_PASSWORD", "mdp de a")
    yield r
    r.arreter()


def test_le_fichier_se_lit_ligne_a_ligne(fichier):
    fichier.write_text("# commentaire\n;a@exemple.fr commenté à la façon d'un .ini\n\n  B@Exemple.fr\t  un mot de passe avec  des blancs \n"
                       "ligne-sans-adresse secret\nc@exemple.fr\n", encoding="utf-8")
    t = credentials.table()
    assert t == {"b@exemple.fr": "un mot de passe avec  des blancs"}, t     # ligne 4 et 5 mal formées : ignorées


def test_sans_fichier_rien_ne_change(monkeypatch, tmp_path):
    monkeypatch.setenv("ATOMBOX_BOXES_FILE", str(tmp_path / "absent"))
    monkeypatch.setenv("ATOMBOX_IMAP_MASTER", "maitre"); monkeypatch.setenv("ATOMBOX_IMAP_PASSWORD", "m")
    assert credentials.imap_login("b@exemple.fr") == ("b@exemple.fr*maitre", "m")
    monkeypatch.setenv("ATOMBOX_IMAP_MASTER", "")
    assert credentials.imap_login("b@exemple.fr") == ("b@exemple.fr", "m")


def test_la_deuxieme_boite_est_refusee_sans_ses_identifiants(fournisseur):
    """la contre-épreuve : c'est la panne de la production, reproduite"""
    open_mailbox("a@exemple.fr").close()
    with pytest.raises(imaplib.IMAP4.error, match="AUTHENTICATIONFAILED"):
        open_mailbox("b@exemple.fr")
    assert fournisseur.logins == ["a@exemple.fr"]


def test_la_deuxieme_boite_entre_avec_ses_identifiants_sans_redemarrer(fournisseur, fichier):
    with pytest.raises(imaplib.IMAP4.error): open_mailbox("b@exemple.fr")
    fichier.write_text("b@exemple.fr mdp de b\n", encoding="utf-8")    # même processus : le fichier est relu
    open_mailbox("b@exemple.fr").close()
    open_mailbox("a@exemple.fr").close()                                 # la première ne change pas
    assert fournisseur.logins == ["b@exemple.fr", "a@exemple.fr"]


def test_le_relais_refuse_que_a_expedie_pour_b(relais):
    with pytest.raises(smtplib.SMTPSenderRefused):
        deliver(MESSAGE, "b@exemple.fr", ["z@ailleurs.example"])
    assert relais.remises == []


def test_b_expedie_avec_ses_identifiants(relais, fichier):
    fichier.write_text("b@exemple.fr mdp de b\n", encoding="utf-8")
    deliver(MESSAGE, "b@exemple.fr", ["z@ailleurs.example"])
    deliver(MESSAGE.replace(b"From: b@", b"From: a@"), "a@exemple.fr", ["z@ailleurs.example"])
    assert [r["de"] for r in relais.wait(2, 3)] == ["b@exemple.fr", "a@exemple.fr"]


def test_aucune_connexion_au_fournisseur_ne_contourne_open_mailbox():
    """un chemin qui bâtirait sa propre connexion retrouverait l'ancienne règle, et la panne"""
    fautifs = [str(p.relative_to(RACINE)) for p in (RACINE / "atombox").rglob("*.py")
               if p.name != "imap.py" and re.search(r"Poller\(.*\)\s*\.connect\(", p.read_text(encoding="utf-8"))]
    assert fautifs == []
    # la garde n'est pas vide : elle reconnaît la forme d'avant, telle qu'elle était écrite
    assert re.search(r"Poller\(.*\)\s*\.connect\(",
                     'releve = Poller(cfg["hote"], cfg["port"], tls=tls_imap()).connect(login_of(adresse, cfg["master"]), cfg["mot_de_passe"])')
