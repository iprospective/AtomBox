"""LES DOSSIERS UTILISATEUR (F013 — D051, D047) et LES IDENTITÉS (F032 — D102, D116).

Un dossier utilisateur est une vraie entité (D051), et tant qu'IMAP est la vérité (D140b) il doit
exister des deux côtés : le créer ici et pas là-bas ferait disparaître les messages qu'on y range
au prochain passage du démon. Les dossiers protégés (INBOX, Sent…) ne se renomment ni ne se
suppriment (D047)."""
from __future__ import annotations
import os
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from ..journal import journal
from ..schema.models import Adresse, Boite, Dossier, Identite, Rattachement
from ..uuid7 import uuid7
from .. import settings

log = journal("api")

def _imap_available() -> bool: return bool(settings.read("ATOMBOX_IMAP_HOST"))


def _poller_for(adresse: str):
    """une relève ouverte sur l'adresse chez le FOURNISSEUR, ou None si l'IMAP n'est pas configuré"""
    from ..ingestion.imap import Poller, tls_imap
    from ..sync.module import config_imap, login_of
    if not _imap_available(): return None
    cfg = config_imap()
    return Poller(cfg["hote"], cfg["port"], tls=tls_imap()).connect(login_of(adresse, cfg["master"]), cfg["mot_de_passe"])


async def _imap(s: AsyncSession, boite: Boite):
    return _poller_for((await s.get(Adresse, boite.adresse_id)).adresse_complete)


def _mirror(adresse: str, action: str, *args) -> None:
    """le même geste chez le FOURNISSEUR, d'abord. Tant qu'IMAP est la vérité (D140b), un dossier créé
    ici et pas là-bas perdrait ses messages au prochain passage du démon ; et si le fournisseur
    refuse, on ne crée rien ici non plus — sinon les deux côtés divergent dès le premier geste."""
    rel = _poller_for(adresse)
    if rel is None: return
    try: getattr(rel, action)(*args)
    finally: rel.close()


def serialize_folder(d: Dossier) -> dict:
    return {"id": str(d.dossier_id), "nom": d.nom, "alias_imap": d.alias_imap,
            "protege": bool(d.protege), "ordre": d.ordre}


# ── LES RÈGLES, une seule fois ───────────────────────────────────────────────────────────────────
# Trois chemins créent, renomment et suppriment des dossiers : le webmail (asynchrone), le serveur
# IMAP d'AtomBox (synchrone, RM3499), et demain d'autres. Les règles vivent ICI, sans base : chacun
# fait ses propres requêtes, mais personne ne réécrit ce qui est permis.
class FolderRefused(ValueError):
    """un geste refusé, avec la raison à dire à l'utilisateur — et son code IMAP (RFC 5530)"""
    def __init__(self, message: str, code: str = "CANNOT"):
        super().__init__(message); self.code = code


def wire(nom: str) -> str:
    """le nom LISIBLE d'un segment → son nom sur le FIL (modified UTF-7, RFC 3501 § 5.1.3)"""
    from ..imap import mutf7
    return mutf7.encode(nom)


def readable(segment: str) -> str:
    from ..imap import mutf7
    return mutf7.decode(segment)


def check_name(nom: str) -> str:
    nom = (nom or "").strip().strip("/")
    if not nom: raise FolderRefused("un nom", "CANNOT")
    return nom


def check_renamable(d: Dossier) -> None:
    if d.protege or d.exit_reason:
        raise FolderRefused("un dossier protégé ne se renomme pas (D047)", "CANNOT")


def check_deletable(d: Dossier, messages: int, children: int) -> None:
    if d.protege or d.exit_reason:
        raise PermissionError("un dossier protégé ne se supprime pas (D047)")
    if children:
        raise FolderRefused("le dossier contient %d sous-dossier(s) — les supprimer d'abord" % children, "INUSE")
    if messages:
        # D118 : un rattachement n'est jamais effacé. Supprimer un dossier plein détruirait le
        # rangement de ses messages sans qu'on sache où les mettre ; on le dit plutôt que de choisir.
        raise FolderRefused("le dossier contient %d message(s) — le vider d'abord" % messages, "INUSE")


def forget_as_origin(dossier_id):
    """les messages qui se SOUVIENNENT de ce dossier l'oublient — avant qu'il disparaisse.

    Un message garde le dernier dossier ordinaire où il est passé (D088), pour y revenir quand il
    sort de la corbeille ou des archives. Supprimer ce dossier, même VIDE, violait la clé étrangère :
    le webmail rendait une erreur interne, le client IMAP « erreur interne » — sur un dossier
    qu'aucun message n'occupait plus. Oublier l'origine ne détruit rien : un message sans origine
    revient dans INBOX (`mailbox._target_query`), ce qui est la seule place évidente quand la
    sienne n'existe plus."""
    return update(Rattachement).where(Rattachement.dossier_origine_id == dossier_id).values(dossier_origine_id=None)


def renamed_alias(old: str, new_parent: str, nom: str) -> str:
    return (new_parent + "/" if new_parent else "") + nom


# ── le chemin du webmail (asynchrone) ────────────────────────────────────────────────────────────
async def create_folder(s: AsyncSession, boite: Boite, nom: str, parent: Dossier | None = None) -> dict:
    nom = check_name(nom)
    # « Pièces » tapé dans le webmail : le nom LISIBLE reste `nom`, le nom du FIL part chez le
    # fournisseur. Sans ce codage, imaplib refusait d'envoyer un nom non ASCII.
    alias = ((parent.alias_imap + "/") if parent and parent.alias_imap else "") + wire(nom)
    if await s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id, Dossier.alias_imap == alias)):
        raise ValueError("ce dossier existe déjà")
    _mirror((await s.get(Adresse, boite.adresse_id)).adresse_complete, "create_folder", alias)
    d = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=nom, alias_imap=alias,
                parent_id=parent.dossier_id if parent else None, protege=False)
    s.add(d); await s.commit()
    log.info("dossier « %s » créé dans %s", alias, boite.boite_id)
    return serialize_folder(d)

async def rename_folder(s: AsyncSession, boite: Boite, d: Dossier, nom: str) -> dict:
    if d.protege: raise PermissionError("un dossier protégé ne se renomme pas (D047)")
    nom = check_name(nom)
    old = d.alias_imap or ""
    parent = old.rsplit("/", 1)[0] if "/" in old else ""
    alias = renamed_alias(old, parent, wire(nom))
    _mirror((await s.get(Adresse, boite.adresse_id)).adresse_complete, "rename_folder", old, alias)
    d.nom, d.alias_imap = nom, alias
    # LES SOUS-DOSSIERS SUIVENT. Le fournisseur les renomme de lui-même (RFC 3501 § 6.3.5) ; ici,
    # leur alias gardait l'ancien préfixe, et la relève suivante ne les retrouvait plus.
    for enfant in await s.scalars(select(Dossier).where(Dossier.boite_id == boite.boite_id,
                                                         Dossier.alias_imap.like(old + "/%"))):
        enfant.alias_imap = alias + enfant.alias_imap[len(old):]
    await s.commit()
    return serialize_folder(d)

async def delete_folder(s: AsyncSession, boite: Boite, d: Dossier) -> None:
    n = await s.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.dossier_id == d.dossier_id))
    k = await s.scalar(select(func.count()).select_from(Dossier).where(Dossier.parent_id == d.dossier_id))
    check_deletable(d, n or 0, k or 0)
    _mirror((await s.get(Adresse, boite.adresse_id)).adresse_complete, "delete_folder", d.alias_imap)
    await s.execute(forget_as_origin(d.dossier_id))
    await s.delete(d); await s.commit()
    log.info("dossier « %s » supprimé", d.alias_imap)


# ── le chemin du serveur IMAP d'AtomBox (synchrone, RM3499) ──────────────────────────────────────
def create_folder_sync(s, boite: Boite, alias: str) -> Dossier:
    """CREATE — avec la hiérarchie : « Projets/Dupont/2026 » crée les niveaux qui manquent
    (RFC 3501 § 6.3.3 : le serveur DEVRAIT créer les noms supérieurs nécessaires)."""
    parts = [check_name(x) for x in (alias or "").strip("/").split("/")]
    if s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id, Dossier.alias_imap == "/".join(parts))):
        raise FolderRefused("ce dossier existe déjà", "ALREADYEXISTS")
    adresse = s.get(Adresse, boite.adresse_id).adresse_complete
    parent, d = None, None
    for i in range(len(parts)):
        a = "/".join(parts[:i + 1])
        d = s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id, Dossier.alias_imap == a))
        if d is None:
            _mirror(adresse, "create_folder", a)
            d = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=readable(parts[i]), alias_imap=a,
                        parent_id=parent.dossier_id if parent else None, protege=False)
            s.add(d); s.flush()
            log.info("dossier « %s » créé dans %s (IMAP)", a, boite.boite_id)
        elif d.exit_reason:
            raise FolderRefused("on ne range pas de dossier sous une boîte d'état (%s)" % a, "CANNOT")
        parent = d
    s.commit()
    return d


def rename_folder_sync(s, boite: Boite, d: Dossier, new_alias: str) -> Dossier:
    """RENAME — y compris vers un autre parent, que l'on crée s'il manque ; les sous-dossiers suivent."""
    check_renamable(d)
    parts = [check_name(x) for x in (new_alias or "").strip("/").split("/")]
    new = "/".join(parts)
    if s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id, Dossier.alias_imap == new)):
        raise FolderRefused("ce nom est déjà pris", "ALREADYEXISTS")
    old = d.alias_imap or ""
    if new == old or new.startswith(old + "/"):
        raise FolderRefused("on ne range pas un dossier dans lui-même", "CANNOT")
    parent = None
    if len(parts) > 1:
        parent = s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id,
                                                Dossier.alias_imap == "/".join(parts[:-1])))
        if parent is not None and (parent.exit_reason or parent.protege):
            # Thunderbird « supprime » un dossier en le rangeant sous la Corbeille. Chez nous la
            # corbeille est un ÉTAT (D183), pas un conteneur de dossiers : on le dit franchement.
            raise FolderRefused("on ne range pas de dossier sous « %s » : c'est une boîte d'état — "
                                "supprimer le dossier une fois vidé" % parent.alias_imap, "CANNOT")
        if parent is None:
            parent = create_folder_sync(s, boite, "/".join(parts[:-1]))
    adresse = s.get(Adresse, boite.adresse_id).adresse_complete
    _mirror(adresse, "rename_folder", old, new)
    d.nom, d.alias_imap, d.parent_id = readable(parts[-1]), new, parent.dossier_id if parent else None
    for enfant in s.scalars(select(Dossier).where(Dossier.boite_id == boite.boite_id,
                                                  Dossier.alias_imap.like(old + "/%"))):
        enfant.alias_imap = new + enfant.alias_imap[len(old):]
    s.commit()
    log.info("dossier « %s » renommé « %s » (IMAP)", old, new)
    return d


def delete_folder_sync(s, boite: Boite, d: Dossier) -> None:
    n = s.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.dossier_id == d.dossier_id))
    k = s.scalar(select(func.count()).select_from(Dossier).where(Dossier.parent_id == d.dossier_id))
    check_deletable(d, n or 0, k or 0)
    _mirror(s.get(Adresse, boite.adresse_id).adresse_complete, "delete_folder", d.alias_imap)
    s.execute(forget_as_origin(d.dossier_id))
    s.delete(d); s.commit()
    log.info("dossier « %s » supprimé (IMAP)", d.alias_imap)

# ---- identités (F032) ------------------------------------------------------------------------
def serialize_identity(i: Identite, adresse: str) -> dict:
    return {"id": str(i.identite_id), "boite_id": str(i.boite_id), "nom_affiche": i.nom_affiche,
            "adresse": adresse, "reply_to": i.reply_to, "signature": i.signature,
            "au_nom_de": bool(i.au_nom_de), "par_defaut": bool(i.par_defaut)}

async def identities(s: AsyncSession, boites: list[Boite]) -> list[dict]:
    out = []
    for b in boites:
        adresse = (await s.get(Adresse, b.adresse_id)).adresse_complete
        for i in await s.scalars(select(Identite).where(Identite.boite_id == b.boite_id).order_by(Identite.par_defaut.desc())):
            out.append(serialize_identity(i, adresse))
    return out

async def create_identity(s: AsyncSession, boite: Boite, c: dict) -> dict:
    i = Identite(identite_id=uuid7(), boite_id=boite.boite_id, adresse_id=boite.adresse_id,
                 nom_affiche=(c.get("nom_affiche") or "").strip() or "(sans nom)",
                 reply_to=c.get("reply_to") or None, signature=c.get("signature") or None,
                 au_nom_de=bool(c.get("au_nom_de")), par_defaut=bool(c.get("par_defaut")))
    if i.par_defaut:
        for autre in await s.scalars(select(Identite).where(Identite.boite_id == boite.boite_id)): autre.par_defaut = False
    s.add(i); await s.commit()
    return serialize_identity(i, (await s.get(Adresse, boite.adresse_id)).adresse_complete)

async def update_identity(s: AsyncSession, i: Identite, c: dict) -> dict:
    for champ in ("nom_affiche", "reply_to", "signature"):
        if champ in c: setattr(i, champ, c[champ] or None)
    if "au_nom_de" in c: i.au_nom_de = bool(c["au_nom_de"])
    if c.get("par_defaut"):
        for autre in await s.scalars(select(Identite).where(Identite.boite_id == i.boite_id)): autre.par_defaut = False
        i.par_defaut = True
    await s.commit()
    b = await s.get(Boite, i.boite_id)
    return serialize_identity(i, (await s.get(Adresse, b.adresse_id)).adresse_complete)

async def delete_identity(s: AsyncSession, i: Identite) -> None:
    n = await s.scalar(select(func.count()).select_from(Identite).where(Identite.boite_id == i.boite_id))
    if n <= 1: raise ValueError("c'est la dernière identité de cette boîte")
    await s.delete(i); await s.commit()

# ---- carnet auto-collecté (F108, D109) --------------------------------------------------------
async def address_book(s: AsyncSession, boites: list[Boite], q: str = "", limit: int = 50) -> list[dict]:
    """Les adresses à qui ce compte a ÉCRIT, par fréquence puis récence. Le carnet gratuit de la
    V0 (D109) : personne ne le saisit, il se déduit des envois."""
    from ..schema.models import Comm, Participant
    ids = [b.boite_id for b in boites]
    if not ids: return []
    st = (select(Adresse.adresse_complete, func.max(Participant.nom_affiche).label("nom"),
                 func.count().label("n"), func.max(Comm.date_recue).label("dernier"))
          .join(Participant, Participant.adresse_id == Adresse.adresse_id)
          .join(Comm, Comm.comm_id == Participant.comm_id)
          .join(Rattachement, Rattachement.comm_id == Comm.comm_id)
          .where(Rattachement.boite_id.in_(ids), Comm.sens == "out", Participant.role.in_(("to", "cc")))
          .group_by(Adresse.adresse_complete).order_by(func.count().desc(), func.max(Comm.date_recue).desc()).limit(limit))
    if q: st = st.where(func.lower(Adresse.adresse_complete).contains(q.lower()))
    return [{"adresse": a, "nom": nom, "echanges": n, "dernier": d.isoformat() if d else None}
            for a, nom, n, d in (await s.execute(st)).all()]
