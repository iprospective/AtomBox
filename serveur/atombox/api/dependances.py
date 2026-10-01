"""Les dépendances FastAPI : une session ORM asynchrone par requête (D158)."""
from __future__ import annotations
from ..db import async_session_factory

async def session_async():
    async with async_session_factory()() as s:
        yield s
