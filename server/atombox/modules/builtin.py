"""LES MODULES INTERNES — le noyau écrit comme un module (D160)."""
from __future__ import annotations
from . import Module, hook
from ..controllers.session import SessionController
from ..controllers.status import StatusController
from ..controllers.references import ReferencesController
from ..controllers.tree import TreeController
from ..controllers.messages import MessagesController
from ..controllers.live import EventsController
from ..controllers.folders import VirtualFoldersController, SettingsController, AttachmentsController
from ..controllers.search import SearchController
from ..controllers.applications import ApplicationController, AxesController
from ..sending.module import SendingModule
from ..sync.module import ModuleSync
from ..controllers.filters import FiltersController
from ..controllers.folders_util import AddressBookController, FoldersController, IdentitiesController
from ..journal import journal

class ModuleSession(Module):
    nom = "session"; version = "0.1"; description = "connexion, jeton, déconnexion (F124, D063, D157)"; interne = True
    controllers = [SessionController]

class ModuleStatus(Module):
    nom = "etat"; version = "0.1"; description = "page d'état, journal lisible (F122, D152)"; interne = True
    controllers = [StatusController]

class ModuleIngestion(Module):
    nom = "ingestion"; version = "0.1"; description = "relève IMAP, analyse, magasin, moteur de filtres (F001, F002, F016)"; interne = True
    controllers = [FiltersController]
    log = journal("ingestion")

    @hook("message.ingere", priority=1000)
    def count(self, ctx):
        """dernier de la chaîne : dit ce que les modules ont fait du message"""
        if ctx.get("tags"): self.log.debug("%s : tags posés par les modules : %s", ctx["comm_id"], ctx["tags"])

class ModuleMessages(Module):
    nom = "messages"; version = "0.1"; description = "référentiels, arborescence, liste, message, fil, rattachement, création — ce que le webmail lit (D141)"; interne = True
    controllers = [ReferencesController, TreeController, MessagesController, VirtualFoldersController,
                   SettingsController, AttachmentsController, SearchController,
                   FoldersController, IdentitiesController, AddressBookController, ApplicationController, AxesController,
                   EventsController]

BUILTIN_MODULES = [ModuleSession, ModuleStatus, ModuleIngestion, ModuleMessages, SendingModule, ModuleSync]
