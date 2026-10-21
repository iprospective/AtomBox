"""LES DÉCLENCHEURS (D161) — les accroches au niveau de l'ORM.

Une accroche parle métier (« un message est ingéré ») ; un déclencheur parle donnée (« une
ligne de comm va être insérée »). Ils sont engendrés pour CHAQUE modèle (schema/modeles.py) :

    <entite>.avant_insertion   <entite>.apres_insertion
    <entite>.avant_modification <entite>.apres_modification    (ctx : objet, modifie = {champ: (avant, après)})
    <entite>.avant_suppression <entite>.apres_suppression

Ils servent à la dénormalisation, aux compteurs (nb_references, D087), à l'audit (D054), à la
validation — dans le code, pas dans PostgreSQL : portables, testables, journalisés. Ce qui doit
tenir même si le code est contourné (une unicité, une clé) reste une contrainte du schéma.
Un déclencheur ne fait jamais tomber une transaction du noyau : il est journalisé et ignoré ;
s'il doit REFUSER, il lève RefusDeclencheur — la seule exception qui traverse."""
from __future__ import annotations
from sqlalchemy import event, inspect
from ..journal import journal
from ..schema.models import Base, MODELS

log = journal("apps")
OPERATIONS = ("avant_insertion", "apres_insertion", "avant_modification", "apres_modification", "avant_suppression", "apres_suppression")

class TriggerRefused(Exception):
    """un déclencheur refuse l'opération : la transaction échoue, avec la raison"""

class Triggers:
    def __init__(self):
        self._h: dict[str, list[tuple[int, str, object]]] = {}

    @staticmethod
    def points() -> list[str]: return ["%s.%s" % (e, op) for e in MODELS for op in OPERATIONS]

    def declare(self, point: str, fn, module: str, priority: int = 100):
        entite, _, op = point.rpartition(".")
        if entite not in MODELS or op not in OPERATIONS: raise ValueError("déclencheur inconnu : %s" % point)
        self._h.setdefault(point, []).append((priority, module, fn)); self._h[point].sort(key=lambda t: t[0])

    def remove(self, module: str):
        for p in self._h: self._h[p] = [t for t in self._h[p] if t[1] != module]

    def subscribers(self, point: str) -> list[str]: return [m for _, m, _ in self._h.get(point, [])]

    def run(self, point: str, objet, session=None, modifie: dict | None = None):
        for _, module, fn in list(self._h.get(point, [])):
            try: fn({"objet": objet, "session": session, "modifie": modifie or {}, "point": point})
            except TriggerRefused: raise
            except Exception: log.exception("module %s : déclencheur %s en échec — ignoré", module, point)

triggers = Triggers()

def _changed(objet) -> dict:
    etat = inspect(objet); out = {}
    for attr in etat.attrs:
        h = attr.history
        if h.has_changes(): out[attr.key] = ((h.deleted or [None])[0], (h.added or [None])[0])
    return out

def _bind_sqlalchemy():
    """une seule écoute sur la Base : chaque modèle hérite des six points"""
    def _name(target): return target.__tablename__
    @event.listens_for(Base, "before_insert", propagate=True)
    def _bi(mapper, cnx, target): triggers.run(_name(target) + ".avant_insertion", target)
    @event.listens_for(Base, "after_insert", propagate=True)
    def _ai(mapper, cnx, target): triggers.run(_name(target) + ".apres_insertion", target)
    @event.listens_for(Base, "before_update", propagate=True)
    def _bu(mapper, cnx, target): triggers.run(_name(target) + ".avant_modification", target, modifie=_changed(target))
    @event.listens_for(Base, "after_update", propagate=True)
    def _au(mapper, cnx, target): triggers.run(_name(target) + ".apres_modification", target)
    @event.listens_for(Base, "before_delete", propagate=True)
    def _bd(mapper, cnx, target): triggers.run(_name(target) + ".avant_suppression", target)
    @event.listens_for(Base, "after_delete", propagate=True)
    def _ad(mapper, cnx, target): triggers.run(_name(target) + ".apres_suppression", target)

_bind_sqlalchemy()
