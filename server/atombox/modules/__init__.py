"""TOUT EST MODULE (D073, D160) — y compris le noyau.

Un module est une classe qui déclare ce qu'elle apporte : des contrôleurs (des routes), des
accroches (des méthodes décorées @accroche("point")), un domaine de journal, des migrations.
Le noyau ne fait que les découvrir, les monter et les appeler. Les modules internes
(session, état, ingestion) sont écrits exactement comme le serait un module tiers."""
from __future__ import annotations
import inspect
from .hooks import hooks, POINTS
from .triggers import triggers, OPERATIONS
from .events import subscribers as event_subscribers
from .tasks import tasks

def hook(point: str, priority: int = 100):
    """@accroche("message.ingere") sur une méthode de module"""
    if point not in POINTS: raise ValueError("point d'accroche inconnu : " + point)
    def deco(fn):
        fn._hook = (point, priority); return fn
    return deco

def trigger(point: str, priority: int = 100):
    """@declencheur("comm.apres_insertion") — niveau ORM (D161)"""
    entite, _, op = point.rpartition(".")
    if op not in OPERATIONS: raise ValueError("déclencheur inconnu : " + point)
    def deco(fn):
        fn._trigger = (point, priority); return fn
    return deco

def event(type_: str):
    """@evenement("message.ingere") — traité hors processus, au moins une fois (D086, D161)"""
    def deco(fn):
        fn._event = type_; return fn
    return deco

def task(every: str, nom: str | None = None):
    """@tache(chaque="10m") — cadencée par le processus des tâches"""
    def deco(fn):
        fn._task = (every, nom); return fn
    return deco

class Module:
    nom: str = ""                 # identifiant court : « session », « dolibarr »… — préfixe des routes de module (/modules/<nom>/…)
    version: str = "0"
    description: str = ""
    controllers: list = []        # des Controleur (D158) — routes du contrat, ou sous /modules/<nom>/
    migrations: str | None = None # dossier de révisions Alembic propres au module (tables préfixées mod_<nom>_)
    interne: bool = False         # les modules du noyau
    dependencies: list[str] = []   # d'autres modules, chargés avant celui-ci
    settings_defaults: dict = {}         # ses réglages et leurs défauts, dans la cascade (D106) sous mod.<nom>.*
    roles: list[str] = []         # les rôles qu'il définit (D072), préfixés mod.<nom>.
    interface: list[str] = []     # ses scripts côté webmail, servis sous /modules/<nom>/interface/…

    def start(self, core) -> None:
        """appelé une fois au chargement, avec le noyau (accroches, journal, config)"""

    def bind(self):
        for nom, fn in inspect.getmembers(self, predicate=inspect.ismethod):
            a = getattr(fn, "_hook", None)
            if a: hooks.declare(a[0], fn, self.nom, a[1])
            d = getattr(fn, "_trigger", None)
            if d: triggers.declare(d[0], fn, self.nom, d[1])
            e = getattr(fn, "_event", None)
            if e: event_subscribers.declare(e, fn, self.nom)
            t = getattr(fn, "_task", None)
            if t: tasks.declare(fn, self.nom, t[0], t[1])

    def unbind(self):
        hooks.remove(self.nom); triggers.remove(self.nom); event_subscribers.remove(self.nom); tasks.remove(self.nom)

    def own_routes(self) -> str: return "/modules/" + self.nom
