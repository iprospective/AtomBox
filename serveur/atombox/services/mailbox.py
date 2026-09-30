"""LES BOÎTES AUX LETTRES (D183) — et le SEUL endroit qui déplace un message de l'une à l'autre.

Une boîte aux lettres est une ligne de `dossier`. Quatre d'entre elles portent un `exit_reason` :
ce sont les états d'un message reçu, et un message est dans une et une seule (D175 § 4).

    exit_reason NULL   → INBOX, un dossier utilisateur, Envoyés, Brouillons
    processed          → Traités
    archived           → Archivés
    deleted            → Corbeille
    junk               → Indésirables

POURQUOI UNE SEULE FONCTION POUR DÉPLACER, et pourquoi elle est ici plutôt que dans le contrôleur :
trois chemins y mènent — un clic dans le webmail, un `UID MOVE` d'un client IMAP, une règle à
l'ingestion — et chacun doit faire EXACTEMENT les mêmes cinq choses :

  1. écrire `exit_reason`, qui est la vérité ;
  2. poser la date et l'auteur de CETTE transition, sans jamais écraser une date déjà posée ;
  3. déplacer `dossier_id` vers la boîte correspondante, en mémorisant le dossier d'origine ;
  4. attribuer un UID NEUF, pris dans la boîte d'arrivée ;
  5. écrire au journal des actes.

Trois implémentations de cette liste auraient divergé au premier correctif. Elle est écrite une fois.

L'UID NEUF N'EST PAS NÉGOCIABLE. En IMAP l'UID appartient à la boîte aux lettres, pas au message
(RFC 3501 § 2.3.1.1), et il doit croître dans l'ordre d'ajout. Garder l'ancien ferait qu'un message
traité aujourd'hui arriverait dans « Traités » avec un UID inférieur à ceux qui y sont déjà : un
client qui synchronise par incrément ne le verrait jamais.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from ..journal import journal
from ..schema.modeles import Dossier, Rattachement
from . import trace

log = journal("api")

# LA TABLE DES QUATRE BOÎTES D'ÉTAT : (nom affiché, nom SERVI en IMAP, attribut RFC 6154, alias
# à ADOPTER). Une seule table, lue par le service ET par la migration 0012 — deux listes auraient
# divergé au premier alias ajouté.
#
# Les noms servis sont en ASCII : IMAP encode les noms de boîtes en modified UTF-7 (RFC 3501
# § 5.1.3), que nous ne savons pas produire. Les attributs SPECIAL-USE permettent au client
# d'afficher SON libellé traduit — sauf pour « Traités », qui n'a pas d'équivalent normalisé.
#
# LES ALIAS SERVENT À ADOPTER, PAS À DEVINER. Une boîte relevée chez un fournisseur arrive avec ses
# dossiers — « Archives », « Trash », « Junk ». Ne pas les reconnaître créait une SECONDE boîte
# « Archive » à côté de la leur : le client en affichait deux, et l'utilisateur ne savait pas
# laquelle regarder. Adopter le dossier existant fait aussi que la synchronisation montante range
# le message là où le fournisseur l'attend.
STATES = {
    "processed": ("Traités", "Processed", None,
                  ("PROCESSED", "TRAITÉS", "TRAITES")),
    "archived": ("Archivés", "Archive", "\\Archive",
                 ("ARCHIVE", "ARCHIVES", "ARCHIVED", "ARCHIVÉS", "ARCHIVÉ", "ALL MAIL")),
    "deleted": ("Corbeille", "Trash", "\\Trash",
                ("TRASH", "DELETED ITEMS", "DELETED MESSAGES", "CORBEILLE")),
    "junk": ("Indésirables", "Junk", "\\Junk",
             ("JUNK", "SPAM", "JUNK E-MAIL", "INDÉSIRABLES", "INDESIRABLES")),
}

# la date et l'auteur que chaque transition pose (D175 § 4 bis)
TRANSITION_DATES = {"processed": ("processed_at", "processed_by"), "archived": ("archived_at", "archived_by"),
         "deleted": ("deleted_at", "deleted_by"), "junk": ("junk_at", "junk_by")}

JOURNAL_ACTIONS = {"processed": "processed", "archived": "archived", "deleted": "deleted", "junk": "junked"}

TRASH_RETENTION = timedelta(days=30)     # D121 — réglable par domaine, un jour


def _target_query(boite_id, valeur: str | None, origine_id):
    """le dossier d'arrivée : la boîte de l'état, ou — pour un retour en file — l'origine, à défaut INBOX"""
    if valeur is not None:
        return select(Dossier).where(Dossier.boite_id == boite_id, Dossier.exit_reason == valeur)
    if origine_id is not None:
        return select(Dossier).where(Dossier.dossier_id == origine_id)
    # « INBOX » et non le premier dossier venu : remettre un message dans « Devis 2026 » parce que
    # c'est la première ligne rendue serait pire que de le remettre à sa place évidente.
    return select(Dossier).where(Dossier.boite_id == boite_id,
                                 Dossier.exit_reason.is_(None),
                                 Dossier.alias_imap.in_(("INBOX", "Inbox", "inbox")))


def _apply_move(r: Rattachement, valeur: str | None, cible: Dossier | None, compte_id, maintenant,
              courant: Dossier | None, uid: int | None):
    """LA MUTATION, SANS AUCUNE REQUÊTE : c'est toute la raison d'être de cette fonction.

    `courant` est le dossier d'où l'on part — nécessaire pour savoir si c'était un dossier
    UTILISATEUR (qu'il faut mémoriser) ou déjà une boîte d'état (qu'il ne faut pas). `uid` est
    l'UID déjà obtenu pour la boîte d'arrivée.

    POURQUOI L'UID EST PASSÉ ET NON CALCULÉ ICI, et ça a coûté un incident. On écrivait
    `r.dossier_id` puis on appelait `attribuer()` pour l'UID. Or `attribuer()` exécute une requête,
    et SQLAlchemy VIDE alors les modifications en attente : il envoyait donc `dossier_id = Trash`
    avec l'ANCIEN `uid_servi`, qui heurtait `uq_rattachement_uid_servi` si la Corbeille utilisait
    déjà ce numéro. Symptôme côté client : « erreur interne », et rien de déplacé.

    La règle qui en sort : **entre le moment où l'on change de boîte aux lettres et celui où l'on
    pose le nouvel UID, il ne doit y avoir AUCUNE requête.** Les deux champs forment un couple ;
    les écrire séparément, c'est laisser exister un état interdit, ne serait-ce qu'un instant."""
    avant = r.exit_reason
    if cible is None:
        # PAS UN AVERTISSEMENT, UNE ERREUR : sans la boîte d'arrivée, l'état est écrit mais le
        # message ne bouge pas — c'est-à-dire exactement le symptôme « je déplace et rien ne
        # change ». `ensure_mailboxes()` les pose à l'amorçage et la migration 0012 pour l'existant ; s'il
        # en manque une, une boîte a été créée par un chemin qui ne les pose pas.
        log.error("boîte aux lettres « %s » absente de la boîte %s : l'état est écrit, le contenant "
                  "ne bouge pas. Appeler services.mailbox.ensure_mailboxes() sur cette boîte (D183)",
                  valeur, r.boite_id)
    else:
        # LE DOSSIER D'ORIGINE EST « LE DERNIER DOSSIER ORDINAIRE », pas « le premier qu'on ait vu ».
        # Un message rangé dans « Devis 2026 » puis traité doit pouvoir y revenir (D088) ; s'il passe
        # ensuite de Traités à la Corbeille, l'origine ne bouge pas — on part d'une boîte d'état,
        # qui n'est la place de personne. Garder « le premier » ramenait tout à l'INBOX.
        if (r.dossier_id is not None and r.dossier_id != cible.dossier_id
                and (courant is None or courant.exit_reason is None)):
            r.dossier_origine_id = r.dossier_id
        r.dossier_id = cible.dossier_id
        r.uid_servi = uid          # même instant, même transaction, aucune requête entre les deux
    r.exit_reason = valeur
    if valeur in TRANSITION_DATES:
        champ_date, champ_qui = TRANSITION_DATES[valeur]
        if getattr(r, champ_date) is None:
            setattr(r, champ_date, maintenant)
            setattr(r, champ_qui, compte_id)
    if valeur == "deleted":
        r.restaurable_jusqu_au = maintenant + TRASH_RETENTION
    return avant


async def move(s, r: Rattachement, valeur: str | None, compte_id, cible: Dossier | None = None) -> str | None:
    """API (session asynchrone) — rend l'état précédent.

    `cible` IMPOSE la boîte d'arrivée : un `MOVE` IMAP nomme sa destination, et déduire celle-ci de
    l'état enverrait le message dans l'INBOX alors que le client a dit « Devis 2026 »."""
    from ..uid_servi import attribuer_async
    maintenant = datetime.now(timezone.utc)
    courant = await s.get(Dossier, r.dossier_id) if r.dossier_id else None
    if cible is None:
        cible = await s.scalar(_target_query(r.boite_id, valeur, r.dossier_origine_id).limit(1))
    # L'UID D'ABORD : toutes les requêtes ont lieu AVANT la première mutation (cf. `_apply_move`).
    uid = await attribuer_async(s, cible.dossier_id) if cible is not None else None
    # ET CEINTURE EN PLUS DES BRETELLES. L'ordre suffit en principe ; `no_autoflush` garantit que
    # même une requête ajoutée ici par distraction ne pourra pas faire partir un état à moitié
    # appliqué — `dossier_id` neuf avec l'ancien `uid_servi` heurte l'unicité, et le client voit
    # « erreur interne » sans rien de déplacé. L'invariant devient structurel, pas discipliné.
    with s.no_autoflush:
        avant = _apply_move(r, valeur, cible, compte_id, maintenant, courant, uid)
    trace.record(s, compte_id, JOURNAL_ACTIONS.get(valeur or "", "refiled"), "rattachement", r.comm_id,
                 {"boite_id": str(r.boite_id), "avant": avant, "apres": valeur})
    return avant


def move_sync(s, r: Rattachement, valeur: str | None, compte_id, cible: Dossier | None = None) -> str | None:
    """IMAP et démon (session synchrone) — le même geste, la même trace"""
    from ..uid_servi import attribuer
    maintenant = datetime.now(timezone.utc)
    courant = s.get(Dossier, r.dossier_id) if r.dossier_id else None
    if cible is None:
        cible = s.scalar(_target_query(r.boite_id, valeur, r.dossier_origine_id).limit(1))
    # L'UID D'ABORD, puis `no_autoflush` : voir `deplacer` — même raison, même garantie.
    uid = attribuer(s, cible.dossier_id) if cible is not None else None
    with s.no_autoflush:
        avant = _apply_move(r, valeur, cible, compte_id, maintenant, courant, uid)
    trace.record(s, compte_id, JOURNAL_ACTIONS.get(valeur or "", "refiled"), "rattachement", r.comm_id,
                 {"boite_id": str(r.boite_id), "avant": avant, "apres": valeur})
    return avant


def state_of_folder(d: Dossier | None) -> str | None:
    return d.exit_reason if d is not None else None


def served_name(d: Dossier) -> str:
    """LE NOM QU'ON SERT EN IMAP — et il ne vient PAS de `alias_imap`.

    `alias_imap` est le nom du dossier CHEZ LE FOURNISSEUR (D043, D140b) : c'est par lui que la
    relève retrouve ses dossiers. Le réécrire a coûté un incident — la boîte avait un dossier
    « Archives » chez son fournisseur, la migration l'a adopté comme boîte d'état ET renommé son
    alias en « Archive », et le démon d'ingestion, ne retrouvant plus « Archives », en a recréé un
    À CÔTÉ. Deux dossiers pour une idée, et l'utilisateur ne sait pas lequel regarder.

    Le nom servi est donc CANONIQUE, déduit de l'état : il est le même d'une boîte à l'autre, il est
    en ASCII (IMAP encode les noms en modified UTF-7, § 5.1.3, que nous ne produisons pas), et il ne
    dépend d'aucun fournisseur. Les attributs SPECIAL-USE font que le client affiche SON libellé."""
    if d.exit_reason in STATES:
        return STATES[d.exit_reason][1]
    return d.alias_imap or d.nom


def ensure_mailboxes(s, boite_id) -> int:
    """crée les quatre boîtes d'état qui manquent à cette boîte — idempotent, en session SYNCHRONE.

    Une base montée de `schema.sql` (les tests, une instance neuve) n'a AUCUNE donnée : sans cet
    appel, `Archive` n'existe pas et un `MOVE` vers elle répond `TRYCREATE` — le client abandonne et
    l'utilisateur voit son geste ne rien faire. La migration 0012 fait la même chose pour l'existant.
    """
    from ..uuid7 import uuid7
    presents = {d.exit_reason for d in s.scalars(
        select(Dossier).where(Dossier.boite_id == boite_id, Dossier.exit_reason.isnot(None)))}
    libres = list(s.scalars(select(Dossier).where(Dossier.boite_id == boite_id,
                                                 Dossier.exit_reason.is_(None))))
    posees = 0
    for etat, (nom, servi, special, alias) in STATES.items():
        if etat in presents: continue
        existant = next((d for d in libres
                         if (d.alias_imap or d.nom or "").upper().split("/")[-1] in alias), None)
        if existant is not None:
            # ON N'ÉCRIT PAS `alias_imap` : c'est le nom du dossier chez le fournisseur, et la
            # relève s'en sert pour le retrouver. Le nom SERVI est déduit de l'état (`served_name`).
            existant.exit_reason, existant.special_use, existant.protege = etat, special, True
            libres.remove(existant)
        else:
            s.add(Dossier(dossier_id=uuid7(), boite_id=boite_id, nom=nom, alias_imap=servi,
                          protege=True, exit_reason=etat, special_use=special,
                          uid_validity_servie=int(datetime.now(timezone.utc).timestamp()),
                          uid_servi_suivant=1))
        posees += 1
    if posees:
        s.flush()
        log.info("boîte %s : %d boîte(s) aux lettres d'état posée(s) (D183)", boite_id, posees)
    return posees
