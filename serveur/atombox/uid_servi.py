"""L'UID qu'AtomBox SERT à ses propres clients IMAP (Q024, chapitre 06).

Deux invariants, et ils ne se rattrapent pas :

- **croissant et jamais réutilisé** dans un dossier. Réutiliser un UID après une suppression ferait
  lire à un client un message pour un autre, sans qu'il s'en aperçoive : son cache est indexé par
  UID. C'est pourquoi le compteur vit sur le DOSSIER et ne fait qu'avancer, et pourquoi il n'est
  jamais recalculé depuis le plus grand UID présent ;
- **par boîte aux lettres**, pas par message. Déplacer un message lui donne un UID NEUF, pris au
  dossier d'arrivée — c'est la sémantique d'IMAP, et s'en écarter casse la synchronisation.

Ne pas confondre avec `rattachement.uid_imap` et `dossier.uid_validity`/`uid_suivant`, qui sont ceux
du FOURNISSEUR chez qui AtomBox relève (D043, F001). Ceux-ci sont les nôtres.

L'attribution est un `UPDATE … RETURNING` : elle incrémente et rend la valeur dans la même
instruction, donc deux ingestions concurrentes ne peuvent pas servir le même UID. Lire puis écrire
en deux temps, c'est se donner rendez-vous avec le doublon.
"""
from __future__ import annotations
from sqlalchemy import BigInteger, func, update
from .journal import journal
from .schema.modeles import Dossier

log = journal("imap")

# `COALESCE(…, 1) + 1` : un dossier neuf commence à 1 ; RETURNING rend la valeur NOUVELLE, donc
# l'UID attribué est celle-ci moins un.
#
# La même instruction POSE l'UIDVALIDITY s'il manque, avec un `COALESCE` : il est donc attribué une
# fois et ne bouge plus jamais — c'est tout ce qu'un client demande. On l'attribue ici, paresseusement,
# plutôt qu'à la création du dossier : les dossiers naissent à quatre endroits (amorçage, API,
# découverte IMAP, harnais de test), et un défaut posé à trois d'entre eux est un défaut qui manque.
# Le seul moment où l'UIDVALIDITY compte vraiment est celui où l'on sert quelque chose.
def _requete(dossier_id):
    return (update(Dossier).where(Dossier.dossier_id == dossier_id)
            .values(uid_servi_suivant=func.coalesce(Dossier.uid_servi_suivant, 1) + 1,
                    uid_validity_servie=func.coalesce(Dossier.uid_validity_servie,
                                                      func.extract("epoch", func.now()).cast(BigInteger)))
            .returning(Dossier.uid_servi_suivant))


def attribuer(session, dossier_id) -> int | None:
    """version synchrone — l'ingestion (F001)"""
    if dossier_id is None: return None
    return _rendu(session.scalar(_requete(dossier_id)), dossier_id)


async def attribuer_async(session, dossier_id) -> int | None:
    """version asynchrone — l'API"""
    if dossier_id is None: return None
    return _rendu(await session.scalar(_requete(dossier_id)), dossier_id)


def _rendu(suivant, dossier_id):
    if suivant is None:
        log.warning("UID demandé pour un dossier inconnu (%s) — le message ne sera pas servi en IMAP", dossier_id)
        return None
    log.debug("UID servi %d dans le dossier %s", suivant - 1, dossier_id)
    return suivant - 1
