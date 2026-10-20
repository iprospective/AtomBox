"""GET /etat/journal — le journal d'exploitation lisible dans l'interface (F122, D152).
V0 : tout compte connecté (il n'y a pas de rôles) ; dès F041, un rôle d'administration."""
from __future__ import annotations
import os, re
from fastapi import Depends, HTTPException, Query
from ..api.routing import Controller, action
from ..api.security import current_account
from ..api.dependencies import async_session
from ..journal import DOMAINS, directory, journal
from ..schema.models import Compte

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
log = journal("status")

class StatusController(Controller):
    prefix = "/etat"

    @action("GET", "")
    async def status(self, compte: Compte = Depends(current_account), s=Depends(async_session)):
        from ..services.status import status as calculer
        return await calculer(s, compte)

    @action("GET", "/metriques")
    async def metrics(self, compte: Compte = Depends(current_account), s=Depends(async_session)):
        from fastapi.responses import PlainTextResponse
        from ..services.status import status as calculer, metrics as rendre
        return PlainTextResponse(rendre(await calculer(s, compte)), media_type="text/plain; version=0.0.4")

    @action("GET", "/journal")
    async def journal(self, domaine: str = Query("atombox", description="atombox (tout), erreurs, ou un domaine : " + ", ".join(DOMAINS)),
                      niveau: str = Query("INFO", description="niveau minimal : DEBUG, INFO, WARNING, ERROR"),
                      lines: int = Query(200, ge=1, le=2000), filtre: str | None = Query(None, description="un mot à retrouver"),
                      compte: Compte = Depends(current_account)):
        if domaine not in DOMAINS + ("atombox", "erreurs"): raise HTTPException(404, "journal inconnu")
        niveau = niveau.upper()
        if niveau not in LEVELS: raise HTTPException(400, "niveau inconnu")
        path = os.path.join(directory(), domaine + ".log")
        if not os.path.exists(path): return {"domaine": domaine, "lignes": [], "fichier": path}
        seuil = LEVELS.index(niveau)
        motif = re.compile(r"^\S+ \S+ (\w+)\s+(\S+)\s+(.*)$")
        out = []
        with open(path, encoding="utf-8", errors="replace") as f:
            for l in _queue(f, lines * 4):
                m = motif.match(l.rstrip("\n"))
                if not m: continue
                if LEVELS.index(m.group(1)) < seuil if m.group(1) in LEVELS else True: continue
                if filtre and filtre.lower() not in l.lower(): continue
                out.append({"quand": l[:23].strip(), "niveau": m.group(1), "domaine": m.group(2), "message": m.group(3)})
        log.debug("journal %s lu par %s (%d lignes)", domaine, compte.login, len(out))
        return {"domaine": domaine, "niveau": niveau, "lignes": out[-lines:], "fichier": path}

def _queue(f, n: int):
    """les n dernières lignes, sans lire tout un fichier d'un an"""
    f.seek(0, 2); taille = f.tell(); bloc = 65536; pos = taille; morceaux = []
    while pos > 0 and sum(m.count("\n") for m in morceaux) <= n:
        pos = max(0, pos - bloc); f.seek(pos); morceaux.insert(0, f.read(min(bloc, taille - pos)))
    return "".join(morceaux).splitlines(keepends=True)[-n:]
