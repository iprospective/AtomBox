"""LES TÂCHES (D161) — ce qui tourne à intervalle, sans message pour le déclencher : le
ramasse-miettes (D087), les règles rétroactives (Q067), le dépouillement DMARC (D115), la purge
selon la rétention (D104). Un module déclare @tache(chaque="10m") ; le processus `taches`
(atombox.taches) les cadence, et traite la file des événements entre deux."""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from ..journal import journal

log = journal("apps")

def _duree(s: str) -> timedelta:
    m = re.fullmatch(r"(\d+)\s*([smhj])", s.strip())
    if not m: raise ValueError("durée invalide : %r (ex. 30s, 10m, 2h, 1j)" % s)
    n, u = int(m.group(1)), m.group(2)
    return timedelta(seconds=n) if u == "s" else timedelta(minutes=n) if u == "m" else timedelta(hours=n) if u == "h" else timedelta(days=n)

class Taches:
    def __init__(self): self._t: list[dict] = []
    def declarer(self, fn, module: str, chaque: str, nom: str | None = None):
        self._t.append({"fn": fn, "module": module, "chaque": _duree(chaque), "nom": nom or fn.__name__, "derniere": None})
    def retirer(self, module: str): self._t = [t for t in self._t if t["module"] != module]
    def dues(self, maintenant: datetime | None = None) -> list[dict]:
        m = maintenant or datetime.now(timezone.utc)
        return [t for t in self._t if t["derniere"] is None or m - t["derniere"] >= t["chaque"]]
    def lancer(self, t: dict, noyau=None):
        t["derniere"] = datetime.now(timezone.utc)
        try: t["fn"]({"noyau": noyau, "quand": t["derniere"]})
        except Exception: log.exception("module %s : tâche %s en échec — reprogrammée", t["module"], t["nom"])
    def liste(self): return [(t["module"], t["nom"], t["chaque"]) for t in self._t]

taches = Taches()
