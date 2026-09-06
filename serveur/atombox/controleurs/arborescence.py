"""GET /arborescence — les compteurs de TOUTE l'arborescence en une passe (D078), les dossiers virtuels personnels (D143), les épingles (D144)."""
from __future__ import annotations
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..schema.modeles import Compte
from ..services import messages as svc
from ..journal import journal

log = journal("api")

class ArborescenceControleur(Controleur):
    @action("GET", "/arborescence")
    async def lire(self, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        arbo = await svc.compteurs(s, compte)
        log.debug("arborescence de %s : %d dossier(s) comptés", compte.login, len(arbo["compteurs"]))
        return arbo
