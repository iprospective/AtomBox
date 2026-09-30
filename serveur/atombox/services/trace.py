"""LE JOURNAL DES ACTES (D054) — qui a fait quoi, quand, sur quoi. Jamais purgé.

À ne pas confondre avec `atombox/journal.py`, qui est le journal d'EXPLOITATION (des fichiers, pour
celui qui tient le serveur). Celui-ci est une TABLE, et c'est un livre de comptes.

POURQUOI IL EXISTE VRAIMENT, et pourquoi il n'est pas décoratif : depuis D175, le rattachement ne
porte plus que l'état COURANT d'un message. « Traité le 3, puis archivé le 10 » ne se lit donc plus
sur la ligne — seul le journal le raconte. Sans écriture ici, l'historique des sorties n'existe pas.

Ce qu'il ne contient JAMAIS : le contenu d'un message du dossier personnel (D134). Les détails
disent l'acte — l'avant, l'après, la boîte — pas le message.
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from ..journal import journal
from ..schema.modeles import Journal
from ..uuid7 import uuid7

log = journal("api")


def record(s, compte_id, action: str, cible_type: str, cible_id, details: dict | None = None) -> None:
    """ajoute une ligne — SYNCHRONE au sens ORM : on empile, l'appelant commite.

    Pas de commit ici : une trace qui se commite seule sortirait du même coup l'acte à moitié
    écrit qu'elle décrit. Elle doit vivre et mourir avec lui."""
    s.add(Journal(journal_id=uuid7(), quand=datetime.now(timezone.utc), qui=compte_id,
                  action=action, cible_type=cible_type, cible_id=cible_id, details=details or None))


async def history(s: AsyncSession, cible_id, limite: int = 50) -> list[dict]:
    """l'histoire d'une cible, la plus récente d'abord — « traité puis archivé » se relit ici"""
    from sqlalchemy import select
    lignes = await s.scalars(select(Journal).where(Journal.cible_id == cible_id)
                             .order_by(Journal.quand.desc()).limit(limite))
    return [{"quand": j.quand.astimezone(timezone.utc).isoformat(), "qui": str(j.qui) if j.qui else None,
             "action": j.action, "details": j.details} for j in lignes]
