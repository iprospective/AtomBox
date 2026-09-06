"""LA DÉCOUVERTE des modules (D160) : les internes, puis les points d'entrée Python
(`atombox.modules` dans pyproject d'un paquet tiers), puis ATOMBOX_MODULES="paquet:Classe,…"."""
from __future__ import annotations
import importlib, os
from importlib.metadata import entry_points
from ..journal import journal
from . import Module
from .accroches import accroches

log = journal("apps")
_charges: list[Module] = []

class Noyau:
    def __init__(self): self.accroches = accroches; self.modules = _charges

def internes() -> list[Module]:
    from .internes import MODULES_INTERNES
    return [m() for m in MODULES_INTERNES]

def charger(supplementaires: list[Module] | None = None, tiers: bool = True) -> list[Module]:
    """charge (ou recharge) l'ensemble ; rend la liste dans l'ordre : internes, tiers, supplémentaires"""
    for m in _charges: m.debrancher()
    _charges.clear()
    liste = internes()
    if tiers:
        for ep in entry_points(group="atombox.modules"):
            try: liste.append(ep.load()())
            except Exception: log.exception("module tiers %s : chargement en échec — ignoré", ep.name)
        for spec in filter(None, os.environ.get("ATOMBOX_MODULES", "").split(",")):
            try:
                mod, cls = spec.strip().split(":"); liste.append(getattr(importlib.import_module(mod), cls)())
            except Exception: log.exception("module %s : chargement en échec — ignoré", spec)
    liste += list(supplementaires or [])
    # les dépendances (D161) : un module se charge après ceux qu'il déclare ; une dépendance absente l'écarte
    disponibles = {m.nom for m in liste}
    ordonnee, vus = [], set()
    def visiter(m, pile=()):
        if m.nom in vus: return
        if m.nom in pile: log.error("modules en cycle : %s — %s écarté", " → ".join(pile + (m.nom,)), m.nom); return
        for d in m.dependances:
            if d not in disponibles: log.error("module %s : dépendance %s absente — écarté", m.nom, d); return
            visiter(next(x for x in liste if x.nom == d), pile + (m.nom,))
        if all(d in vus for d in m.dependances): vus.add(m.nom); ordonnee.append(m)
    for m in liste: visiter(m)
    liste = ordonnee
    noms = set()
    noyau = Noyau()
    for m in liste:
        if not m.nom or m.nom in noms: log.error("module sans nom ou nom en double : %r — ignoré", m.nom); continue
        noms.add(m.nom); m.brancher()
        try: m.demarrer(noyau)
        except Exception: log.exception("module %s : demarrer() en échec", m.nom)
        _charges.append(m)
        log.info("module %s %s chargé (%d contrôleur(s))%s", m.nom, m.version, len(m.controleurs), " — interne" if m.interne else "")
    return list(_charges)

def charges() -> list[Module]: return list(_charges)
