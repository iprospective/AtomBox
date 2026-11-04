"""LE DIRECT (RM3632, D169, D170) — les événements d'une portée, poussés en SSE au webmail et aux applications.

Le serveur écrit déjà chaque fait dans la table des événements, dans la transaction du fait (D161) :
message arrivé, état changé, déplacé… Le direct n'invente rien : il RELAIE ces lignes à qui les a
dans sa portée, dans l'ordre, avec un CURSEUR (l'identifiant de l'événement, uuid v7 donc ordonné
dans le temps). Un client qui se reconnecte donne le dernier qu'il a vu (`Last-Event-ID`) et reçoit
ce qu'il a manqué — rien de perdu, rien en double.

L'ÉVÉNEMENT INVALIDE, il ne porte pas l'état (D169) : il dit « ce message, ce dossier a changé » ; le
client relit ce qui le concerne par les routes habituelles, qui appliquent leurs propres droits.

Un compte ne reçoit JAMAIS un événement d'une boîte hors de sa portée : le filtre est ici, au seul
endroit qui relaie, et il porte sur la boîte de l'événement."""
from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from ..journal import journal
from ..schema.models import Evenement

log = journal("api")

# ce qui intéresse un écran ; le reste (envois, webhooks techniques…) ne sort pas par ici
RELAYED = ("message.ingere", "rattachement.change", "etat.descendu", "dossier.change", "tags.change")


def boites_of(charge: dict) -> set:
    """les boîtes qu'un événement concerne : `boite_id`, ou la liste `boites`"""
    out = set()
    if isinstance(charge, dict):
        if charge.get("boite_id"): out.add(str(charge["boite_id"]))
        for b in charge.get("boites") or []: out.add(str(b))
    return out


def frame(e_id, type_: str, charge: dict) -> str:
    """une trame SSE : `id`, `event`, `data` (une ligne JSON), et la ligne vide qui la termine"""
    return "id: %s\nevent: %s\ndata: %s\n\n" % (e_id, type_, json.dumps(charge, ensure_ascii=False, default=str))


async def latest(s) -> str | None:
    """le curseur « maintenant » : un client neuf ne reçoit pas l'historique, seulement la suite"""
    v = await s.scalar(select(Evenement.evenement_id).order_by(Evenement.evenement_id.desc()).limit(1))
    return str(v) if v else None


async def since(s, cursor: str | None, boites: set, limit: int = 200) -> tuple[list, str | None]:
    """[(id, type, charge)] des événements RELAYÉS après `cursor`, dans la portée ; et le nouveau curseur.

    Le curseur avance sur TOUS les événements lus, même ceux hors portée : sinon un client verrait
    la même page d'événements d'autrui à chaque passage."""
    q = select(Evenement.evenement_id, Evenement.type, Evenement.charge).where(Evenement.type.in_(RELAYED))
    if cursor:
        try: q = q.where(Evenement.evenement_id > uuid.UUID(cursor))
        except ValueError: pass
    rows = (await s.execute(q.order_by(Evenement.evenement_id).limit(limit))).all()
    out = [(str(i), t, c) for i, t, c in rows if boites_of(c) & boites]
    if out: log.debug("direct : %d événement(s) relayé(s) sur %d lu(s)", len(out), len(rows))
    return out, (str(rows[-1][0]) if rows else cursor)
