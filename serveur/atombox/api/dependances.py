"""Les dépendances FastAPI : une session ORM asynchrone par requête (D158)."""
from __future__ import annotations
from ..db import fabrique_async

async def session_async():
    async with fabrique_async()() as s:
        yield s
