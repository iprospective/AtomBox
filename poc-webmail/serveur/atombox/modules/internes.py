"""LES MODULES INTERNES — le noyau écrit comme un module (D160)."""
from __future__ import annotations
from . import Module, accroche
from ..controleurs.session import SessionControleur
from ..controleurs.etat import EtatControleur
from ..journal import journal

class ModuleSession(Module):
    nom = "session"; version = "0.1"; description = "connexion, jeton, déconnexion (F124, D063, D157)"; interne = True
    controleurs = [SessionControleur]

class ModuleEtat(Module):
    nom = "etat"; version = "0.1"; description = "page d'état, journal lisible (F122, D152)"; interne = True
    controleurs = [EtatControleur]

class ModuleIngestion(Module):
    nom = "ingestion"; version = "0.1"; description = "relève IMAP, analyse, magasin (F001, F002) — émet message.avant_ingestion et message.ingere"; interne = True
    log = journal("ingestion")

    @accroche("message.ingere", priorite=1000)
    def compter(self, ctx):
        """dernier de la chaîne : dit ce que les modules ont fait du message"""
        if ctx.get("tags"): self.log.debug("%s : tags posés par les modules : %s", ctx["comm_id"], ctx["tags"])

MODULES_INTERNES = [ModuleSession, ModuleEtat, ModuleIngestion]
