"""TOUT EST MODULE (D073, D160) — y compris le noyau.

Un module est une classe qui déclare ce qu'elle apporte : des contrôleurs (des routes), des
accroches (des méthodes décorées @accroche("point")), un domaine de journal, des migrations.
Le noyau ne fait que les découvrir, les monter et les appeler. Les modules internes
(session, état, ingestion) sont écrits exactement comme le serait un module tiers."""
from __future__ import annotations
import inspect
from .accroches import accroches, POINTS

def accroche(point: str, priorite: int = 100):
    """@accroche("message.ingere") sur une méthode de module"""
    if point not in POINTS: raise ValueError("point d'accroche inconnu : " + point)
    def deco(fn):
        fn._accroche = (point, priorite); return fn
    return deco

class Module:
    nom: str = ""                 # identifiant court : « session », « dolibarr »… — préfixe des routes de module (/modules/<nom>/…)
    version: str = "0"
    description: str = ""
    controleurs: list = []        # des Controleur (D158) — routes du contrat, ou sous /modules/<nom>/
    migrations: str | None = None # dossier de révisions Alembic propres au module (tables préfixées mod_<nom>_)
    interne: bool = False         # les modules du noyau

    def demarrer(self, noyau) -> None:
        """appelé une fois au chargement, avec le noyau (accroches, journal, config)"""

    def brancher(self):
        for nom, fn in inspect.getmembers(self, predicate=inspect.ismethod):
            a = getattr(fn, "_accroche", None)
            if a: accroches.declarer(a[0], fn, self.nom, a[1])

    def debrancher(self): accroches.retirer(self.nom)

    def routes_propres(self) -> str: return "/modules/" + self.nom
