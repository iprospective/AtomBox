"""LE PROCESSUS DES TÂCHES (D161) — un ou plusieurs par instance : la file des événements
(au moins une fois, verrouillage par lot, réveil par NOTIFY) et les tâches cadencées des modules.

    DATABASE_URL=… python3 -m atombox.taches
"""
from __future__ import annotations
import asyncio, os, select as _select
from .db import session as ouvrir_session, moteur
from .journal import journal
from .modules import chargement
from .modules.evenements import CANAL, a_traiter, traiter
from .modules.taches import taches

log = journal("apps")

def un_tour() -> int:
    n = 0
    with ouvrir_session() as s:
        for e in a_traiter(s):
            if traiter(s, e): n += 1
            s.commit()
        for t in taches.dues(): taches.lancer(t)
    return n

async def principal():
    charges = chargement.charger()
    log.info("processus des tâches : %d module(s), %d tâche(s) cadencée(s)", len(charges), len(taches.liste()))
    cnx = moteur().raw_connection(); cnx.set_isolation_level(0) if hasattr(cnx, "set_isolation_level") else None
    cur = cnx.cursor(); cur.execute("LISTEN %s" % CANAL); cnx.commit()
    while True:
        traites = await asyncio.to_thread(un_tour)
        if traites: continue
        await asyncio.to_thread(_select.select, [cnx], [], [], float(os.environ.get("ATOMBOX_TACHES_PAS", "15")))
        cnx.poll() if hasattr(cnx, "poll") else None

if __name__ == "__main__":
    asyncio.run(principal())
