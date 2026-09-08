"""LES POINTS D'ACCROCHE (D073, D160) — là où un module se branche.

Un point est nommé, documenté, et porte un contexte (un dict) que les modules lisent et
peuvent enrichir. Deux façons d'émettre : synchrone (le démon, l'ingestion — des threads) et
asynchrone (l'API). Un module dont l'accroche échoue est journalisé et ignoré : un module ne
fait jamais tomber le noyau (D152 : échouer bruyamment, pas deux fois)."""
from __future__ import annotations
import asyncio, inspect
from ..journal import journal

log = journal("apps")

POINTS = {
    "api.demarrage":            "l'application est montée — ctx : app, table (les routes)",
    "demon.demarrage":          "le démon d'ingestion démarre — ctx : boites",
    "message.avant_ingestion":  "un message brut est analysé, pas encore écrit — ctx : analyse, boite_id, octets ; un module peut poser ctx['ignorer']=True ou ajouter des ctx['tags']",
    "message.ingere":           "un message est en base — ctx : comm_id, nouveau, analyse, boite_id, tags ; un module peut classer, notifier, pousser vers une application",
    "session.ouverte":          "un compte vient de se connecter — ctx : compte, agent",
    "session.fermee":           "un compte s'est déconnecté — ctx : compte",
    "filtre.action":            "le moteur de filtres rencontre une action qu'il ne connaît pas — ctx : action, comm_id, parametres (F016)",
    "rattachement.pousse":      "un état a été poussé vers IMAP (F113) — ctx : comm_id, boite_id",
}

class Accroches:
    def __init__(self):
        self._h: dict[str, list[tuple[int, str, object]]] = {p: [] for p in POINTS}

    def declarer(self, point: str, fn, module: str, priorite: int = 100):
        if point not in POINTS: raise ValueError("point d'accroche inconnu : %s (connus : %s)" % (point, ", ".join(POINTS)))
        self._h[point].append((priorite, module, fn)); self._h[point].sort(key=lambda t: t[0])

    def retirer(self, module: str):
        for p in self._h: self._h[p] = [t for t in self._h[p] if t[1] != module]

    def abonnes(self, point: str) -> list[str]: return [m for _, m, _ in self._h[point]]

    def emettre(self, point: str, **ctx) -> dict:
        """synchrone : les accroches asynchrones y sont exécutées dans une boucle locale"""
        for _, module, fn in list(self._h[point]):
            try:
                r = fn(ctx)
                if inspect.isawaitable(r): asyncio.run(r)
            except Exception:
                log.exception("module %s : accroche %s en échec — ignorée", module, point)
        return ctx

    async def emettre_async(self, point: str, **ctx) -> dict:
        for _, module, fn in list(self._h[point]):
            try:
                r = fn(ctx)
                if inspect.isawaitable(r): await r
            except Exception:
                log.exception("module %s : accroche %s en échec — ignorée", module, point)
        return ctx

accroches = Accroches()
