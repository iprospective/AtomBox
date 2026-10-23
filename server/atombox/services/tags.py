"""LES TAGS (F009/F010 — D002, D017, D018, D019, D020, D021).

Le tag est l'axe central du produit : AtomBox indexe sur des **critères paramétrables**, pas
seulement sur les champs d'un email (D002). Trois règles du CDC gouvernent ce fichier :

  — le tag est posé sur le MESSAGE, pas sur le rattachement (D017) : c'est ce qui le rend
    interopérable entre applications. Deux personnes d'une boîte partagée voient les mêmes tags ;
  — plusieurs applications posent sur le même message SANS s'écraser (D020) : la source est
    gardée (`manuel`, ou le nom du connecteur), et retirer le tag d'autrui se trace ;
  — un axe a une ACL (D018) : ce qu'on ne peut pas lire ne s'affiche pas, ce qu'on ne peut pas
    écrire ne se pose pas. En V0 il n'y a qu'un compte, donc l'ACL est permissive — mais la
    portée passe par ici, pour qu'il n'y ait rien à déplacer quand elle se resserrera.

L'axe et la valeur se créent à la volée : un utilisateur qui tape « client = Untel » ne doit pas
avoir à déclarer un axe d'abord. C'est ce qui distingue un tag d'un dossier.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..journal import journal
from ..schema.models import Axe, Comm, CommTag, Compte, Rattachement, Tag
from ..uuid7 import uuid7

log = journal("api")


async def tags_of(s: AsyncSession, comm_ids: list) -> dict:
    """{comm_id: [{axe, val, source}]} — EN UNE PASSE pour toute une liste (D078).
    Une requête par message rendrait la liste inutilisable dès la deuxième page."""
    if not comm_ids:
        return {}
    lines = (await s.execute(
        select(CommTag.comm_id, Axe.nom, Tag.valeur, CommTag.source, Tag.libelle)
        .join(Tag, Tag.tag_id == CommTag.tag_id).join(Axe, Axe.axe_id == Tag.axe_id)
        .where(CommTag.comm_id.in_(comm_ids)).order_by(Axe.ordre, Axe.nom, Tag.valeur))).all()
    out: dict = {}
    for cid, axe, val, source, libelle in lines:
        # le LIBELLÉ poussé par l'application (D187) : « PR2610-0012 — client » plutôt que « 123 »
        out.setdefault(cid, []).append({"axe": axe, "val": val, "source": source, "libelle": libelle})
    return out


async def _axis(s: AsyncSession, nom: str) -> Axe:
    nom = nom.strip().lower()
    a = await s.scalar(select(Axe).where(Axe.nom == nom))
    if a is None:
        n = await s.scalar(select(Axe).order_by(Axe.ordre.desc()).limit(1))
        a = Axe(axe_id=uuid7(), nom=nom, application_id=None, acl={}, derive=False,
                ordre=((n.ordre or 0) + 1) if n else 1)
        s.add(a)
        await s.flush()
        log.info("axe « %s » créé à la volée", nom)
    return a


async def _tag(s: AsyncSession, axe: Axe, valeur: str) -> Tag:
    valeur = valeur.strip()
    t = await s.scalar(select(Tag).where(Tag.axe_id == axe.axe_id, Tag.valeur == valeur))
    if t is None:
        t = Tag(tag_id=uuid7(), axe_id=axe.axe_id, valeur=valeur, libelle=valeur, actif=True)
        s.add(t)
        await s.flush()
    return t


def _application(qui):
    """l'application derrière l'appel, ou None pour une personne (F048)"""
    from ..applications import AppPrincipal
    return qui.application if isinstance(qui, AppPrincipal) else None


async def _scope(s: AsyncSession, compte: Compte, comm_id) -> bool:
    """Le message est-il rattaché à une boîte du compte ? Hors portée = 404, jamais 403 (D108)."""
    from .messages import account_mailboxes
    mailbox_ids = [b.boite_id for b in await account_mailboxes(s, compte)]
    if not mailbox_ids:
        return False
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id,
                                                  Rattachement.boite_id.in_(mailbox_ids)).limit(1))
    return r is not None


async def add(s: AsyncSession, compte: Compte, comm_id, axe_nom: str, valeur: str,
                source: str = "manuel") -> list | None:
    """Rend la liste des tags du message, ou None si le message est hors de portée."""
    axe_nom, valeur = (axe_nom or "").strip(), (valeur or "").strip()
    if not axe_nom or not valeur:
        return None
    if not await _scope(s, compte, comm_id):
        return None
    if await s.get(Comm, comm_id) is None:
        return None
    app = _application(compte)
    if app is not None:
        # UNE APPLICATION N'ÉTIQUETTE QUE SES AXES (D019, RM3517) : ceux qu'elle déclare, qu'elle
        # possède. Elle ne crée pas d'axe à la volée — ce droit-là est celui d'une personne. Un axe
        # qui n'est pas le sien est, pour elle, un axe qui n'existe pas : 404, jamais 403 (D108).
        axe = await s.scalar(select(Axe).where(Axe.nom == axe_nom.lower(), Axe.application_id == app.application_id))
        if axe is None:
            log.warning("application « %s » : axe « %s » non déclaré — tag refusé", app.nom, axe_nom)
            return None
        source = app.type_connecteur
    else:
        axe = await _axis(s, axe_nom)
    tag = await _tag(s, axe, valeur)
    exists = await s.scalar(select(CommTag).where(CommTag.comm_id == comm_id, CommTag.tag_id == tag.tag_id))
    if exists is None:
        # clé (comm_id, tag_id) : le même tag ne se pose pas deux fois, la base le garantit
        s.add(CommTag(comm_id=comm_id, tag_id=tag.tag_id, source=source,
                      application_id=app.application_id if app is not None else None,
                      pose_le=datetime.now(timezone.utc)))
        await s.commit()
        log.info("tag %s=%s posé sur %s par %s (%s)", axe.nom, tag.valeur, comm_id, compte.login, source)
    else:
        await s.commit()          # poser deux fois le même tag est un succès silencieux (D019)
    return (await tags_of(s, [comm_id])).get(comm_id, [])


async def remove(s: AsyncSession, compte: Compte, comm_id, axe_nom: str, valeur: str) -> list | None:
    if not await _scope(s, compte, comm_id):
        return None
    axe = await s.scalar(select(Axe).where(Axe.nom == (axe_nom or "").strip().lower()))
    if axe is None:
        return None
    app = _application(compte)
    if app is not None and axe.application_id != app.application_id:
        return None                       # pas son axe : pour elle, il n'existe pas (D108)
    tag = await s.scalar(select(Tag).where(Tag.axe_id == axe.axe_id, Tag.valeur == (valeur or "").strip()))
    if tag is None:
        return None
    link = await s.scalar(select(CommTag).where(CommTag.comm_id == comm_id, CommTag.tag_id == tag.tag_id))
    if link is None:
        return None
    # Retirer un tag posé par un CONNECTEUR est un geste qui se trace (D021, Q034) : le connecteur
    # le reposera à son prochain passage, et l'utilisateur doit pouvoir comprendre pourquoi.
    if link.source != "manuel":
        log.warning("tag %s=%s retiré à la main sur %s alors qu'il vient de « %s » — il sera reposé",
                    axe.nom, tag.valeur, comm_id, link.source)
    await s.delete(link)
    await s.commit()
    log.info("tag %s=%s retiré de %s par %s", axe.nom, tag.valeur, comm_id, compte.login)
    return (await tags_of(s, [comm_id])).get(comm_id, [])
