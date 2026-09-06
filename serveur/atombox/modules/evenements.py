"""LES ÉVÉNEMENTS (D086, D161) — ce qui sort du processus : persistés, rejouables, hors transaction.

Une accroche est synchrone et dans le processus : elle ne doit ni attendre un réseau ni
survivre à un redémarrage. Un ÉVÉNEMENT est une ligne écrite DANS LA MÊME TRANSACTION que le
fait métier (motif « boîte d'envoi » : jamais un événement sans le fait, jamais le fait sans
l'événement), puis traitée par un autre processus (taches.py), au moins une fois, avec
tentatives à intervalle croissant, et un NOTIFY PostgreSQL pour réveiller sans attendre.
C'est ce qui porte les webhooks vers les applications (D086) et tout ce qu'un module veut
faire lentement, ailleurs, ou après."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, text
from ..journal import journal
from ..schema.modeles import Evenement
from ..uuid7 import uuid7

log = journal("apps")
CANAL = "atombox_evenements"
DELAIS = [30, 120, 600, 3600, 6 * 3600, 24 * 3600]        # secondes, tentative par tentative

class Abonnes:
    def __init__(self): self._h: dict[str, list[tuple[str, object]]] = {}
    def declarer(self, type_: str, fn, module: str): self._h.setdefault(type_, []).append((module, fn))
    def retirer(self, module: str):
        for t in self._h: self._h[t] = [x for x in self._h[t] if x[0] != module]
    def pour(self, type_: str): return list(self._h.get(type_, [])) + list(self._h.get("*", []))

abonnes = Abonnes()

def emettre(session, type_: str, charge: dict, module: str = "noyau", cible: str | None = None) -> Evenement:
    """à appeler DANS la transaction du fait métier ; le NOTIFY part avec le commit"""
    e = Evenement(evenement_id=uuid7(), type=type_, module=module, cible=cible, charge=charge,
                  cree_le=datetime.now(timezone.utc), prochaine_tentative=datetime.now(timezone.utc), tentatives=0)
    session.add(e)
    session.execute(text("select pg_notify(:c, :t)"), {"c": CANAL, "t": type_})   # dans schema/ on aurait mis le SQL ; ici c'est un NOTIFY, pas une requête
    return e

def a_traiter(session, lot: int = 50) -> list[Evenement]:
    """les événements dus, verrouillés pour ce processus — plusieurs travailleurs se partagent la file"""
    return list(session.scalars(select(Evenement).where(Evenement.traite_le.is_(None), Evenement.prochaine_tentative <= datetime.now(timezone.utc))
                                .order_by(Evenement.prochaine_tentative).limit(lot).with_for_update(skip_locked=True)))

def traiter(session, e: Evenement) -> bool:
    """rend True si traité ; sinon programme la tentative suivante — ou abandonne, bruyamment"""
    handlers = abonnes.pour(e.type)
    try:
        for module, fn in handlers: fn({"evenement": e, "session": session, "charge": e.charge, "type": e.type})
        e.traite_le = datetime.now(timezone.utc); e.erreur = None
        return True
    except Exception as ex:
        e.tentatives += 1; e.erreur = str(ex)[:500]
        if e.tentatives > len(DELAIS):
            e.traite_le = datetime.now(timezone.utc); e.abandonne = True
            log.error("événement %s (%s) ABANDONNÉ après %d tentatives : %s", e.evenement_id, e.type, e.tentatives, ex)
        else:
            e.prochaine_tentative = datetime.now(timezone.utc) + timedelta(seconds=DELAIS[e.tentatives - 1])
            log.warning("événement %s (%s) : tentative %d en échec, reprise dans %d s — %s", e.evenement_id, e.type, e.tentatives, DELAIS[e.tentatives - 1], ex)
        return False
