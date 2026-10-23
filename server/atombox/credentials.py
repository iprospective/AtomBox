"""LES IDENTIFIANTS DE CHAQUE BOÎTE chez le fournisseur — quand il n'y a pas de compte master.

Le chapitre 06 prévoit un compte master : un secret au lieu de cent (`boîte*master`). Tous les
fournisseurs n'en donnent pas, et un hébergement mutualisé n'en donne jamais. Sans master, chaque
boîte se connecte avec SON adresse et SON mot de passe, en IMAP comme en SMTP — un relais refuse
d'ailleurs qu'un compte expédie pour l'adresse d'un autre (`reject_sender_login_mismatch`).

OÙ. Un fichier à part, `/etc/atombox/boxes` (640 root:mathieu, comme `/etc/atombox/env`) : jamais en
base, jamais dans le dépôt (D149). Une ligne par boîte, l'adresse puis le mot de passe, séparés par
des blancs ; le mot de passe est tout le reste de la ligne. `#` commente.

    test@exemple.fr   le mot de passe de test@

Une boîte ABSENTE du fichier garde la règle d'avant : le master s'il y en a un, sinon l'adresse avec
`ATOMBOX_IMAP_PASSWORD`. Le fichier est relu à chaque connexion : ajouter une boîte ne demande pas
de redémarrer, la relève la prend à sa prochaine tentative.

Aucune fonction d'ici ne journalise un mot de passe, ni une ligne du fichier : une ligne mal formée
est signalée par son NUMÉRO.
"""
from __future__ import annotations
import os, re
from .journal import journal
from . import settings

log = journal("status")

DEFAULT_FILE = "/etc/atombox/boxes"
_LINE = re.compile(r"(\S+@\S+)\s+(.+)$")
_warned: set[str] = set()


def _warn_once(key: str, message: str, *args):
    if key not in _warned:
        _warned.add(key); log.warning(message, *args)


def table() -> dict[str, str]:
    """adresse (en minuscules) → mot de passe ; vide si le fichier n'existe pas"""
    path = settings.read("ATOMBOX_BOXES_FILE", DEFAULT_FILE)
    try:
        text = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return {}
    except OSError as e:
        _warn_once("lecture:" + path, "identifiants des boîtes : %s illisible (%s)", path, e.strerror); return {}
    if os.stat(path).st_mode & 0o004:
        _warn_once("droits:" + path, "identifiants des boîtes : %s est lisible par tous — chmod 640", path)
    out = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"): continue
        m = _LINE.match(line.strip())
        if not m:
            _warn_once("ligne:%s:%d" % (path, n), "identifiants des boîtes : %s, ligne %d mal formée (adresse puis mot de passe)", path, n)
            continue
        out[m.group(1).lower()] = m.group(2)
    return out


def login_of(adresse: str, master: str) -> str:
    """« boîte*master » avec un compte master (chapitre 06) ; l'adresse seule sinon"""
    return adresse if not master or master.lower() == adresse.lower() else "%s*%s" % (adresse, master)


def imap_login(adresse: str) -> tuple[str, str]:
    """(identifiant, mot de passe) pour ouvrir la boîte chez le fournisseur"""
    own = table().get(adresse.lower())
    if own is not None: return adresse, own
    master = (settings.read("ATOMBOX_IMAP_MASTER") or "").strip()
    return login_of(adresse, master), settings.read("ATOMBOX_IMAP_PASSWORD") or ""


def smtp_login(adresse: str | None) -> tuple[str | None, str | None]:
    """(utilisateur, mot de passe) pour remettre au relais un message expédié PAR cette adresse"""
    own = table().get(adresse.lower()) if adresse else None
    if own is not None: return adresse, own
    return settings.read("ATOMBOX_SMTP_USER"), settings.read("ATOMBOX_SMTP_PASSWORD")
