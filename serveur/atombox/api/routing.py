"""LE ROUTAGE (D158) — des routes qui mènent à des CONTRÔLEURS et des ACTIONS, comme Symfony.

Un contrôleur est une classe ; une action est une méthode décorée par @action(méthode, chemin).
Le chemin est celui de routes.yml, sans le préfixe /api/v1 : le dictionnaire est le contrat,
et verifier_contrat() dit ce qui est écrit hors contrat (refusé) et ce qui reste à écrire."""
from __future__ import annotations
import inspect, os, re, yaml
from fastapi import FastAPI, APIRouter

PREFIX = "/api/v1"

def action(methode: str, path: str, **options):
    """déclare une action : @action("GET", "/messages/{id}")"""
    def deco(fn):
        fn._route = (methode.upper(), path, options)
        return fn
    return deco

class Controller:
    """une classe par ressource ; ses actions sont ses méthodes décorées"""
    prefix = ""

    @classmethod
    def actions(cls):
        for nom, fn in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(fn, "_route"): yield nom, fn

def register(app: FastAPI, controllers: list[type[Controller]]) -> list[tuple[str, str, str]]:
    """monte chaque action ; rend [(méthode, chemin, Contrôleur.action)]"""
    routeur = APIRouter(prefix=PREFIX)
    table = []
    for cls in controllers:
        instance = cls()
        for nom, fn in cls.actions():
            methode, path, options = fn._route
            path = cls.prefix + path
            routeur.add_api_route(path, getattr(instance, nom), methods=[methode], name="%s.%s" % (cls.__name__, nom), **options)
            table.append((methode, path, "%s.%s" % (cls.__name__, nom)))
    app.include_router(routeur)
    return table

def routes_from_dictionary(chemin_dict: str | None = None) -> list[tuple[str, str, dict]]:
    d = chemin_dict or _find_dict()
    if not d: return []
    rows = yaml.safe_load(open(os.path.join(d, "routes.yml"), encoding="utf-8"))
    return [(r["methode"].upper(), r["chemin"].replace(PREFIX, "", 1), r) for r in rows]

def check_contract(table: list[tuple[str, str, str]], chemin_dict: str | None = None, modules: list[str] | None = None) -> dict:
    """{hors_contrat: [...], sans_action: [...], couvertes: n, propres: n} — une route sous /modules/<nom>/ d'un
    module chargé est PROPRE au module (D160) : hors du contrat du noyau, et légitime"""
    contrat = {(m, _norm(c)): r for m, c, r in routes_from_dictionary(chemin_dict)}
    ecrites = {(m, _norm(c)): a for m, c, a in table}
    propre = lambda c: any(c.startswith("/modules/%s/" % n) for n in (modules or []))
    return { "hors_contrat": sorted("%s %s → %s" % (m, c, a) for (m, c), a in ecrites.items() if (m, c) not in contrat and not propre(c)),
             "propres": sum(1 for (m, c) in ecrites if propre(c)),
             "sans_action": sorted("%s %s (%s)" % (m, c, r.get("etat")) for (m, c), r in contrat.items() if (m, c) not in ecrites),
             "couvertes": sum(1 for k in ecrites if k in contrat), "contrat": len(contrat) }

def _norm(c: str) -> str: return re.sub(r"\{[^}]+\}", "{}", c.rstrip("/"))

def _find_dict():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs", "dict")
        if os.path.isdir(c): return c
        d = os.path.dirname(d)
    return os.environ.get("CDC_DIR") and os.path.join(os.environ["CDC_DIR"], "dict")
