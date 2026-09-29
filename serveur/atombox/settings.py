"""LES RÉGLAGES (D181) — un point de lecture unique, et le repli sur les anciens noms.

Les identifiants sont en anglais, la prose en français : c'est la règle du projet depuis D181. Ce
fichier en est le premier exemple, et il est volontairement petit pour qu'il serve de modèle.

POURQUOI UN REPLI, ET PAS UN RENOMMAGE SEC. Le fichier `/etc/atombox/env` d'une instance en service
porte les anciens noms, et il n'est **pas** dans le dépôt : c'est un secret (D150). Renommer d'un
bloc ne casse rien tout de suite — ça casse au **prochain redémarrage**, c'est-à-dire un jour où
personne ne fera le lien avec le commit qui l'a causé. Une panne différée est la pire espèce.

Chaque réglage est donc lu par son nouveau nom, **puis** par l'ancien. L'ancien journalise un
avertissement qui NOMME son remplaçant : la liste des avertissements dit exactement ce qu'il reste
à migrer, et le jour où `to_migrate()` rend une liste vide partout, ce module perd sa raison d'être
et s'en va avec.
"""
from __future__ import annotations
import os
from .journal import journal

log = journal("etat")      # les réglages relèvent de l'exploitation : c'est là qu'on les lit

# nouveau nom → nom d'hier. Une ligne qui disparaît est une migration finie.
FORMER_NAMES = {
    "ATOMBOX_STORE":            "ATOMBOX_MAGASIN",
    "ATOMBOX_HOST":             "ATOMBOX_HOTE",
    "ATOMBOX_PUBLIC_URL":       "ATOMBOX_URL_PUBLIQUE",
    "ATOMBOX_SERVICE_SENDER":   "ATOMBOX_EXPEDITEUR_SERVICE",
    "ATOMBOX_LOG_LEVEL":        "ATOMBOX_LOG_NIVEAU",
    "ATOMBOX_LOG_LEVELS":       "ATOMBOX_LOG_NIVEAUX",
    "ATOMBOX_TASKS_INTERVAL":   "ATOMBOX_TACHES_PAS",
    "ATOMBOX_IDLE_SECONDS":     "ATOMBOX_IDLE_SECONDES",
    "ATOMBOX_TRACE_CLIENT_IP":  "ATOMBOX_TRACER_IP_CLIENT",
    "ATOMBOX_IMAP_HOST":        "ATOMBOX_IMAP_HOTE",
    "ATOMBOX_IMAP_PASSWORD":    "ATOMBOX_IMAP_MOT_DE_PASSE",
    "ATOMBOX_SMTP_HOST":        "ATOMBOX_SMTP_HOTE",
    "ATOMBOX_SMTP_USER":        "ATOMBOX_SMTP_UTILISATEUR",
    "ATOMBOX_SMTP_PASSWORD":    "ATOMBOX_SMTP_MOT_DE_PASSE",
    "ATOMBOX_IMAPD_LISTEN":     "ATOMBOX_IMAPD_ECOUTE",
    "ATOMBOX_IMAPD_KEY":        "ATOMBOX_IMAPD_CLE",
    "ATOMBOX_TARGET":           "ATOMBOX_CIBLE",
    "ATOMBOX_ANDROID_PASSWORD": "ATOMBOX_ANDROID_MDP",
}

_warned: set[str] = set()


def read(name: str, default=None):
    """la valeur du réglage, ou de son nom d'hier — avec un avertissement, une seule fois"""
    value = os.environ.get(name)
    if value is not None: return value
    former = FORMER_NAMES.get(name)
    if former:
        value = os.environ.get(former)
        if value is not None:
            if former not in _warned:
                _warned.add(former)
                log.warning("réglage « %s » : nom d'hier, à renommer en « %s » (D181)", former, name)
            return value
    return default


def integer(name: str, default: int) -> int:
    value = read(name)
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        # Un réglage illisible ne doit pas empêcher de démarrer : on le dit et on garde le défaut.
        log.warning("réglage « %s » : %r n'est pas un entier, on garde %d", name, value, default)
        return default


def boolean(name: str, default: bool = False) -> bool:
    value = read(name)
    if value is None: return default
    return value.strip().lower() in ("1", "oui", "yes", "true", "vrai", "on")


def to_migrate() -> list[str]:
    """les noms d'hier encore posés dans l'environnement — ce qu'il reste à renommer"""
    return sorted(former for former in FORMER_NAMES.values() if os.environ.get(former) is not None)
