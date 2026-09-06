"""GET /referentiels — ce que le webmail charge à l'amorçage (D141) : moi, mes boîtes, les dossiers, les statuts, les vues."""
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

class ReferentielsControleur(Controleur):
    @action("GET", "/referentiels")
    async def lire(self, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        ref = await svc.referentiels(s, compte)
        log.debug("référentiels de %s : %d boîte(s), %d dossier(s)", compte.login, len(ref["moi"]["boites"]), len(ref["util"]))
        return ref
