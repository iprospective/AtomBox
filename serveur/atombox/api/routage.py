"""LE ROUTAGE (D158) — des routes qui mènent à des CONTRÔLEURS et des ACTIONS, comme Symfony.

Un contrôleur est une classe ; une action est une méthode décorée par @action(méthode, chemin).
Le chemin est celui de routes.yml, sans le préfixe /api/v1 : le dictionnaire est le contrat,
et verifier_contrat() dit ce qui est écrit hors contrat (refusé) et ce qui reste à écrire."""
from __future__ import annotations
import inspect, os, re, yaml
from fastapi import FastAPI, APIRouter

PREFIXE = "/api/v1"

def action(methode: str, chemin: str, **options):
    """déclare une action : @action("GET", "/messages/{id}")"""
    def deco(fn):
        fn._route = (methode.upper(), chemin, options)
        return fn
    return deco

class Controleur:
    """une classe par ressource ; ses actions sont ses méthodes décorées"""
    prefixe = ""

    @classmethod
    def actions(cls):
        for nom, fn in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(fn, "_route"): yield nom, fn

def enregistrer(app: FastAPI, controleurs: list[type[Controleur]]) -> list[tuple[str, str, str]]:
    """monte chaque action ; rend [(méthode, chemin, Contrôleur.action)]"""
    routeur = APIRouter(prefix=PREFIXE)
    table = []
    for cls in controleurs:
        instance = cls()
        for nom, fn in cls.actions():
            methode, chemin, options = fn._route
            chemin = cls.prefixe + chemin
            routeur.add_api_route(chemin, getattr(instance, nom), methods=[methode], name="%s.%s" % (cls.__name__, nom), **options)
            table.append((methode, chemin, "%s.%s" % (cls.__name__, nom)))
    app.include_router(routeur)
    return table

def routes_du_dictionnaire(chemin_dict: str | None = None) -> list[tuple[str, str, dict]]:
    d = chemin_dict or _trouver_dict()
    if not d: return []
    rows = yaml.safe_load(open(os.path.join(d, "routes.yml"), encoding="utf-8"))
    return [(r["methode"].upper(), r["chemin"].replace(PREFIXE, "", 1), r) for r in rows]

def verifier_contrat(table: list[tuple[str, str, str]], chemin_dict: str | None = None, modules: list[str] | None = None) -> dict:
    """{hors_contrat: [...], sans_action: [...], couvertes: n, propres: n} — une route sous /modules/<nom>/ d'un
    module chargé est PROPRE au module (D160) : hors du contrat du noyau, et légitime"""
    contrat = {(m, _norm(c)): r for m, c, r in routes_du_dictionnaire(chemin_dict)}
    ecrites = {(m, _norm(c)): a for m, c, a in table}
    propre = lambda c: any(c.startswith("/modules/%s/" % n) for n in (modules or []))
    return { "hors_contrat": sorted("%s %s → %s" % (m, c, a) for (m, c), a in ecrites.items() if (m, c) not in contrat and not propre(c)),
             "propres": sum(1 for (m, c) in ecrites if propre(c)),
             "sans_action": sorted("%s %s (%s)" % (m, c, r.get("etat")) for (m, c), r in contrat.items() if (m, c) not in ecrites),
             "couvertes": sum(1 for k in ecrites if k in contrat), "contrat": len(contrat) }

def _norm(c: str) -> str: return re.sub(r"\{[^}]+\}", "{}", c.rstrip("/"))

def _trouver_dict():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs", "dict")
        if os.path.isdir(c): return c
        d = os.path.dirname(d)
    return os.environ.get("CDC_DIR") and os.path.join(os.environ["CDC_DIR"], "dict")
