"""GET /etat/journal — le journal d'exploitation lisible dans l'interface (F122, D152).
V0 : tout compte connecté (il n'y a pas de rôles) ; dès F041, un rôle d'administration."""
from __future__ import annotations
import os, re
from fastapi import Depends, HTTPException, Query
from ..api.routage import Controleur, action
from ..api.securite import compte_courant
from ..journal import DOMAINES, dossier, journal
from ..schema.modeles import Compte

NIVEAUX = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
log = journal("etat")

class EtatControleur(Controleur):
    prefixe = "/etat"

    @action("GET", "/journal")
    async def journal(self, domaine: str = Query("atombox", description="atombox (tout), erreurs, ou un domaine : " + ", ".join(DOMAINES)),
                      niveau: str = Query("INFO", description="niveau minimal : DEBUG, INFO, WARNING, ERROR"),
                      lignes: int = Query(200, ge=1, le=2000), filtre: str | None = Query(None, description="un mot à retrouver"),
                      compte: Compte = Depends(compte_courant)):
        if domaine not in DOMAINES + ("atombox", "erreurs"): raise HTTPException(404, "journal inconnu")
        niveau = niveau.upper()
        if niveau not in NIVEAUX: raise HTTPException(400, "niveau inconnu")
        chemin = os.path.join(dossier(), domaine + ".log")
        if not os.path.exists(chemin): return {"domaine": domaine, "lignes": [], "fichier": chemin}
        seuil = NIVEAUX.index(niveau)
        motif = re.compile(r"^\S+ \S+ (\w+)\s+(\S+)\s+(.*)$")
        out = []
        with open(chemin, encoding="utf-8", errors="replace") as f:
            for l in _queue(f, lignes * 4):
                m = motif.match(l.rstrip("\n"))
                if not m: continue
                if NIVEAUX.index(m.group(1)) < seuil if m.group(1) in NIVEAUX else True: continue
                if filtre and filtre.lower() not in l.lower(): continue
                out.append({"quand": l[:23].strip(), "niveau": m.group(1), "domaine": m.group(2), "message": m.group(3)})
        log.debug("journal %s lu par %s (%d lignes)", domaine, compte.login, len(out))
        return {"domaine": domaine, "niveau": niveau, "lignes": out[-lignes:], "fichier": chemin}

def _queue(f, n: int):
    """les n dernières lignes, sans lire tout un fichier d'un an"""
    f.seek(0, 2); taille = f.tell(); bloc = 65536; pos = taille; morceaux = []
    while pos > 0 and sum(m.count("\n") for m in morceaux) <= n:
        pos = max(0, pos - bloc); f.seek(pos); morceaux.insert(0, f.read(min(bloc, taille - pos)))
    return "".join(morceaux).splitlines(keepends=True)[-n:]
