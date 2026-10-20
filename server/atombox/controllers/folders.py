"""POST /dossiers-virtuels, DELETE /dossiers-virtuels/{id} (D143) ; GET et PUT /parametres (D106, D144) ; GET /pieces-jointes (D011)."""
from __future__ import annotations
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..api.routing import Controller, action
from ..api.dependencies import async_session
from ..api.security import current_account
from ..journal import journal
from ..schema.models import Comm, CommPieceJointe, Compte, PieceJointe, Rattachement
from ..services import folders as svc, messages as svcm

log = journal("api")

class VirtualFoldersController(Controller):
    prefix = "/dossiers-virtuels"

    @action("POST", "")
    async def create(self, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        c = await request.json() or {}
        d = await svc.create_virtual(s, compte, c.get("label"), c.get("criteres"))
        if d is None: raise HTTPException(400, "libellé et au moins un critère")
        log.info("dossier virtuel %s créé par %s", d["label"], compte.login)
        return {"ok": True, "crees": 1, "dossier": d}

    @action("DELETE", "/{id}")
    async def delete(self, id: str, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        if not await svc.delete_virtual(s, compte, id): raise HTTPException(404, "dossier inconnu")
        return {"ok": True, "supprimes": 1}

class SettingsController(Controller):
    prefix = "/parametres"

    @action("GET", "")
    async def read(self, compte: Compte = Depends(current_account)):
        return svc.settings_of(compte)

    @action("PUT", "")
    async def set_settings(self, request: Request, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        c = await request.json() or {}
        p = await svc.set_settings(s, compte, c.get("cle"), c.get("valeur"))
        if p is None: raise HTTPException(400, "réglage inconnu : %s" % c.get("cle"))
        return {"ok": True, "modifies": 1, "parametre": p}

class AttachmentsController(Controller):
    @action("GET", "/pieces-jointes")
    async def listing_all(self, compte: Compte = Depends(current_account), s: AsyncSession = Depends(async_session)):
        boites = [b.boite_id for b in await svcm.account_mailboxes(s, compte)]
        rows = (await s.execute(select(CommPieceJointe, PieceJointe, Comm).join(PieceJointe, PieceJointe.piece_jointe_id == CommPieceJointe.piece_jointe_id)
                                .join(Comm, Comm.comm_id == CommPieceJointe.comm_id).join(Rattachement, Rattachement.comm_id == Comm.comm_id)
                                .where(Rattachement.boite_id.in_(boites)).order_by(Comm.date_recue.desc()).limit(500))).all()
        seen, out = set(), []
        for l, p, c in rows:
            if (l.comm_id, l.ordre) in seen: continue
            seen.add((l.comm_id, l.ordre))
            out.append({"pj_id": str(p.piece_jointe_id), "ordre": l.ordre, "nom": l.nom_declare or ("piece-%d" % l.ordre), "octets": p.taille_octets,
                        "mime_declare": l.type_declare, "mime_detecte": p.type_detecte, "sha256": p.blob_ref, "partage_par": p.nb_references,
                        "message": {"id": str(c.comm_id), "sujet": c.sujet, "from_nom": c.from_nom, "date_recue": svcm.iso(c.date_recue)}})
        return {"pieces_jointes": out}
