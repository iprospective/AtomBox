"""POST /dossiers-virtuels, DELETE /dossiers-virtuels/{id} (D143) ; GET et PUT /parametres (D106, D144) ; GET /pieces-jointes (D011)."""
from __future__ import annotations
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routage import Controleur, action
from ..api.dependances import session_async
from ..api.securite import compte_courant
from ..journal import journal
from ..schema.modeles import Comm, CommPieceJointe, Compte, PieceJointe, Rattachement
from ..services import dossiers as svc, messages as svcm

log = journal("api")

class DossiersVirtuelsControleur(Controleur):
    prefixe = "/dossiers-virtuels"

    @action("POST", "")
    async def creer(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        c = await request.json() or {}
        d = await svc.creer_virtuel(s, compte, c.get("label"), c.get("criteres"))
        if d is None: raise HTTPException(400, "libellé et au moins un critère")
        log.info("dossier virtuel %s créé par %s", d["label"], compte.login)
        return {"ok": True, "crees": 1, "dossier": d}

    @action("DELETE", "/{id}")
    async def supprimer(self, id: str, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        if not await svc.supprimer_virtuel(s, compte, id): raise HTTPException(404, "dossier inconnu")
        return {"ok": True, "supprimes": 1}

class ParametresControleur(Controleur):
    prefixe = "/parametres"

    @action("GET", "")
    async def lire(self, compte: Compte = Depends(compte_courant)):
        return svc.parametres(compte)

    @action("PUT", "")
    async def regler(self, request: Request, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        c = await request.json() or {}
        p = await svc.regler(s, compte, c.get("cle"), c.get("valeur"))
        if p is None: raise HTTPException(400, "réglage inconnu : %s" % c.get("cle"))
        return {"ok": True, "modifies": 1, "parametre": p}

class PiecesJointesControleur(Controleur):
    @action("GET", "/pieces-jointes")
    async def toutes(self, compte: Compte = Depends(compte_courant), s: AsyncSession = Depends(session_async)):
        boites = [b.boite_id for b in await svcm.boites_du_compte(s, compte)]
        rows = (await s.execute(select(CommPieceJointe, PieceJointe, Comm).join(PieceJointe, PieceJointe.piece_jointe_id == CommPieceJointe.piece_jointe_id)
                                .join(Comm, Comm.comm_id == CommPieceJointe.comm_id).join(Rattachement, Rattachement.comm_id == Comm.comm_id)
                                .where(Rattachement.boite_id.in_(boites)).order_by(Comm.date_recue.desc()).limit(500))).all()
        vus, out = set(), []
        for l, p, c in rows:
            if (l.comm_id, l.ordre) in vus: continue
            vus.add((l.comm_id, l.ordre))
            out.append({"pj_id": str(p.piece_jointe_id), "ordre": l.ordre, "nom": l.nom_declare or ("piece-%d" % l.ordre), "octets": p.taille_octets,
                        "mime_declare": l.type_declare, "mime_detecte": p.type_detecte, "sha256": p.blob_ref, "partage_par": p.nb_references,
                        "message": {"id": str(c.comm_id), "sujet": c.sujet, "from_nom": c.from_nom, "date_recue": svcm.iso(c.date_recue)}})
        return {"pieces_jointes": out}
