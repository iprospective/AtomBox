"""LA DÉCOUVERTE des modules (D160) : les internes, puis les points d'entrée Python
(`atombox.modules` dans pyproject d'un paquet tiers), puis ATOMBOX_MODULES="paquet:Classe,…"."""
from __future__ import annotations
import importlib, os
from importlib.metadata import entry_points
from ..journal import journal
from . import Module
from .hooks import hooks
from .. import settings

log = journal("apps")
_charges: list[Module] = []

class Core:
    def __init__(self): self.hooks = hooks; self.modules = _charges

def builtin_modules() -> list[Module]:
    from .builtin import BUILTIN_MODULES
    return [m() for m in BUILTIN_MODULES]

def load(extra: list[Module] | None = None, tiers: bool = True) -> list[Module]:
    """charge (ou recharge) l'ensemble ; rend la liste dans l'ordre : internes, tiers, supplémentaires"""
    for m in _charges: m.unbind()
    _charges.clear()
    listing = builtin_modules()
    if tiers:
        for ep in entry_points(group="atombox.modules"):
            try: listing.append(ep.load()())
            except Exception: log.exception("module tiers %s : chargement en échec — ignoré", ep.name)
        for spec in filter(None, settings.read("ATOMBOX_MODULES", "").split(",")):
            try:
                mod, cls = spec.strip().split(":"); listing.append(getattr(importlib.import_module(mod), cls)())
            except Exception: log.exception("module %s : chargement en échec — ignoré", spec)
    listing += list(extra or [])
    # les dépendances (D161) : un module se charge après ceux qu'il déclare ; une dépendance absente l'écarte
    available = {m.nom for m in listing}
    ordered, seen = [], set()
    def visit(m, stack=()):
        if m.nom in seen: return
        if m.nom in stack: log.error("modules en cycle : %s — %s écarté", " → ".join(stack + (m.nom,)), m.nom); return
        for d in m.dependencies:
            if d not in available: log.error("module %s : dépendance %s absente — écarté", m.nom, d); return
            visit(next(x for x in listing if x.nom == d), stack + (m.nom,))
        if all(d in seen for d in m.dependencies): seen.add(m.nom); ordered.append(m)
    for m in listing: visit(m)
    listing = ordered
    names = set()
    core = Core()
    for m in listing:
        if not m.nom or m.nom in names: log.error("module sans nom ou nom en double : %r — ignoré", m.nom); continue
        names.add(m.nom); m.bind()
        try: m.start(core)
        except Exception: log.exception("module %s : demarrer() en échec", m.nom)
        _charges.append(m)
        log.info("module %s %s chargé (%d contrôleur(s))%s", m.nom, m.version, len(m.controllers), " — interne" if m.interne else "")
    return list(_charges)

def loaded() -> list[Module]: return list(_charges)
