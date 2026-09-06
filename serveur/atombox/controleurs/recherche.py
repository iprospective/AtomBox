"""GET /recherche?q= — plein texte, portée du jeton, zone active par défaut (D034)."""
from __future__ import annotations
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..journal import journal
from ..schema.modeles import Compte
from ..services import recherche as svc

log = journal("api")

class RechercheControleur(Controleur):
    @action("GET", "/recherche")
    async def chercher(self, q: str = Query(""), sortis: int = 0, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        l = await svc.rechercher(s, compte, q, sortis=bool(sortis))
        log.debug("recherche %r par %s : %d", q, compte.login, len(l))
        return {"messages": l, "total": len(l), "q": q}
