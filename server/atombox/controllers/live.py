"""/evenements — le direct en SSE (RM3632, D169, D170) : le webmail et les applications restent connectés,
et le serveur leur pousse ce qui change dans leur portée.

SSE et non WebSocket (D169) : le besoin est unidirectionnel — les gestes partent par les routes REST —,
la reconnexion avec curseur est native (`Last-Event-ID`), et rien d'autre que HTTP ne traverse le
relais. La connexion ne garde AUCUNE transaction ouverte : chaque passage ouvre une session courte."""
from __future__ import annotations

import asyncio
import time

from fastapi import Depends, Query, Request
from fastapi.responses import StreamingResponse

from ..api.dependencies import async_session
from ..api.routing import Controller, action
from ..api.security import current_reader
from ..db import async_session_factory
from ..journal import journal
from ..schema.models import Compte
from ..services import live
from ..services.messages import account_mailboxes
from .. import settings

log = journal("api")


class EventsController(Controller):
    prefix = "/evenements"

    @action("GET", "")
    async def flux(self, request: Request, depuis: str | None = Query(None),
                   compte: Compte = Depends(current_reader), s=Depends(async_session)):
        boites = {str(b.boite_id) for b in await account_mailboxes(s, compte)}
        cursor = request.headers.get("last-event-id") or depuis or await live.latest(s)
        await s.close()                       # rien ne reste ouvert pendant la connexion
        pause = float(settings.read("ATOMBOX_LIVE_POLL", "1.5"))
        battement = float(settings.read("ATOMBOX_LIVE_PING", "20"))
        qui = getattr(compte, "login", None) or "application"
        log.info("direct : %s connecté (%d boîte(s))", qui, len(boites))

        async def gen():
            nonlocal cursor
            # `retry` : le navigateur rouvre seul après 3 s ; le premier commentaire dit « connecté »
            yield "retry: 3000\n: connecte\n\n"
            dernier = time.monotonic()
            try:
                while True:
                    if await request.is_disconnected(): break
                    async with async_session_factory()() as s2:
                        evts, cursor = await live.since(s2, cursor, boites)
                    for e_id, t, charge in evts:
                        yield live.frame(e_id, t, charge)
                        dernier = time.monotonic()
                    if not evts and time.monotonic() - dernier >= battement:
                        # un COMMENTAIRE garde la connexion vivante à travers les relais, et donne
                        # au client le curseur courant sans rien lui annoncer
                        yield ": ping\n\n"
                        dernier = time.monotonic()
                    await asyncio.sleep(pause)
            finally:
                log.info("direct : %s déconnecté", qui)

        # `no-transform` : un relais qui compresse (mod_deflate) mettrait le flux en tampon
        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})
