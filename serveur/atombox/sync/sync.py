"""Le cœur de la synchronisation (F113) : la traduction entre l'état AtomBox et les FLAGS IMAP."""
from __future__ import annotations
import contextlib, threading
from datetime import datetime, timezone
from ..journal import journal

log = journal("imap")
_local = threading.local()

def descendante() -> bool:
    """vrai quand le processus applique un changement VENU d'IMAP : on ne le renvoie pas"""
    return getattr(_local, "descendante", False)

@contextlib.contextmanager
def en_descendante():
    avant = descendante(); _local.descendante = True
    try: yield
    finally: _local.descendante = avant

def drapeaux_voulus(ratt) -> tuple[list[str], list[str]]:
    """(à poser, à retirer) — la traduction de l'état AtomBox vers les FLAGS IMAP.
    On ne touche QUE ce qu'on sait traduire : \\Seen et \\Flagged. Les mots-clés d'un autre
    client ne sont jamais effacés (D140b : IMAP est la vérité, pas notre copie)."""
    poser, retirer = [], []
    (poser if ratt.lu_le else retirer).append("\\Seen")
    (poser if ratt.drapeau else retirer).append("\\Flagged")
    return poser, retirer

def etat_imap(flags: list[str]) -> dict:
    """la traduction inverse : ce que les FLAGS disent de l'état"""
    return {"lu": "\\Seen" in flags, "drapeau": "\\Flagged" in flags,
            "supprime": "\\Deleted" in flags}

def appliquer_descendante(s, ratt, flags: list[str]) -> list[str]:
    """Met le rattachement au diapason des FLAGS. Rend la liste des champs modifiés — vide si
    rien ne bouge, ce qui est le cas courant et doit rester silencieux."""
    e = etat_imap(flags); change = []
    with en_descendante():
        if e["lu"] and not ratt.lu_le:
            ratt.lu_le = datetime.now(timezone.utc); change.append("lu")
        elif not e["lu"] and ratt.lu_le:
            ratt.lu_le = None; change.append("non lu")
        if e["drapeau"] != bool(ratt.drapeau):
            ratt.drapeau = e["drapeau"]; change.append("drapeau")
    return change
