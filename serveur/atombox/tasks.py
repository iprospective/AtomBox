"""LE PROCESSUS DES TÂCHES (D161) — un ou plusieurs par instance : la file des événements
(au moins une fois, verrouillage par lot, réveil par NOTIFY) et les tâches cadencées des modules.

    DATABASE_URL=… python3 -m atombox.tasks
"""
from __future__ import annotations
import asyncio, os
import psycopg
from .db import session as open_session
from .journal import journal
from .modules import loading
from .modules.events import CHANNEL, pending, process
from .modules.tasks import tasks
from . import settings

log = journal("apps")

def one_round() -> int:
    n = 0
    with open_session() as s:
        for e in pending(s):
            if process(s, e): n += 1
            s.commit()
        for t in tasks.due(): tasks.run(t)
    return n

async def main():
    loaded = loading.load()
    log.info("processus des tâches : %d module(s), %d tâche(s) cadencée(s)", len(loaded), len(tasks.listing()))
    # l'écoute NOTIFY : une connexion psycopg 3 à part, en autocommit (D161) — pas de SQL ici, un canal
    cnx = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True); cnx.execute("LISTEN %s" % CHANNEL)
    pas = float(settings.read("ATOMBOX_TASKS_INTERVAL", "15"))
    def wait():
        for _ in cnx.notifies(timeout=pas): break      # réveillé par un NOTIFY, ou délai écoulé
    while True:
        traites = await asyncio.to_thread(one_round)
        if traites: continue
        await asyncio.to_thread(wait)

if __name__ == "__main__":
    asyncio.run(main())
