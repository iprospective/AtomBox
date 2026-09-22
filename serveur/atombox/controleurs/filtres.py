"""/filtres — les règles du moteur (F016, D074) : lire, créer, modifier, supprimer, et VOIR
lesquelles ne se déclenchent jamais (D075 § 1)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..filtres.moteur import ACTIONS, CHAMPS, OPERATEURS
from ..journal import journal
from ..schema.modeles import Compte, Filtre
from ..services.messages import boites_du_compte, iso
from ..uuid7 import uuid7

log = journal("filtres")

def _serialiser(f: Filtre) -> dict:
    return {"id": str(f.filtre_id), "nom": f.nom, "ordre": f.ordre, "actif": f.actif,
            "predicat": f.predicat, "action": f.action, "portee": f.portee_type,
            "nb_declenchements": f.nb_declenchements or 0,
            "dernier_declenchement": iso(f.dernier_declenchement),
            "muette": not (f.nb_declenchements or 0), "importe_de": f.importe_de}

def _valider(c: dict, complet: bool) -> None:
    """Ce qu'une règle doit être pour avoir un sens. `complet` : à la création, tout est exigé ; à
    la modification, seuls les champs envoyés sont contrôlés.

    Partagé entre POST et PATCH, et c'est le point : POST validait, PATCH ne validait RIEN. On
    pouvait donc créer une règle correcte puis la CASSER d'un coup de PATCH — lui poser une action
    que le moteur ne connaît pas. La règle continuait à compter ses déclenchements (le prédicat,
    lui, correspondait toujours) et ne faisait plus rien : elle avait l'air de travailler. C'est
    exactement l'angle mort que le compteur de D075 § 1 est censé éclairer, et il ne le voyait pas.
    """
    if complet or "nom" in c:
        if not (c.get("nom") or "").strip(): raise HTTPException(400, "un nom")
    if complet or "predicat" in c:
        if not ((c.get("predicat") or {}).get("criteres")):
            raise HTTPException(400, "au moins un critère — un prédicat vide n'attrape rien")
        for crit in c["predicat"]["criteres"]:
            if crit.get("champ") not in CHAMPS: raise HTTPException(400, "champ inconnu : %s" % crit.get("champ"))
            if crit.get("operateur", "contient") not in OPERATEURS:
                raise HTTPException(400, "opérateur inconnu : %s" % crit.get("operateur"))
    if complet or "action" in c:
        if (c.get("action") or {}).get("type") not in ACTIONS:
            raise HTTPException(400, "action inconnue : %s" % (c.get("action") or {}).get("type"))


class FiltresControleur(Controleur):
    prefixe = "/filtres"

    @action("GET", "")
    async def liste(self, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        boites = [b.boite_id for b in await boites_du_compte(s, compte)]
        fs = list(await s.scalars(select(Filtre).where(Filtre.action.isnot(None)).order_by(Filtre.ordre)))
        fs = [f for f in fs if (f.portee_type == "compte" and f.portee_id == compte.compte_id)
              or (f.portee_type == "boite" and f.portee_id in boites)]
        return {"filtres": [_serialiser(f) for f in fs], "total": len(fs),
                "champs": sorted(CHAMPS), "operateurs": sorted(OPERATEURS), "actions": list(ACTIONS)}

    @action("POST", "")
    async def creer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        c = await request.json() or {}
        _valider(c, complet=True)
        # UNE RÈGLE QUI AGIT EST UNE RÈGLE DE BOÎTE (D171). Elle modifie le rattachement, qui est
        # unique par boîte (D124) : elle vaut pour tous ceux qui la partagent, et c'est à la boîte
        # que l'ingestion demande ses règles. Portée « compte », elle ne s'appliquait JAMAIS au
        # courrier entrant — et l'écran des règles créait tout en portée « compte » (RM3188).
        # Une règle de compte, sans action, c'est un dossier virtuel : il passe par sa propre route.
        boites = [b.boite_id for b in await boites_du_compte(s, compte)]
        if c.get("portee_id"):
            pid = uuid.UUID(c["portee_id"])
        elif len(boites) == 1:
            pid = boites[0]
        else:
            raise HTTPException(400, "précisez la boîte (portee_id) : une règle trie le courrier D'UNE boîte")
        if pid not in boites: raise HTTPException(404, "boîte inconnue")
        if c.get("portee", "boite") != "boite":
            log.info("règle « %s » : portée « %s » demandée, rattachée à la boîte — une règle qui agit est une règle de boîte (D171)",
                     (c.get("nom") or "").strip(), c.get("portee"))
        portee = "boite"
        dernier = await s.scalar(select(Filtre).where(Filtre.portee_type == portee, Filtre.portee_id == pid).order_by(Filtre.ordre.desc()).limit(1))
        f = Filtre(filtre_id=uuid7(), portee_type=portee, portee_id=pid, nom=c["nom"].strip(),
                   ordre=c.get("ordre") or ((dernier.ordre + 1) if dernier else 1),
                   predicat=c["predicat"], action=c["action"], actif=c.get("actif", True),
                   retroactif=False, nb_declenchements=0, cree_par=compte.compte_id)
        s.add(f); await s.commit()
        log.info("règle « %s » créée par %s (portée %s)", f.nom, compte.login, portee)
        return {"ok": True, "crees": 1, "filtre": _serialiser(f)}

    @action("PATCH", "/{id}")
    async def modifier(self, id: str, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        f = await self._mien(s, compte, id)
        c = await request.json() or {}
        _valider(c, complet=False)
        for champ in ("nom", "ordre", "actif", "predicat", "action"):
            if champ in c: setattr(f, champ, c[champ])
        await s.commit()
        return {"ok": True, "modifies": 1, "filtre": _serialiser(f)}

    @action("DELETE", "/{id}")
    async def supprimer(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        f = await self._mien(s, compte, id)
        await s.delete(f); await s.commit()
        log.info("règle « %s » supprimée par %s", f.nom, compte.login)
        return {"ok": True, "supprimes": 1}

    async def _mien(self, s, compte, id: str) -> Filtre:
        try: f = await s.get(Filtre, uuid.UUID(id))
        except ValueError: f = None
        if f is None: raise HTTPException(404, "règle inconnue")
        boites = [b.boite_id for b in await boites_du_compte(s, compte)]
        if not ((f.portee_type == "compte" and f.portee_id == compte.compte_id)
                or (f.portee_type == "boite" and f.portee_id in boites)):
            raise HTTPException(404, "règle inconnue")     # hors portée = 404 (D108)
        return f
