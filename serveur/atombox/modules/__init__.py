"""TOUT EST MODULE (D073, D160) — y compris le noyau.

Un module est une classe qui déclare ce qu'elle apporte : des contrôleurs (des routes), des
accroches (des méthodes décorées @accroche("point")), un domaine de journal, des migrations.
Le noyau ne fait que les découvrir, les monter et les appeler. Les modules internes
(session, état, ingestion) sont écrits exactement comme le serait un module tiers."""
from __future__ import annotations
import inspect
from .accroches import accroches, POINTS
from .declencheurs import declencheurs, OPERATIONS
from .evenements import abonnes as abonnes_evenements
from .taches import taches

def accroche(point: str, priorite: int = 100):
    """@accroche("message.ingere") sur une méthode de module"""
    if point not in POINTS: raise ValueError("point d'accroche inconnu : " + point)
    def deco(fn):
        fn._accroche = (point, priorite); return fn
    return deco

def declencheur(point: str, priorite: int = 100):
    """@declencheur("comm.apres_insertion") — niveau ORM (D161)"""
    entite, _, op = point.rpartition(".")
    if op not in OPERATIONS: raise ValueError("déclencheur inconnu : " + point)
    def deco(fn):
        fn._declencheur = (point, priorite); return fn
    return deco

def evenement(type_: str):
    """@evenement("message.ingere") — traité hors processus, au moins une fois (D086, D161)"""
    def deco(fn):
        fn._evenement = type_; return fn
    return deco

def tache(chaque: str, nom: str | None = None):
    """@tache(chaque="10m") — cadencée par le processus des tâches"""
    def deco(fn):
        fn._tache = (chaque, nom); return fn
    return deco

class Module:
    nom: str = ""                 # identifiant court : « session », « dolibarr »… — préfixe des routes de module (/modules/<nom>/…)
    version: str = "0"
    description: str = ""
    controleurs: list = []        # des Controleur (D158) — routes du contrat, ou sous /modules/<nom>/
    migrations: str | None = None # dossier de révisions Alembic propres au module (tables préfixées mod_<nom>_)
    interne: bool = False         # les modules du noyau
    dependances: list[str] = []   # d'autres modules, chargés avant celui-ci
    parametres: dict = {}         # ses réglages et leurs défauts, dans la cascade (D106) sous mod.<nom>.*
    roles: list[str] = []         # les rôles qu'il définit (D072), préfixés mod.<nom>.
    interface: list[str] = []     # ses scripts côté webmail, servis sous /modules/<nom>/interface/…

    def demarrer(self, noyau) -> None:
        """appelé une fois au chargement, avec le noyau (accroches, journal, config)"""

    def brancher(self):
        for nom, fn in inspect.getmembers(self, predicate=inspect.ismethod):
            a = getattr(fn, "_accroche", None)
            if a: accroches.declarer(a[0], fn, self.nom, a[1])
            d = getattr(fn, "_declencheur", None)
            if d: declencheurs.declarer(d[0], fn, self.nom, d[1])
            e = getattr(fn, "_evenement", None)
            if e: abonnes_evenements.declarer(e, fn, self.nom)
            t = getattr(fn, "_tache", None)
            if t: taches.declarer(fn, self.nom, t[0], t[1])

    def debrancher(self):
        accroches.retirer(self.nom); declencheurs.retirer(self.nom); abonnes_evenements.retirer(self.nom); taches.retirer(self.nom)

    def routes_propres(self) -> str: return "/modules/" + self.nom
