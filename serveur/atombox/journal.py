"""LE JOURNAL (D152, mise en œuvre) — des fichiers par DOMAINE et par SÉVÉRITÉ, dans logs/.

    logs/atombox.log     tout, au niveau réglé
    logs/<domaine>.log   un fichier par domaine : auth, api, imap, ingestion, magasin, filtres, apps, schema, demon, etat
    logs/erreurs.log     WARNING et plus, tous domaines — ce qu'on lit à 3 h du matin

Quatre niveaux : DEBUG (le détail d'un protocole), INFO (ce qui s'est passé), WARNING (ce qui a
tenu mais ne devrait pas), ERROR (ce qui a échoué — bruyamment, D152). Rotation à minuit,
14 jours gardés. Réglages :

    ATOMBOX_LOGS=/var/log/atombox            le dossier (défaut : <dépôt>/logs)
    ATOMBOX_LOG_NIVEAU=info                   le niveau par défaut
    ATOMBOX_LOG_NIVEAUX="imap=debug,auth=info" par domaine
    ATOMBOX_LOG_CONSOLE=1                     aussi sur la sortie d'erreur (développement)

Le journal des ACTIONS métier (qui a lu, traité, partagé — D054) est autre chose : une table.
Ici c'est le journal d'exploitation : ce que le logiciel a fait, pour qui l'exploite.

Usage : `from ..journal import journal ; log = journal("imap") ; log.info("…")`."""
from __future__ import annotations
import logging, logging.handlers, os, sys, threading

DOMAINES = ("auth", "api", "imap", "ingestion", "magasin", "filtres", "apps", "schema", "demon", "etat")
FORMAT = "%(asctime)s %(levelname)-7s %(domaine)-9s %(message)s"
_verrou = threading.Lock(); _configure = False; _dossier = None

class _Domaine(logging.Filter):
    def filter(self, r):
        r.domaine = r.name.split(".", 1)[1] if r.name.startswith("atombox.") else r.name
        return True

def dossier() -> str:
    global _dossier
    if _dossier: return _dossier
    d = os.environ.get("ATOMBOX_LOGS")
    if not d:
        ici = os.path.dirname(os.path.abspath(__file__))
        d = os.path.join(ici, "..", "..", "logs")            # <dépôt>/logs
    _dossier = os.path.abspath(d)
    os.makedirs(_dossier, exist_ok=True)
    return _dossier

def _niveau(nom: str, defaut: int) -> int:
    return getattr(logging, nom.upper(), defaut) if isinstance(nom, str) else defaut

def _fichier(chemin: str, niveau: int) -> logging.Handler:
    h = logging.handlers.TimedRotatingFileHandler(chemin, when="midnight", backupCount=14, encoding="utf-8", utc=False)
    h.setLevel(niveau); h.setFormatter(logging.Formatter(FORMAT)); h.addFilter(_Domaine())
    return h

def configurer(dossier_logs: str | None = None, niveau: str | None = None, niveaux: str | None = None, console: bool | None = None, forcer: bool = False):
    """appelée une fois par processus — par journal() à la première demande, ou explicitement par les tests"""
    global _configure, _dossier
    with _verrou:
        if _configure and not forcer: return
        if dossier_logs: _dossier = None; os.environ["ATOMBOX_LOGS"] = dossier_logs
        d = dossier()
        base = logging.getLogger("atombox")
        for h in list(base.handlers): base.removeHandler(h); h.close()
        defaut = _niveau(niveau or os.environ.get("ATOMBOX_LOG_NIVEAU", "info"), logging.INFO)
        base.setLevel(logging.DEBUG); base.propagate = False
        base.addHandler(_fichier(os.path.join(d, "atombox.log"), defaut))
        base.addHandler(_fichier(os.path.join(d, "erreurs.log"), logging.WARNING))
        if console if console is not None else os.environ.get("ATOMBOX_LOG_CONSOLE") == "1":
            c = logging.StreamHandler(sys.stderr); c.setLevel(defaut); c.setFormatter(logging.Formatter(FORMAT)); c.addFilter(_Domaine()); base.addHandler(c)
        par_domaine = {}
        for morceau in (niveaux or os.environ.get("ATOMBOX_LOG_NIVEAUX", "")).split(","):
            if "=" in morceau: k, v = morceau.split("=", 1); par_domaine[k.strip()] = _niveau(v.strip(), defaut)
        for dom in DOMAINES:
            lg = logging.getLogger("atombox." + dom)
            for h in list(lg.handlers): lg.removeHandler(h); h.close()
            lg.setLevel(par_domaine.get(dom, defaut))
            lg.addHandler(_fichier(os.path.join(d, dom + ".log"), logging.DEBUG))
        _configure = True

def journal(domaine: str) -> logging.Logger:
    """le logger d'un domaine — configure le journal à la première demande"""
    if domaine not in DOMAINES: raise ValueError("domaine de journal inconnu : %s (connus : %s)" % (domaine, ", ".join(DOMAINES)))
    if not _configure: configurer()
    return logging.getLogger("atombox." + domaine)
