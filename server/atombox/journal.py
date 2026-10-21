"""LE JOURNAL (D152, mise en œuvre) — des fichiers par DOMAINE et par SÉVÉRITÉ, dans logs/.

    logs/atombox.log     tout, au niveau réglé
    logs/<domaine>.log   un fichier par domaine : auth, api, imap, ingestion, store, filters, apps, schema, daemon, status
    logs/erreurs.log     WARNING et plus, tous domaines — ce qu'on lit à 3 h du matin

Quatre niveaux : DEBUG (le détail d'un protocole), INFO (ce qui s'est passé), WARNING (ce qui a
tenu mais ne devrait pas), ERROR (ce qui a échoué — bruyamment, D152). Rotation à minuit,
14 jours gardés. Réglages :

    ATOMBOX_LOGS=/var/log/atombox            le dossier (défaut : <dépôt>/logs)
    ATOMBOX_LOG_LEVEL=info                   le niveau par défaut
    ATOMBOX_LOG_LEVELS="imap=debug,auth=info" par domaine
    ATOMBOX_LOG_CONSOLE=1                     aussi sur la sortie d'erreur (développement)

Le journal des ACTIONS métier (qui a lu, traité, partagé — D054) est autre chose : une table.
Ici c'est le journal d'exploitation : ce que le logiciel a fait, pour qui l'exploite.

Usage : `from ..journal import journal ; log = journal("imap") ; log.info("…")`."""
from __future__ import annotations
import logging, logging.handlers, os, sys, threading

DOMAINS = ("auth", "api", "imap", "ingestion", "store", "filters", "apps", "schema", "daemon", "status")
FORMAT = "%(asctime)s %(levelname)-7s %(domain)-9s %(message)s"
_lock = threading.Lock(); _configured = False; _directory = None

class _Domain(logging.Filter):
    def filter(self, r):
        r.domain = r.name.split(".", 1)[1] if r.name.startswith("atombox.") else r.name
        return True

def directory() -> str:
    global _directory
    if _directory: return _directory
    d = os.environ.get("ATOMBOX_LOGS")
    if not d:
        here = os.path.dirname(os.path.abspath(__file__))
        d = os.path.join(here, "..", "..", "logs")            # <dépôt>/logs
    _directory = os.path.abspath(d)
    os.makedirs(_directory, exist_ok=True)
    return _directory

def _level(name: str, default: int) -> int:
    return getattr(logging, name.upper(), default) if isinstance(name, str) else default

def _file_handler(path: str, level: int) -> logging.Handler:
    h = logging.handlers.TimedRotatingFileHandler(path, when="midnight", backupCount=14, encoding="utf-8", utc=False)
    h.setLevel(level); h.setFormatter(logging.Formatter(FORMAT)); h.addFilter(_Domain())
    return h

def configure(log_directory: str | None = None, level: str | None = None, levels: str | None = None, console: bool | None = None, force: bool = False):
    """appelée une fois par processus — par journal() à la première demande, ou explicitement par les tests"""
    global _configured, _directory
    with _lock:
        if _configured and not force: return
        if log_directory: _directory = None; os.environ["ATOMBOX_LOGS"] = log_directory
        d = directory()
        base = logging.getLogger("atombox")
        for h in list(base.handlers): base.removeHandler(h); h.close()
        default = _level(level or os.environ.get("ATOMBOX_LOG_LEVEL", "info"), logging.INFO)
        base.setLevel(logging.DEBUG); base.propagate = False
        base.addHandler(_file_handler(os.path.join(d, "atombox.log"), default))
        base.addHandler(_file_handler(os.path.join(d, "erreurs.log"), logging.WARNING))
        if console if console is not None else os.environ.get("ATOMBOX_LOG_CONSOLE") == "1":
            c = logging.StreamHandler(sys.stderr); c.setLevel(default); c.setFormatter(logging.Formatter(FORMAT)); c.addFilter(_Domain()); base.addHandler(c)
        by_domain = {}
        for chunk in (levels or os.environ.get("ATOMBOX_LOG_LEVELS", "")).split(","):
            if "=" in chunk: k, v = chunk.split("=", 1); by_domain[k.strip()] = _level(v.strip(), default)
        for dom in DOMAINS:
            lg = logging.getLogger("atombox." + dom)
            for h in list(lg.handlers): lg.removeHandler(h); h.close()
            lg.setLevel(by_domain.get(dom, default))
            lg.addHandler(_file_handler(os.path.join(d, dom + ".log"), logging.DEBUG))
        _configured = True

def journal(domain: str) -> logging.Logger:
    """le logger d'un domaine — configure le journal à la première demande"""
    if domain not in DOMAINS: raise ValueError("domaine de journal inconnu : %s (connus : %s)" % (domain, ", ".join(DOMAINS)))
    if not _configured: configure()
    return logging.getLogger("atombox." + domain)
