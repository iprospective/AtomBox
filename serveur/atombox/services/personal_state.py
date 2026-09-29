"""L'ÉTAT PERSONNEL D'UN MESSAGE (D175, D177, D178) — les faits de lecture et les marqueurs.

Trois plans, et c'est la distinction qui débloque tout :

    le FAIT       « ouvert le 3 à 9 h 12 »   par personne   JAMAIS effaçable   → read_state
    l'INTENTION   « à revoir »               par personne   retirable          → marker_personal
    l'ACTE SIGNÉ  « traité par Untel le 10 » la boîte       l'historique reste → rattachement

Ce module tient les deux premiers. Le troisième vit dans `messages.py`, sur le rattachement.

CE QU'IL FAUT COMPRENDRE SUR `lu` : « marquer comme non lu » n'existe plus. Le geste reste (même
bouton, même raccourci, même gras dans la liste), mais il pose le marqueur « à revoir » au lieu
d'effacer la date d'ouverture. On n'efface pas un fait pour exprimer une intention — et c'était la
seule trace que quelqu'un avait regardé le message, sur une boîte partagée où ça compte.

LA RELÈVE (D177). Pendant un congé, on lit l'état de la personne qu'on remplace À DÉFAUT du sien :
`acces.stands_in_for` le dit, par accès, donc par boîte, et ça s'éteint tout seul à la fin de
l'accès. On s'y REPLIE, on ne COPIE pas — copier, c'est 40 000 insertions figées à t₀, qui restent
après la révocation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from ..journal import journal
from ..schema.modeles import Acces, Marker, MarkerPersonal, Rattachement, ReadState

log = journal("api")

A_REVOIR = "to_review"
SOMMEIL = "snooze"


# ── ce que le compte a ouvert, en SQL ───────────────────────────────────────────────────────────
def ouvert_par(compte_id):
    """« ce compte a-t-il ouvert ce rattachement ? » — un EXISTS corrélé, avec la relève.

    EXISTS et non une jointure externe : une jointure multiplierait les lignes, et tous les
    `count()` déjà écrits changeraient de valeur sans qu'on le voie. Ici la cardinalité de la
    requête appelante ne bouge pas d'un pouce.

    La relève tombe dedans toute seule : on joint l'ACCÈS du compte à cette boîte, et l'on accepte
    aussi l'état de `stands_in_for`. Poser cette colonne EST l'adhésion au repli (D177 § 3) ; sans
    elle, la sous-requête ne voit que mes propres lignes."""
    return (select(ReadState.compte_id)
            .join(Acces, and_(Acces.boite_id == ReadState.boite_id,
                              Acces.compte_id == compte_id, Acces.fin.is_(None)))
            .where(ReadState.comm_id == Rattachement.comm_id,
                   ReadState.boite_id == Rattachement.boite_id,
                   or_(ReadState.compte_id == compte_id,
                       ReadState.compte_id == Acces.stands_in_for),
                   ReadState.opened_at.isnot(None))
            .exists())


def non_ouvert_par(compte_id):
    """jamais ouvert PAR MOI (ou par celui que je relève)"""
    return ~ouvert_par(compte_id)


def marque_par(compte_id, code: str):
    """« ce compte a-t-il posé CE marqueur sur ce rattachement ? » — un EXISTS corrélé de plus"""
    return (select(MarkerPersonal.compte_id)
            .join(Marker, Marker.marker_id == MarkerPersonal.marker_id)
            .where(MarkerPersonal.comm_id == Rattachement.comm_id,
                   MarkerPersonal.boite_id == Rattachement.boite_id,
                   MarkerPersonal.compte_id == compte_id, Marker.code == code)
            .exists())


def a_voir_par(compte_id):
    """CE QUE LA LISTE MET EN GRAS, et donc ce que le compteur doit compter : jamais ouvert, OU
    remis de côté par « à revoir ».

    Sans le second terme, D175 § 2 n'était pas tenue : le geste « marquer comme non lu » n'effaçait
    plus rien — parfait —, mais le message ne revenait pas dans la liste, donc le geste ne servait
    plus à rien. Un test l'a trouvé. Et le compteur lit la MÊME expression que la liste, parce que
    D166 interdit qu'ils disent deux choses."""
    return or_(non_ouvert_par(compte_id), marque_par(compte_id, A_REVOIR))


# ── lire l'état de toute une liste, en une passe ────────────────────────────────────────────────
async def etats_de(s: AsyncSession, compte_id, comm_ids: list) -> dict:
    """{(comm_id, boite_id): {"lu": bool, "drapeau": bool, "a_revoir": bool, "sommeil": iso|None}}

    Une requête pour la liste entière, comme les tags (D078) : une requête par ligne rendrait la
    deuxième page inutilisable. Les clés absentes veulent dire « personne n'y a touché » — la table
    est creuse, et c'est son intérêt."""
    if not comm_ids: return {}
    out: dict = {}
    lignes = await s.execute(select(ReadState).where(ReadState.compte_id == compte_id,
                                                    ReadState.comm_id.in_(comm_ids)))
    for (r,) in lignes:
        out.setdefault((r.comm_id, r.boite_id), {}).update(
            lu=r.opened_at is not None, drapeau=bool(r.flagged),
            ouvert_le=r.opened_at, vu_le=r.last_seen_at, nb_ouvertures=r.open_count)
    marques = await s.execute(select(MarkerPersonal, Marker.code)
                              .join(Marker, Marker.marker_id == MarkerPersonal.marker_id)
                              .where(MarkerPersonal.compte_id == compte_id,
                                     MarkerPersonal.comm_id.in_(comm_ids)))
    for m, code in marques:
        e = out.setdefault((m.comm_id, m.boite_id), {})
        if code == A_REVOIR: e["a_revoir"] = True
        elif code == SOMMEIL: e["sommeil"] = m.due_at
        e.setdefault("marqueurs", []).append(code)
    return out


def serialiser_etat(e: dict | None) -> dict:
    """ce que le webmail lit — les noms du contrat (D141), pas ceux des colonnes"""
    e = e or {}
    return {"lu": bool(e.get("lu")), "drapeau": bool(e.get("drapeau")),
            "a_revoir": bool(e.get("a_revoir")),
            "sommeil": e["sommeil"].astimezone(timezone.utc).isoformat() if e.get("sommeil") else None,
            "marqueurs": e.get("marqueurs") or []}


# ── écrire les faits ────────────────────────────────────────────────────────────────────────────
# Les ÉCRITURES sont rendues sous forme d'ORDRES, pas exécutées : l'API tient une session
# asynchrone, le démon d'ingestion une session synchrone, et les deux doivent poser exactement le
# même fait. Deux implémentations auraient divergé au premier correctif — c'est arrivé ailleurs.
#
#     await s.execute(ordre_ouvrir(...))     depuis l'API
#     s.execute(ordre_ouvrir(...))           depuis le démon

def ordre_ouvrir(compte_id, comm_id, boite_id, quand=None):
    """OUVERT : la première fois pose `opened_at` et ne la retouche plus jamais.

    Un UPSERT et non « lire, puis écrire » : deux onglets qui ouvrent le même message en même temps
    feraient sinon deux INSERT dont un échoue. `open_count` s'incrémente côté SGBD pour la même
    raison — lire, ajouter un, écrire, c'est perdre un compte dès qu'on est deux."""
    maintenant = quand or datetime.now(timezone.utc)
    st = insert(ReadState).values(compte_id=compte_id, comm_id=comm_id, boite_id=boite_id,
                                 opened_at=maintenant, last_seen_at=maintenant,
                                 open_count=1, flagged=False)
    # COALESCE et non `excluded` : la PREMIÈRE ouverture gagne pour toujours. Écrire `excluded`
    # aurait fait d'`opened_at` la DERNIÈRE ouverture — un doublon de `last_seen_at` —, et l'on
    # aurait perdu sans le voir le seul fait que D175 protège.
    return st.on_conflict_do_update(
        constraint="pk_read_state",
        set_={"opened_at": func.coalesce(ReadState.opened_at, st.excluded.opened_at),
              "last_seen_at": maintenant, "open_count": ReadState.open_count + 1})


def ordre_drapeau(compte_id, comm_id, boite_id, flagged: bool, quand=None):
    """pose ou retire le drapeau — crée la ligne au besoin, SANS prétendre à une ouverture.

    C'est pour ce cas qu'`opened_at` est nullable : mettre un drapeau sur un message qu'on n'a pas
    ouvert est un geste courant, et inventer une ouverture pour avoir une ligne serait un faux."""
    maintenant = quand or datetime.now(timezone.utc)
    st = insert(ReadState).values(compte_id=compte_id, comm_id=comm_id, boite_id=boite_id,
                                 opened_at=None, last_seen_at=maintenant, open_count=0,
                                 flagged=bool(flagged))
    return st.on_conflict_do_update(constraint="pk_read_state", set_={"flagged": bool(flagged)})


async def ouvrir(s: AsyncSession, compte_id, comm_id, boite_id) -> None:
    await s.execute(ordre_ouvrir(compte_id, comm_id, boite_id))


async def toucher(s: AsyncSession, compte_id, comm_id, boite_id, flagged: bool | None = None) -> None:
    await s.execute(ordre_drapeau(compte_id, comm_id, boite_id, bool(flagged)))


def compte_releveur(s, boite_id):
    """LE compte sur qui la synchronisation IMAP descendante impute l'état (D175 § 3).

    L'IMAP d'un FOURNISSEUR n'a qu'un jeu de drapeaux pour toute la boîte : il ne dit pas qui a lu.
    On l'impute donc au membre qui relève — mais seulement s'il n'y en a qu'un. À plusieurs, on ne
    choisit pas : un faux fait ne se distingue plus d'un vrai, et c'est irréversible. Le jour où
    l'IMAP sortant (D174) est la seule porte, la question ne se pose plus : chacun s'y connecte avec
    son compte, et le drapeau est personnel par construction."""
    lignes = list(s.scalars(select(Acces.compte_id)
                            .where(Acces.boite_id == boite_id, Acces.fin.is_(None))))
    return lignes[0] if len(lignes) == 1 else None


class EtatPersonnel:
    """L'état d'un message pour UNE personne, réduit à ce que les deux IMAP en tirent.

    Un objet de valeur et non la ligne ORM, pour une raison précise : `vu` n'est PAS `opened_at`.
    Un message ouvert puis remis de côté (« à revoir ») doit reparaître en gras — dans le webmail
    comme dans Thunderbird. On sert donc `\\Seen` sur `vu`, et le fait (`opened_at`) reste écrit
    dessous, intact. C'est la projection IMAP de D175 § 2, et c'est ce qui évite que les deux
    affichages divergent."""

    __slots__ = ("opened_at", "last_seen_at", "flagged", "a_revoir")

    def __init__(self, opened_at=None, last_seen_at=None, flagged=False, a_revoir=False):
        self.opened_at, self.last_seen_at = opened_at, last_seen_at
        self.flagged, self.a_revoir = bool(flagged), bool(a_revoir)

    @property
    def vu(self) -> bool:
        return self.opened_at is not None and not self.a_revoir


def etat_sync(s, compte_id, comm_id, boite_id) -> EtatPersonnel | None:
    """l'état d'UN message pour UN compte, en session synchrone (le démon, le serveur IMAP)"""
    if compte_id is None: return None
    ligne = s.get(ReadState, (compte_id, comm_id, boite_id))
    marque = s.scalar(select(MarkerPersonal.set_at)
                      .join(Marker, Marker.marker_id == MarkerPersonal.marker_id)
                      .where(MarkerPersonal.compte_id == compte_id, MarkerPersonal.comm_id == comm_id,
                             MarkerPersonal.boite_id == boite_id, Marker.code == A_REVOIR))
    if ligne is None and marque is None: return None
    return EtatPersonnel(opened_at=ligne.opened_at if ligne else None,
                         last_seen_at=ligne.last_seen_at if ligne else None,
                         flagged=ligne.flagged if ligne else False,
                         a_revoir=marque is not None)


# ── les marqueurs ───────────────────────────────────────────────────────────────────────────────
# Même principe que pour les faits : l'ORDRE d'un côté, les deux façons de le passer de l'autre.

def ordre_poser(marker_id, compte_id, comm_id, boite_id, due_at=None, value=None, quand=None):
    st = insert(MarkerPersonal).values(compte_id=compte_id, comm_id=comm_id, boite_id=boite_id,
                                       marker_id=marker_id, set_at=quand or datetime.now(timezone.utc),
                                       due_at=due_at, value=value)
    return st.on_conflict_do_update(constraint="pk_marker_personal",
                                    set_={"due_at": due_at, "value": value})


def ordre_retirer(marker_id, compte_id, comm_id, boite_id):
    return delete(MarkerPersonal).where(MarkerPersonal.compte_id == compte_id,
                                        MarkerPersonal.comm_id == comm_id,
                                        MarkerPersonal.boite_id == boite_id,
                                        MarkerPersonal.marker_id == marker_id)


def _requete_marqueur(code: str):
    return select(Marker).where(Marker.code == code, Marker.actif.is_(True))


def _verifier(m, code: str):
    """un marqueur COLLECTIF n'a rien à faire dans la table personnelle : la portée est déclarée
    une fois pour toutes (D178), et s'y tromper mettrait l'annotation de la boîte sur une personne"""
    if m is None:
        log.warning("marqueur inconnu ou désactivé : %s", code); return False
    if m.scope != "personal":
        log.warning("marqueur « %s » est de portée collective — pas cette table (D178)", code); return False
    return True


async def poser(s: AsyncSession, compte_id, comm_id, boite_id, code: str, due_at=None, value=None) -> bool:
    m = await s.scalar(_requete_marqueur(code))
    if not _verifier(m, code): return False
    await s.execute(ordre_poser(m.marker_id, compte_id, comm_id, boite_id, due_at, value))
    return True


async def retirer(s: AsyncSession, compte_id, comm_id, boite_id, code: str) -> bool:
    m = await s.scalar(_requete_marqueur(code))
    if m is None: return False
    await s.execute(ordre_retirer(m.marker_id, compte_id, comm_id, boite_id))
    return True


def poser_sync(s, compte_id, comm_id, boite_id, code: str, due_at=None, value=None) -> bool:
    m = s.scalar(_requete_marqueur(code))
    if not _verifier(m, code): return False
    s.execute(ordre_poser(m.marker_id, compte_id, comm_id, boite_id, due_at, value))
    return True
