"""LE SERVICE DES MESSAGES — ce que le webmail lit (le contrat : les noms de champs.yml, D141),
depuis les modèles (D158), dans la portée du compte (D036 : le rattachement EST la portée).

Les dossiers du webmail : des identifiants courts pour les spéciaux (inbox, sent, drafts, junk,
trash — les alias IMAP protégés, D047), des vues calculées (traites, archives — D051), l'UUID
d'un dossier utilisateur, et les dossiers virtuels personnels (perso:…, D143)."""
from __future__ import annotations
import base64, email.message, email.policy, email.utils, os, re, socket, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, case, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.models import Acces, Adresse, Blob, Boite, Comm, CommCitation, CommEmail, CommPieceJointe, Compte, Dossier, Filtre, Participant, PieceJointe, Rattachement
from ..uuid7 import uuid7
from ..journal import journal
from ..sync import sync
from . import mailbox
from . import personal_state as personal
from . import trace
from .. import settings

log = journal("api")

SPECIAL = [ {"id": "inbox", "label": "Boîte de réception", "icon": "📥", "alias": ("INBOX",)},
             {"id": "sent", "label": "Envoyés", "icon": "📤", "alias": ("SENT", "SENT ITEMS", "ENVOYÉS", "ENVOYES"), "sortant": True},
             {"id": "drafts", "label": "Brouillons", "icon": "📝", "alias": ("DRAFTS", "BROUILLONS")},
             {"id": "junk", "label": "Indésirables", "icon": "🚫", "alias": ("JUNK", "SPAM", "INDÉSIRABLES")},
             {"id": "trash", "label": "Corbeille", "icon": "🗑", "alias": ("TRASH", "DELETED ITEMS", "CORBEILLE")},
             {"id": "traites", "label": "Traités", "icon": "✓", "vue": True, "alias": ()},
             {"id": "archives", "label": "Archives", "icon": "🗄", "vue": True, "alias": ()} ]
# Les identifiants sont en anglais (D181), les libellés en français : c'est le code qui voyage
# entre le serveur, le webmail et la base, pas le mot affiché.
STATUSES = [ {"id": "new", "label": "Nouveau"}, {"id": "todo", "label": "À faire"}, {"id": "doing", "label": "En cours"},
            {"id": "waiting", "label": "En attente"}, {"id": "processed", "label": "Traité"} ]
IN_PROGRESS = ("todo", "doing")           # ce que le compteur « à faire » compte (D176 § 4)
VIEWS = ["trash", "junk", "archives", "traites"]

def special_of(alias: str | None) -> str | None:
    a = (alias or "").upper().split("/")[-1]
    for s in SPECIAL:
        if a in s["alias"]: return s["id"]
    return None

# Les quatre boîtes d'état (D183) sont des lignes de `dossier` : sans cette table, elles
# apparaîtraient dans l'arborescence comme des dossiers utilisateur nommés « Processed ».
SHORT_ID_OF_STATE = {"processed": "traites", "archived": "archives", "deleted": "trash", "junk": "junk"}

def short_folder_id(d: Dossier | None) -> str | None:
    if d is None: return None
    if d.exit_reason: return SHORT_ID_OF_STATE.get(d.exit_reason, d.exit_reason)
    return special_of(d.alias_imap) or str(d.dossier_id)

def iso(t: datetime | None) -> str | None: return t.astimezone(timezone.utc).isoformat() if t else None

# Les quatre transitions, et la date/l'auteur que chacune pose. UNE seule colonne d'état courant
# (`exit_reason`), mais quatre couples de dates : un message est généralement traité PUIS archivé
# des années après, et si l'archivage écrasait la date de traitement on perdrait la clé d'archivage
# (D014) — la donnée qui commande la transition suivante (D175 § 4 bis).
EXIT_DATES = { "processed": ("processed_at", "processed_by"), "archived": ("archived_at", "archived_by"),
            "deleted": ("deleted_at", "deleted_by"), "junk": ("junk_at", "junk_by") }

def exit_date(r: Rattachement) -> datetime | None:
    """la date de l'état COURANT — ce que l'ancien `sorti_le` disait, sans l'écraser au passage"""
    champ = EXIT_DATES.get(r.exit_reason or "")
    return getattr(r, champ[0]) if champ else None

def when(v) -> datetime | None:
    """ce que le webmail envoie : un nombre de millisecondes, ou une ISO 8601, ou null"""
    if v is None or v is False: return None
    if isinstance(v, (int, float)): return datetime.fromtimestamp(v / 1000, tz=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

async def account_mailboxes(s: AsyncSession, compte: Compte) -> list[Boite]:
    """LA PORTÉE de celui qui appelle : les accès en cours d'une personne, ou la portée déclarée
    d'une application (F048) — un seul chemin, pour que toutes les routes l'appliquent de même."""
    from ..applications import AppPrincipal, mailboxes
    if isinstance(compte, AppPrincipal): return await mailboxes(s, compte.application)
    return list(await s.scalars(select(Boite).join(Acces, Acces.boite_id == Boite.boite_id)
                                .where(Acces.compte_id == compte.compte_id, Acces.fin.is_(None))))

def chosen(boites: list, wanted: str | None) -> list:
    """LE FILTRE EN AMONT (D176 § 3) : les boîtes cochées, parmi celles du compte. Absent = toutes.
    Le paramètre est TOUJOURS intersecté avec les accès : une boîte qu'on ne voit pas, citée dans
    l'URL, ne s'ajoute pas — elle est ignorée, et une sélection qui n'en garde aucune ne montre rien."""
    if not wanted: return boites
    ids = set()
    for x in wanted.split(","):
        try: ids.add(uuid.UUID(x.strip()))
        except ValueError: pass
    return [b for b in boites if b in ids]

async def _axes_and_values(s: AsyncSession) -> dict:
    """Les axes de classement et leurs valeurs (D002, D016) — ils étaient rendus `[]` et `{}` EN DUR.
    Conséquence visible : le formulaire « mes dossiers + » faisait `axes[0].id` sur une liste vide,
    levait, et le clic mourait en silence. Un référentiel vide n'est pas un référentiel neutre :
    tout ce qui s'appuie dessus casse sans le dire.

    Une seule requête pour les deux : un axe sans valeur existe (on vient de le créer), une valeur
    sans axe n'existe pas."""
    from ..schema.models import Application, Axe, Tag
    from ..connectors import declaration
    axes = list(await s.scalars(select(Axe).order_by(Axe.ordre, Axe.nom)))
    # LE LIBELLÉ, pas la clé (D187) : « PR2610-0012 — client » se lit, « 123 » non. La clé reste
    # dans `val` — c'est elle qu'on pose ; poser le libellé créerait une seconde valeur fantôme.
    lines = (await s.execute(select(Axe.nom, Tag.valeur, Tag.libelle).join(Tag, Tag.axe_id == Axe.axe_id)
                              .where(Tag.actif.is_(True)).order_by(Axe.nom, Tag.libelle))).all()
    values: dict = {a.nom: [] for a in axes}
    for nom, val, libelle in lines:
        values.setdefault(nom, []).append({"id": "%s:%s" % (nom, val), "label": libelle or val, "val": val, "axe": nom})
    # le nom d'un axe déclaré vient de son connecteur : « Propositions commerciales », pas « Propal »
    apps = {i: (t, (p or {}).get("url")) for i, t, p in
            (await s.execute(select(Application.application_id, Application.type_connecteur, Application.parametres))).all()} if axes else {}
    types = {i: t for i, (t, _) in apps.items()}
    def label(a):
        d = declaration(types.get(a.application_id)) if a.application_id else None
        return ((d or {}).get("axes") or {}).get(a.nom, {}).get("libelle") or a.nom.replace("_", " ").capitalize()
    # LA FAMILLE (D188) : elle range les axes dans la navigation et nomme les tags au survol
    from ..schema.models import Famille
    familles = list(await s.scalars(select(Famille).order_by(Famille.ordre, Famille.nom))) if axes else []
    nom_famille = {f.famille_id: f.nom for f in familles}
    def lien(a):
        """F149 : la fiche d'une valeur chez l'application — `{id}` est remplacé par le webmail.
        Rien sans adresse déclarée : un lien cassé est pire qu'une puce sans lien."""
        if not a.application_id or a.application_id not in apps: return None
        t, url = apps[a.application_id]
        modele = (((declaration(t) or {}).get("fiches") or {}).get(a.nom))
        return (url.rstrip("/") + modele) if url and modele else None
    return {"axes": [{"id": a.nom, "label": label(a), "derive": a.derive, "famille": nom_famille.get(a.famille_id), "lien": lien(a)} for a in axes],
            "familles": [{"id": f.nom, "label": f.libelle} for f in familles],
            "valeurs": values}


def _folder_tag(dossier: str):
    """(axe, valeur) d'une branche de l'arborescence, ou None si ce n'en est pas une.

    Deux formes, fixées par le SERVEUR puisque c'est lui qui sert le référentiel (D141) :
      `axe:<nom>`      la tête — TOUTE la famille, « tout ce qui porte un projet » ;
      `<axe>:<valeur>` une valeur précise.
    Le découpage se fait sur le PREMIER deux-points : une valeur peut en contenir."""
    if not dossier or ":" not in dossier:
        return None
    gauche, _, droite = dossier.partition(":")
    if gauche == "axe":
        return (droite, None)
    if gauche in ("perso", "recherche"):
        return None
    return (gauche, droite)


async def references(s: AsyncSession, compte: Compte) -> dict:
    boites = await account_mailboxes(s, compte)
    adresses = {b.boite_id: (await s.get(Adresse, b.adresse_id)).adresse_complete for b in boites}
    dossiers = list(await s.scalars(select(Dossier).where(Dossier.boite_id.in_([b.boite_id for b in boites])).order_by(Dossier.ordre, Dossier.nom)))
    util = [ {"id": str(d.dossier_id), "label": d.nom, "icon": "📁", "boite": adresses.get(d.boite_id)}
             for d in dossiers if not special_of(d.alias_imap) and not d.exit_reason ]
    # `action` sans action : NULL SQL, ou le JSON `null` des lignes écrites avant le correctif —
    # les deux veulent dire « ce filtre est un dossier virtuel, pas une règle » (D143).
    sans_action = or_(Filtre.action.is_(None), func.jsonb_typeof(Filtre.action) == "null")
    virtuels = list(await s.scalars(select(Filtre).where(Filtre.portee_type == "compte", Filtre.portee_id == compte.compte_id, sans_action, Filtre.actif.is_(True)).order_by(Filtre.ordre)))
    return { "moi": {"nom": compte.nom, "login": compte.login, "boites": [{"id": str(b.boite_id), "adresse": adresses[b.boite_id], "label": adresses[b.boite_id].split("@")[0]} for b in boites]},
             "speciaux": [{"id": x["id"], "label": x["label"], "icon": x["icon"], **({"vue": True} if x.get("vue") else {}), **({"sortant": True} if x.get("sortant") else {})} for x in SPECIAL],
             "util": util, **(await _axes_and_values(s)), "statuts": STATUSES, "vues": VIEWS,
             "virtuels": [{"id": "perso:" + str(f.filtre_id), "label": f.nom, "criteres": (f.predicat or {}).get("criteres", [])} for f in virtuels],
             "applications": await _applications_for(s, [b.boite_id for b in boites]) }

async def _applications_for(s: AsyncSession, boites: list) -> list[dict]:
    """CE QUE LE WEBMAIL DOIT SAVOIR DES APPLICATIONS (D189 § 3) : laquelle range les tiers (son axe
    de règle d'adresse), et où créer un inconnu — les modèles du connecteur, préfixés par l'adresse
    que le module a déclarée. Seulement les applications dont la portée touche les boîtes du compte,
    et seulement si l'adresse est connue : pas de lien cassé."""
    from ..schema.models import Application
    from ..applications import mailboxes
    from ..connectors import declaration
    out = []
    for app in await s.scalars(select(Application).where(Application.actif.is_(True))):
        d = declaration(app.type_connecteur) or {}
        url = ((app.parametres or {}).get("url") or "").rstrip("/")
        axe = (d.get("regle_adresse") or {}).get("axe")
        if not axe or not url: continue
        if not {b.boite_id for b in await mailboxes(s, app)} & set(boites): continue
        out.append({"nom": app.nom, "type": app.type_connecteur, "libelle": d.get("libelle") or app.type_connecteur,
                    "axe_tiers": axe, "url": url,
                    "creation": {k: url + v for k, v in (d.get("creation") or {}).items() if not k.startswith("_")}})
    return out


def _tag_condition(axe: str, val: str | None):
    """Un dossier virtuel sur un TAG — sa raison d'être (D143). `val` absente = toute la FAMILLE :
    « tout ce qui porte un client », quel qu'il soit. C'est ce que demande « un dossier virtuel
    depuis un tag OU une famille de tags ».

    EXISTS plutôt qu'une jointure : un message portant trois tags du même axe doit apparaître une
    fois, pas trois — et la liste ne doit pas avoir à dédupliquer après coup."""
    from ..schema.models import Axe, CommTag, Tag
    sous = (select(CommTag.comm_id).join(Tag, Tag.tag_id == CommTag.tag_id)
            .join(Axe, Axe.axe_id == Tag.axe_id)
            .where(CommTag.comm_id == Comm.comm_id, Axe.nom == (axe or "").strip().lower()))
    if val and str(val).strip():
        sous = sous.where(Tag.valeur == str(val).strip())
    return sous.exists()


def _scope(compte_boites):
    return Rattachement.boite_id.in_(compte_boites)


def _place(comm_id, boites, sens=None):
    """LA place d'un message pour ce compte (D185) : celle du sens demandé, sinon la REÇUE si elle
    existe (`in` < `out`), sinon la seule — un ordre, jamais le hasard d'un `limit(1)`"""
    q = select(Rattachement).where(Rattachement.comm_id == comm_id, _scope(boites))
    if sens: q = q.where(Rattachement.sens == sens)
    return q.order_by(Rattachement.sens).limit(1)


async def twins(s: AsyncSession, places) -> set:
    """les (message, boîte) qui ont DEUX places — reçue et émise : leur place émise prend « .out »"""
    outs = [(r.comm_id, r.boite_id) for r in places if r.sens == "out"]
    if not outs: return set()
    rows = (await s.execute(select(Rattachement.comm_id, Rattachement.boite_id)
                            .where(Rattachement.sens == "in", Rattachement.comm_id.in_([c for c, _ in outs])))).all()
    return set(rows) & set(outs)


def place_id(r: Rattachement, twin: bool = False) -> str:
    return str(r.comm_id) + (".out" if twin and r.sens == "out" else "")

async def _folders_by_id(s: AsyncSession, boites) -> dict:
    ds = list(await s.scalars(select(Dossier).where(Dossier.boite_id.in_(boites))))
    return {d.dossier_id: d for d in ds}

async def counters(s: AsyncSession, compte: Compte, wanted: str | None = None) -> dict:
    """UNE passe (D078) : par dossier, total / non lus / à faire — et les vues trash, archives, traites.
    `wanted` : les boîtes cochées (D176 § 3) — elles restreignent TOUS les compteurs de dossiers,
    sauf ceux des boîtes elles-mêmes, qui disent ce qu'on décoche."""
    toutes = [b.boite_id for b in await account_mailboxes(s, compte)]
    if not toutes: return {"compteurs": {}, "boites": {}, "virtuels": [], "epingles": []}
    par_boite = await _mailbox_counters(s, toutes, compte)
    boites = chosen(toutes, wanted)
    if not boites: return {"compteurs": {}, "boites": par_boite, "virtuels": (await references(s, compte))["virtuels"],
                           "epingles": (compte.preferences or {}).get("epingles", [])}
    ds = await _folders_by_id(s, boites)
    # LE « NON LU » N'EST PLUS UNE COLONNE (D175) : c'est « moi, je ne l'ai pas ouvert », donc un
    # EXISTS sur read_state. Il entre dans le GROUP BY comme le faisait `lu_le IS NULL` — même forme,
    # même nombre de requêtes ; ce qui change, c'est que deux personnes ne lisent plus le même chiffre.
    non_lu = personal.needs_attention_by(compte.compte_id).label("non_lu")
    rows = (await s.execute(select(Rattachement.dossier_id, Rattachement.exit_reason, non_lu,
                                   Rattachement.status, func.count().label("n"))
                            .where(_scope(boites)).group_by(Rattachement.dossier_id, Rattachement.exit_reason, non_lu, Rattachement.status))).all()
    c: dict = {}
    def bump(k, n, non_lu, statut):
        x = c.setdefault(k, {"t": 0, "u": 0, "f": 0}); x["t"] += n
        if non_lu: x["u"] += n
        if statut in IN_PROGRESS: x["f"] += n
    # L'ORDRE COMPTE : l'état de sortie prime sur le dossier, parce qu'il EST la boîte aux lettres
    # (D175 § 4). Un message archivé rangé dans un dossier utilisateur se compte dans Archives, pas
    # dans son dossier — sinon le compteur annonce ce que la liste ne montre pas (D166).
    for dossier_id, sortie, non_lu, statut, n in rows:
        d = ds.get(dossier_id); k = short_folder_id(d) or "inbox"
        if sortie == "archived": bump("archives", n, non_lu, statut); continue
        if sortie == "processed": bump("traites", n, non_lu, statut); continue
        if sortie == "junk": bump("junk", n, non_lu, statut); continue
        if sortie == "deleted" or k == "trash": bump("trash", n, non_lu, statut); continue
        bump(k, n, non_lu, statut)
    prefs = compte.preferences or {}
    ref = await references(s, compte)
    c.update(await _axis_counters(s, boites, ds, compte))
    c.update(await _virtual_counters(s, boites, ds, compte, ref["virtuels"]))
    return {"compteurs": c, "boites": par_boite, "virtuels": ref["virtuels"], "epingles": prefs.get("epingles", [])}


async def _mailbox_counters(s: AsyncSession, boites, compte) -> dict:
    """LE COMPTEUR D'UNE BOÎTE est un rapport (D176 § 4, arbitré le 23/10) : NON TRAITÉ / TOTAL.

    - total : le périmètre ACTIF — hors archives, corbeille et spam ; les traités y restent, les
      envoyés aussi : c'est ce que la boîte contient de vivant ;
    - non traité (`n`) : ce qui est arrivé et attend — une place REÇUE encore en file. Un envoyé
      n'attend rien de nous ;
    - non lus (`u`) : ne pilote que le gras, et se donne à côté.

    Indépendant des cases cochées : une boîte décochée doit encore dire ce qu'elle contient, sinon
    on ne sait plus ce qu'on cache. Une requête pour toutes les boîtes (D078)."""
    ds = await _folders_by_id(s, boites)
    hors = [d.dossier_id for d in ds.values() if short_folder_id(d) in ("trash", "junk")]
    actif = or_(Rattachement.exit_reason.is_(None), Rattachement.exit_reason == "processed")
    if hors: actif = and_(actif, Rattachement.dossier_id.notin_(hors))
    en_file = and_(Rattachement.sens == "in", Rattachement.exit_reason.is_(None))
    if hors: en_file = and_(en_file, Rattachement.dossier_id.notin_(hors))
    rows = (await s.execute(select(Rattachement.boite_id,
                                   func.count().filter(actif).label("t"),
                                   func.count().filter(en_file).label("n"),
                                   func.count().filter(and_(en_file, personal.needs_attention_by(compte.compte_id))).label("u"))
                            .where(_scope(boites)).group_by(Rattachement.boite_id))).all()
    out = {str(b): {"t": 0, "n": 0, "u": 0} for b in boites}
    for b, total, non_traite, non_lu in rows:
        out[str(b)] = {"t": total, "n": non_traite, "u": non_lu}
    return out


async def _axis_counters(s: AsyncSession, boites, ds: dict, compte) -> dict:
    """Les compteurs de TOUTES les branches d'axes, en une requête (D078).

    Ils comptent TOUT, traités et archivés compris (D166) : une branche de classement s'ouvre sur
    « tous », et le compteur doit dire ce que la liste montre. Un projet terminé reste visible —
    c'est justement celui qu'on vient consulter.

    Pas un agrégat par branche comme pour les dossiers virtuels : un axe peut porter deux cents
    valeurs, et deux cents agrégats conditionnels dans une requête ne se lisent plus. Ici la forme
    naturelle est un `GROUP BY (axe, valeur)` — le SGBD rend tout d'un coup, et la tête d'axe est
    la somme de ses valeurs.

    Un message portant deux valeurs du même axe compte UNE fois dans la tête : `count(distinct)`.
    Sans lui, « Projet » afficherait plus de messages que la somme de ce qu'il contient."""
    from ..schema.models import Axe, CommTag, Tag
    corbeilles = [d.dossier_id for d in ds.values() if short_folder_id(d) == "trash"]
    non_lu = personal.needs_attention_by(compte.compte_id)
    q = (select(Axe.nom, Tag.valeur,
                func.count(func.distinct(Rattachement.comm_id)).label("t"),
                func.count(func.distinct(case((non_lu, Rattachement.comm_id)))).label("u"),
                func.count(func.distinct(case((Rattachement.status.in_(IN_PROGRESS), Rattachement.comm_id)))).label("f"))
         .select_from(CommTag)
         .join(Tag, Tag.tag_id == CommTag.tag_id).join(Axe, Axe.axe_id == Tag.axe_id)
         .join(Rattachement, Rattachement.comm_id == CommTag.comm_id)
         .where(_scope(boites)).group_by(Axe.nom, Tag.valeur))
    if corbeilles:
        q = q.where(Rattachement.dossier_id.notin_(corbeilles))
    out: dict = {}
    for nom, valeur, total, non_lus, a_faire in (await s.execute(q)).all():
        out["%s:%s" % (nom, valeur)] = {"t": total, "u": non_lus, "f": a_faire}

    # La tête n'est PAS la somme de ses valeurs : un message étiqueté « projet=A » et
    # « projet=B » y figure une fois, pas deux. Une seconde agrégation, au niveau de l'axe —
    # GROUPING SETS ferait les deux d'un coup, mais demanderait du SQL brut, interdit hors de
    # schema/ (D154). Deux requêtes constantes valent mieux qu'une exception à la règle.
    qa = (select(Axe.nom,
                 func.count(func.distinct(Rattachement.comm_id)).label("t"),
                 func.count(func.distinct(case((non_lu, Rattachement.comm_id)))).label("u"),
                 func.count(func.distinct(case((Rattachement.status.in_(IN_PROGRESS), Rattachement.comm_id)))).label("f"))
          .select_from(CommTag)
          .join(Tag, Tag.tag_id == CommTag.tag_id).join(Axe, Axe.axe_id == Tag.axe_id)
          .join(Rattachement, Rattachement.comm_id == CommTag.comm_id)
          .where(_scope(boites)).group_by(Axe.nom))
    if corbeilles:
        qa = qa.where(Rattachement.dossier_id.notin_(corbeilles))
    for nom, total, non_lus, a_faire in (await s.execute(qa)).all():
        out["axe:" + nom] = {"t": total, "u": non_lus, "f": a_faire}
    return out


async def _virtual_counters(s: AsyncSession, boites, ds: dict, compte, virtuels: list) -> dict:
    """Un dossier virtuel n'est pas un dossier : il n'apparaît dans aucun `GROUP BY dossier_id`,
    donc il affichait **0/0** en portant des messages. On le compte avec la MÊME condition que
    celle qui le liste — sinon le compteur et la liste diraient deux choses.

    Toujours une seule passe (D078) : un agrégat conditionnel par dossier virtuel dans la même
    requête, plutôt qu'une requête par dossier."""
    if not virtuels:
        return {}
    colonnes, keys = [], []
    for v in virtuels:
        conds = []
        for crit in (v.get("criteres") or []):
            axe = crit.get("axe")
            if not axe:
                continue
            if axe == "dossier" and crit.get("val"): conds.append(_folder_condition(crit["val"], None, ds, compte))
            elif axe == "from" and crit.get("val"): conds.append(Comm.from_adresse.ilike("%" + crit["val"] + "%"))
            elif axe == "sujet" and crit.get("val"): conds.append(Comm.sujet.ilike("%" + crit["val"] + "%"))
            else: conds.append(_tag_condition(axe, crit.get("val")))
        if not conds:
            continue
        ou = and_(*conds)
        keys.append(v["id"])
        colonnes.append(func.count().filter(ou).label("t%d" % len(keys)))
        colonnes.append(func.count().filter(and_(ou, personal.needs_attention_by(compte.compte_id))).label("u%d" % len(keys)))
        colonnes.append(func.count().filter(and_(ou, Rattachement.status.in_(IN_PROGRESS))).label("f%d" % len(keys)))
    if not keys:
        return {}
    corbeilles = [d.dossier_id for d in ds.values() if short_folder_id(d) == "trash"]
    q = (select(*colonnes).select_from(Rattachement).join(Comm, Comm.comm_id == Rattachement.comm_id)
         .where(_scope(boites)))
    if corbeilles:
        q = q.where(Rattachement.dossier_id.notin_(corbeilles))     # la corbeille ne compte pas
    line = (await s.execute(q)).one()
    return {cle: {"t": line[i * 3], "u": line[i * 3 + 1], "f": line[i * 3 + 2]} for i, cle in enumerate(keys)}

def _folder_condition(dossier: str, kind: str | None, ds: dict, compte):
    """la condition SQL d'un dossier du webmail"""
    # `tous` : aucun dossier — tout le courrier de la portée, pour qui cherche par autre chose (les
    # échanges d'un tiers, par ses adresses — D108). La corbeille et les indésirables restent dehors
    # par le filtre de la liste, comme partout.
    if dossier == "tous":
        from sqlalchemy import true
        return true()
    par_court = {}
    for d in ds.values(): par_court.setdefault(short_folder_id(d), []).append(d.dossier_id)
    # LES CINQ BOÎTES AUX LETTRES SONT DES VALEURS D'UNE COLONNE (D051 réalisée par D175 § 4) :
    # `exit_reason` dit dans laquelle un message reçu se trouve, et il est dans une SEULE. Le
    # dossier reste le contenant que sert l'IMAP — d'où le `or_` sur la corbeille, le temps que le
    # ticket des cinq boîtes tranche à qui appartient l'UID (Q024).
    if dossier == "trash": return or_(Rattachement.exit_reason == "deleted",
                                      Rattachement.dossier_id.in_(par_court.get("trash", [uuid7()])))
    if dossier == "archives": return Rattachement.exit_reason == "archived"
    if dossier == "traites": return Rattachement.exit_reason == "processed"
    if dossier == "junk": return or_(Rattachement.exit_reason == "junk",
                                     Rattachement.dossier_id.in_(par_court.get("junk", [uuid7()])))
    if dossier in par_court: return Rattachement.dossier_id.in_(par_court[dossier])
    # une branche d'axe (D016/D077) : elle n'est pas un dossier, c'est un prédicat sur les tags —
    # elle tombait dans le `try UUID` ci-dessous, échouait, et la liste rendait « rien ».
    branche = _folder_tag(dossier)
    if branche: return _tag_condition(branche[0], branche[1])
    try: return Rattachement.dossier_id == __import__("uuid").UUID(dossier)
    except Exception: return Rattachement.dossier_id.is_(None) & (Rattachement.comm_id.is_(None))   # rien

SORTS = { "date_desc": Comm.date_recue.desc(), "date_asc": Comm.date_recue.asc(), "from_nom": Comm.from_nom.asc(), "subj": Comm.sujet.asc(), "taille": Comm.taille.desc() }

def _addresses_condition(adresses: str):
    """LES ÉCHANGES AVEC CES ADRESSES (D108) : l'expéditeur, ou un participant (à, copie). C'est ce
    que montre l'onglet « Échanges » d'une fiche tiers dans l'ERP — dans les deux sens."""
    liste = [a.strip().lower() for a in (adresses or "").split(",") if "@" in a]
    if not liste: return Comm.comm_id.is_(None)          # une liste vide ne montre rien, jamais tout
    par_participant = (select(Participant.comm_id).join(Adresse, Adresse.adresse_id == Participant.adresse_id)
                       .where(Participant.comm_id == Comm.comm_id, Adresse.adresse_complete.in_(liste)).exists())
    return or_(func.lower(Comm.from_adresse).in_(liste), par_participant)


async def listing(s: AsyncSession, compte: Compte, dossier: str, kind: str | None, filtre: str | None, tri: str | None, sens: str | None, statut: str | None, tout: bool = False, wanted: str | None = None, adresses: str | None = None) -> list[dict]:
    boites = chosen([b.boite_id for b in await account_mailboxes(s, compte)], wanted)
    if not boites: return []
    ds = await _folders_by_id(s, boites)
    q = select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id).where(_scope(boites))
    if kind == "perso":
        f = await s.get(Filtre, __import__("uuid").UUID(dossier.split(":", 1)[1])) if dossier.startswith("perso:") else None
        conds = []
        for c in ((f.predicat or {}).get("criteres", []) if f else []):
            if c.get("axe") == "dossier" and c.get("val"): conds.append(_folder_condition(c["val"], None, ds, compte))
            elif c.get("axe") == "from" and c.get("val"): conds.append(Comm.from_adresse.ilike("%" + c["val"] + "%"))
            elif c.get("axe") == "sujet" and c.get("val"): conds.append(Comm.sujet.ilike("%" + c["val"] + "%"))
            elif c.get("axe"): conds.append(_tag_condition(c["axe"], c.get("val")))
        q = q.where(and_(*conds)) if conds else q.where(Comm.comm_id.is_(None))
        q = q.where(Rattachement.dossier_id.notin_([d.dossier_id for d in ds.values() if short_folder_id(d) == "trash"]))
    else:
        q = q.where(_folder_condition(dossier, kind, ds, compte))
    if adresses is not None: q = q.where(_addresses_condition(adresses))
    est_vue = dossier in VIEWS
    if not tout:
        if sens in ("in", "out"): q = q.where(Rattachement.sens == sens)      # le rôle de la PLACE (D185)
        if statut and statut != "tous": q = q.where(Rattachement.status == statut)
        # « tous » : en file, traités et archivés — c'est le défaut d'une branche de CLASSEMENT (D166).
        # La règle « traité sort de la file » (D014/D030) vaut pour une file de travail ; appliquée
        # à un tag, elle fait disparaître un projet entier dès qu'il est terminé.
        #
        # Mais JAMAIS la corbeille : un message supprimé vit dans la vue Corbeille, nulle part
        # ailleurs. « Tous » et « traités / archivés » le montraient dans son dossier d'origine,
        # alors que les compteurs l'excluaient — compteur ≠ liste, ce que D166 interdit. Trouvé par
        # le test de bout en bout : un brouillon envoyé restait dans « Brouillons » (RM3188).
        if not est_vue:
            q = q.where(or_(Rattachement.exit_reason.is_(None),
                            Rattachement.exit_reason.notin_(("deleted", "junk"))))
            if filtre == "sortis": q = q.where(Rattachement.exit_reason.isnot(None))
            elif filtre != "tous": q = q.where(Rattachement.exit_reason.is_(None))
        # « non lus » veut dire « que MOI je n'ai pas ouverts », et « à revoir » y entre : c'est le
        # même geste qu'avant (D175 § 2), il ne détruit plus la trace de l'ouverture.
        if filtre == "non_lus": q = q.where(personal.needs_attention_by(compte.compte_id))
        if filtre == "recents": q = q.where(Comm.date_recue >= datetime.now(timezone.utc) - timedelta(days=30))
        if filtre == "pj": q = q.where(Comm.nb_pieces_jointes > 0)
        if filtre == "lourds": q = q.where(Comm.taille > 2048 * 1024)
    q = q.order_by(SORTS.get(tri or "date_desc", SORTS["date_desc"])).limit(500)
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    lines = (await s.execute(q)).all()
    # les tags de TOUTE la liste en une passe (D078) : une requête par message rendrait la
    # deuxième page inutilisable, et c'est le tag qui porte le classement (D002)
    from .tags import tags_of
    tags = await tags_of(s, [c.comm_id for _, c in lines])
    etats = await personal.states_of(s, compte.compte_id, [c.comm_id for _, c in lines])
    deux = await twins(s, [r for r, _ in lines])
    return [serialize(r, c, ds, adresses.get(r.boite_id), extra={"tags": tags.get(c.comm_id, [])},
                       etat=etats.get((r.comm_id, r.boite_id)), twin=(r.comm_id, r.boite_id) in deux)
            for r, c in lines]

def serialize(r: Rattachement, c: Comm, ds: dict, boite_adresse: str | None, complet: bool = False, extra: dict | None = None, etat: dict | None = None, twin: bool = False) -> dict:
    """`etat` est l'état PERSONNEL du compte qui regarde (D175) : il ne se lit plus sur le
    rattachement, donc il ne peut plus être deviné ici — il se passe. Absent = personne n'y a
    touché, ce qui est le cas de la grande majorité des lignes."""
    origine = short_folder_id(ds.get(r.dossier_origine_id)) if r.dossier_origine_id else short_folder_id(ds.get(r.dossier_id))
    current = short_folder_id(ds.get(r.dossier_id))
    o = { "id": place_id(r, twin), "sujet": c.sujet, "from_nom": c.from_nom, "from_adresse": c.from_adresse,
          "date_recue": iso(c.date_recue), "thread_id": str(c.thread_id) if c.thread_id else None,
          "nb_pieces_jointes": c.nb_pieces_jointes, "taille": c.taille, "sens": r.sens, "nature": c.nature, "snippet": c.snippet,
          "boite": boite_adresse, "statut": r.status, "sorti_le": iso(exit_date(r)), "motif_sortie": r.exit_reason,
          "statut_le": iso(r.status_at), "traite_le": iso(r.processed_at), "archive_le": iso(r.archived_at),
          **personal.serialize_state(etat),
          "dossier_origine": origine or "inbox", "dossier": current if current != origine else None,
          "tags": [], "connu": False, "usurpation": False, "valide": False, "suppr": r.exit_reason == "deleted",
          "reponse_possible": None, "list_id": None, "destinataires": [], "reference": None, "composition": None, "fiabilite": None, "contact_alternatif": None, "dsn": None, "dom": None }
    if extra: o.update(extra)
    return o

def _composition(r: Rattachement, c: Comm, ds: dict, adresse: str, dest: list, copies: list, corps: str, ref: str | None) -> dict | None:
    """Un brouillon se rouvre dans l'état où il a été laissé — reconstruit du MESSAGE, jamais
    d'une copie d'écran gardée à côté : un brouillon EST un message marqué (D089), et une
    seconde source d'écriture aurait divergé dès le premier réenregistrement.

    Le transfert se reconnaît à sa PROVENANCE en base (D067) : elle a remplacé l'en-tête
    `X-AtomBox-Reference`, qui partait chez le destinataire et ne s'indexait pas."""
    if short_folder_id(ds.get(r.dossier_id)) != "drafts":
        return None
    return {"mode": "tr" if ref else "new", "src": ref, "de": adresse,
            "a": ", ".join(dest), "cc": ", ".join(copies), "sujet": c.sujet or "",
            "corps": corps, "pieces_jointes": [], "reference": ref}

async def _contexts(s: AsyncSession, comm_id) -> list[dict]:
    """LE CONTEXTE MÉTIER (F047, D021) : pour chaque tiers d'application que porte le message, ce que
    l'application a POUSSÉ avec lui — encours, échu, objets ouverts. Affiché, jamais calculé ni
    demandé ici : AtomBox n'appelle pas l'ERP. Les objets reçoivent le lien de leur fiche (F149)."""
    from ..schema.models import Application, Axe, CommTag, Tag
    from ..connectors import declaration
    rows = (await s.execute(select(Tag, Axe, Application).join(CommTag, CommTag.tag_id == Tag.tag_id)
                            .join(Axe, Axe.axe_id == Tag.axe_id).join(Application, Application.application_id == Axe.application_id)
                            .where(CommTag.comm_id == comm_id, Application.actif.is_(True)))).all()
    out = []
    for tag, axe, app in rows:
        d = declaration(app.type_connecteur) or {}
        ctx = (tag.ref_externe or {}).get("contexte")
        if axe.nom != (d.get("regle_adresse") or {}).get("axe") or not isinstance(ctx, dict): continue
        url = ((app.parametres or {}).get("url") or "").rstrip("/")
        fiches = d.get("fiches") or {}
        lien = lambda nom_axe, i: (url + fiches[nom_axe]).replace("{id}", str(i)) if url and nom_axe in fiches and i is not None else None
        objets = []
        for o in (ctx.get("objets") or [])[:20]:
            if isinstance(o, dict): objets.append(dict(o, lien=lien(o.get("axe"), o.get("id"))))
        out.append({"application": d.get("libelle") or app.type_connecteur,
                    "tiers": {"id": tag.valeur, "libelle": tag.libelle, "lien": lien(axe.nom, tag.valeur)},
                    "encours": ctx.get("encours"), "echu": ctx.get("echu"), "devise": ctx.get("devise") or "EUR",
                    "objets": objets, "maj": ctx.get("maj")})
    return out


async def detail(s: AsyncSession, compte: Compte, comm_id, sens=None, store=None) -> dict | None:
    boites = [b.boite_id for b in await account_mailboxes(s, compte)]
    r = await s.scalar(_place(comm_id, boites, sens))
    if not r: return None
    c = await s.get(Comm, comm_id); e = await s.get(CommEmail, comm_id); ds = await _folders_by_id(s, boites)
    boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    lines = (await s.execute(select(Participant.role, Adresse.adresse_complete).join(Adresse, Participant.adresse_id == Adresse.adresse_id)
                              .where(Participant.comm_id == comm_id, Participant.role.in_(("to", "cc"))).order_by(Participant.ordre))).all()
    dest = [a for role, a in lines if role == "to"]
    copies = [a for role, a in lines if role == "cc"]
    pjs = (await s.execute(select(CommPieceJointe, PieceJointe).join(PieceJointe, PieceJointe.piece_jointe_id == CommPieceJointe.piece_jointe_id)
                           .where(CommPieceJointe.comm_id == comm_id).order_by(CommPieceJointe.ordre))).all()
    corps = ""
    if store is not None and store.exists(str(comm_id)):
        try:
            from ..ingestion.analysis import analyze
            corps = analyze(store.read_message(str(comm_id))).corps_texte
        except Exception as ex: log.warning("corps de %s illisible : %s", comm_id, ex)
    from .tags import tags_of
    provenance = await _provenance_of(s, comm_id)
    ref = str(provenance) if provenance else None
    to_folder = await _encapsulated_messages(s, comm_id, boites, pjs)      # D168
    etats = await personal.states_of(s, compte.compte_id, [comm_id])
    twin = bool(await twins(s, [r]))
    return serialize(r, c, ds, adresse, True, etat=etats.get((r.comm_id, r.boite_id)), twin=twin, extra={
        "tags": (await tags_of(s, [comm_id])).get(comm_id, []), "reference": ref,
        "destinataires": list(dest) + list(copies), "composition": _composition(r, c, ds, adresse, dest, copies, corps, ref),
        "corps": corps, "reponse_possible": e.reponse_possible if e else None, "list_id": e.list_id if e else None,
        # le contexte métier (F047) : seulement au DÉTAIL — absent de la liste et du fil, il n'y est pas
        # écrasé par la fusion du cache du webmail (la leçon du fil sans tags, 27/10)
        "contexte": await _contexts(s, comm_id),
        "pieces_jointes": [ {"pj_id": str(p.piece_jointe_id), "ordre": l.ordre, "nom": l.nom_declare or ("piece-%d" % l.ordre), "octets": p.taille_octets,
                             "mime_declare": l.type_declare, "mime_detecte": p.type_detecte, "sha256": p.blob_ref, "partage_par": p.nb_references,
                             "content_id": l.content_id, "disposition": l.disposition,
                             "comm_id": to_folder.get(str(p.piece_jointe_id))} for l, p in pjs ] })

async def attachment(s: AsyncSession, compte: Compte, comm_id, pj_id, store=None) -> dict | None:
    """Les OCTETS d'une pièce jointe (F136), dans la portée du compte (D036) — hors portée : None,
    donc 404, jamais 403 (D108).

    Le type rendu est le type DÉTECTÉ (D032), jamais le déclaré : c'est la seule règle qui empêche
    qu'un exécutable nommé `facture.pdf` s'ouvre comme un PDF. Et le nom est nettoyé avant de partir
    dans un en-tête — un nom de fichier vient du message, donc de l'extérieur."""
    boites = [b.boite_id for b in await account_mailboxes(s, compte)]
    r = await s.scalar(_place(comm_id, boites))
    if not r: return None
    line = await s.scalar(select(CommPieceJointe).where(CommPieceJointe.comm_id == comm_id,
                                                        CommPieceJointe.piece_jointe_id == pj_id).limit(1))
    if line is None: return None
    p = await s.get(PieceJointe, pj_id)
    if p is None or store is None or not store.exists(p.blob_ref): return None
    return {"octets": store.read(p.blob_ref), "type": p.type_detecte or "application/octet-stream",
            "nom": _filename(line.nom_declare or ("piece-%d" % line.ordre)),
            "disposition": line.disposition or "attachment"}


async def _encapsulated_messages(s: AsyncSession, comm_id, boites: list, pjs: list) -> dict:
    """D168 — une partie `message/rfc822` dont l'original est EN BASE et DANS LA PORTÉE du lecteur
    se rend comme une référence, pas comme un fichier. La résolution n'accorde aucun droit : elle
    ne regarde que ce que le lecteur peut déjà voir.

    Deux chemins, dans cet ordre : la provenance posée à l'émission (D067), puis le `Message-ID` du
    message encapsulé — le seul indice quand il vient de l'extérieur (D064). Un encapsulé non résolu
    aujourd'hui se résoudra le jour où son original sera ingéré (D163)."""
    encapsules = [(l, p) for l, p in pjs if (p.type_detecte or "") == "message/rfc822"]
    if not encapsules: return {}
    cite = await s.scalar(select(CommCitation.cite_comm_id).where(CommCitation.comm_id == comm_id).limit(1))
    if cite is not None and not await s.scalar(select(Rattachement.comm_id).where(Rattachement.comm_id == cite, _scope(boites)).limit(1)):
        cite = None                      # l'original existe, mais pas pour ce lecteur : un contenu, pas un lien
    out = {}
    for l, p in encapsules:
        vise = cite
        if vise is None:
            vise = await _resolve_by_message_id(s, p, boites)
        if vise is not None: out[str(p.piece_jointe_id)] = str(vise)
        cite = None                      # la provenance ne vaut que pour la PREMIÈRE pièce encapsulée
    return out


async def _resolve_by_message_id(s: AsyncSession, p: PieceJointe, boites: list):
    """Le `Message-ID` lu dans les octets de l'encapsulé, confronté à ce que le lecteur possède."""
    from ..store import Store
    try:
        m = Store(settings.read("ATOMBOX_STORE", "./magasin"))
        if not m.exists(p.blob_ref): return None
        interne = email.message_from_bytes(m.read(p.blob_ref), policy=email.policy.SMTP)
        mid = (interne["Message-ID"] or "").strip()
    except Exception as ex:
        log.debug("encapsulé illisible %s : %s", p.piece_jointe_id, ex); return None
    if not mid: return None
    return await s.scalar(select(Rattachement.comm_id).join(CommEmail, CommEmail.comm_id == Rattachement.comm_id)
                          .where(CommEmail.message_id == mid, _scope(boites)).limit(1))


async def thread(s: AsyncSession, compte: Compte, comm_id) -> list[dict]:
    boites = [b.boite_id for b in await account_mailboxes(s, compte)]
    c = await s.get(Comm, comm_id)
    if not c: return []
    ds = await _folders_by_id(s, boites)
    q = select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id).where(_scope(boites), Comm.thread_id == (c.thread_id or c.comm_id)).order_by(Comm.date_recue.asc())
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    lines = (await s.execute(q)).all()
    etats = await personal.states_of(s, compte.compte_id, [cc.comm_id for _, cc in lines])
    # LES TAGS AUSSI, comme la liste et le détail. Le fil contient le message ouvert lui-même, et le
    # webmail FUSIONNE chaque réponse dans l'objet qu'il garde : un fil sans tags effaçait ceux du
    # message ouvert — le tiers rangé disparaissait, « inconnu de Dolibarr » revenait (27/10).
    from .tags import tags_of
    tags = await tags_of(s, [cc.comm_id for _, cc in lines])
    seen, out = set(), []
    for r, cc in lines:
        if cc.comm_id in seen: continue
        seen.add(cc.comm_id)
        out.append(serialize(r, cc, ds, adresses.get(r.boite_id), etat=etats.get((r.comm_id, r.boite_id)),
                             extra={"tags": tags.get(cc.comm_id, [])}))
    return out

async def patch(s: AsyncSession, compte: Compte, comm_id, patch: dict, sens=None) -> dict | None:
    """Le rattachement ET l'état personnel du compte — jamais le message.

    TROIS PLANS, TROIS ENDROITS (D175), et ce point de passage unique est le seul qui les connaisse
    tous les trois. Ce qui a changé de nature ici :

      * `lu: true` pose un FAIT dans read_state, et ne l'efface plus jamais ;
      * `lu: false` — l'ancien « marquer comme non lu » — pose le marqueur « à revoir ». Le geste
        est le même pour l'utilisateur ; ce qu'il détruisait ne se détruit plus ;
      * `drapeau` est personnel : l'IMAP sortant est par compte, donc chacun a le sien ;
      * chaque transition de sortie pose SA date et SON auteur, et s'écrit au journal — sans quoi
        « traité le 3, puis archivé le 10 » ne serait lisible nulle part.
    """
    boites = [b.boite_id for b in await account_mailboxes(s, compte)]
    r = await s.scalar(_place(comm_id, boites, sens))
    if not r: return None
    ds = await _folders_by_id(s, boites)
    n = 0; dossier_avant = r.dossier_id
    now = datetime.now(timezone.utc)

    async def leave_queue(valeur: str | None):
        """Le déplacement vit dans `services/mailbox.py` : trois chemins y mènent — ce clic, un
        `UID MOVE` d'un client IMAP, une règle à l'ingestion — et ils doivent écrire exactement la
        même chose (D183). Ici on ne fait que compter le changement."""
        nonlocal n
        await mailbox.move(s, r, valeur, compte.compte_id)
        n += 1

    for k, v in (patch or {}).items():
        if k == "lu":
            if v:
                await personal.mark_opened(s, compte.compte_id, comm_id, r.boite_id)
                await personal.unset_marker(s, compte.compte_id, comm_id, r.boite_id, personal.TO_REVIEW)
                trace.record(s, compte.compte_id, "opened", "rattachement", comm_id, {"boite_id": str(r.boite_id)})
            else:
                # « NON LU » N'EXISTE PLUS (D175 § 2) : le geste veut dire « j'y suis passé, il faut
                # que j'y retourne ». On le dit, au lieu d'effacer la preuve du passage.
                await personal.set_marker(s, compte.compte_id, comm_id, r.boite_id, personal.TO_REVIEW)
                trace.record(s, compte.compte_id, "marked", "rattachement", comm_id,
                             {"boite_id": str(r.boite_id), "marqueur": personal.TO_REVIEW, "pose": True})
            n += 1
        elif k == "a_revoir":
            if v: await personal.set_marker(s, compte.compte_id, comm_id, r.boite_id, personal.TO_REVIEW)
            else: await personal.unset_marker(s, compte.compte_id, comm_id, r.boite_id, personal.TO_REVIEW)
            trace.record(s, compte.compte_id, "marked", "rattachement", comm_id,
                         {"boite_id": str(r.boite_id), "marqueur": personal.TO_REVIEW, "pose": bool(v)})
            n += 1
        elif k == "sommeil":
            await personal.set_marker(s, compte.compte_id, comm_id, r.boite_id, personal.SNOOZE, due_at=when(v)) if v \
                else await personal.unset_marker(s, compte.compte_id, comm_id, r.boite_id, personal.SNOOZE)
            n += 1
        elif k == "statut" and v in [x["id"] for x in STATUSES]:
            if v != r.status:
                trace.record(s, compte.compte_id, "status_changed", "rattachement", comm_id,
                             {"boite_id": str(r.boite_id), "avant": r.status, "apres": v})
            r.status, r.status_at, r.status_by = v, now, compte.compte_id; n += 1
        elif k == "motif_sortie": await leave_queue(v or None)
        elif k == "sorti_le":
            # La date ne se pose plus de l'extérieur : c'est la TRANSITION qui la pose, dans la case
            # de l'état où elle a eu lieu. Accepter un `sorti_le` nu, c'était pouvoir dater un
            # traitement sans dire qu'il avait eu lieu.
            log.debug("PATCH %s : sorti_le ignoré — la date suit la transition (D175)", comm_id)
        elif k == "drapeau":
            await personal.set_flag(s, compte.compte_id, comm_id, r.boite_id, flagged=bool(v)); n += 1
        elif k == "personnel": r.personnel = bool(v); n += 1
        elif k == "dossier":
            # RANGER DANS UNE BOÎTE D'ÉTAT, C'EST CHANGER D'ÉTAT (D183). Le webmail envoie encore
            # `{dossier: "trash"}` pour mettre à la corbeille : ce n'est pas un rangement, c'est une
            # transition, et elle doit poser sa date, son auteur et sa trace comme les autres.
            cible = next((d for d in ds.values() if d.boite_id == r.boite_id and short_folder_id(d) == v), None) if v else None
            if v is not None and cible is None:
                log.warning("PATCH %s : boîte aux lettres inconnue %r", comm_id, v); continue
            if (cible is not None and cible.exit_reason) or v is None:
                await leave_queue(cible.exit_reason if cible is not None else None)
                continue
            # PAS D'ÉCRITURE DE L'ORIGINE ICI : ranger un message dans « Devis 2026 », c'est lui
            # donner sa place, pas le faire partir de quelque part. Écrire l'origine à ce moment
            # faisait que tout revenait à l'INBOX — et un message traité depuis « Devis » ne
            # retrouvait jamais son dossier.
            # DÉPLACER, C'EST CHANGER DE BOÎTE AUX LETTRES : l'UID appartient au dossier, pas au
            # message (Q024). En garder l'ancien ferait lire au client un message pour un autre.
            #
            # L'UID S'OBTIENT AVANT DE BOUGER. `attribuer` exécute une requête, et SQLAlchemy vide
            # alors les modifications en attente : écrire `dossier_id` d'abord ferait partir la
            # nouvelle boîte avec l'ANCIEN uid, qui heurte l'unicité si elle l'utilise déjà.
            from ..served_uid import assign_async as assign_uid
            uid = await assign_uid(s, cible.dossier_id)
            r.dossier_id, r.uid_servi = cible.dossier_id, uid
            n += 1
        elif k == "suppr" and v:
            await leave_queue("deleted")
        elif k == "tags": log.info("PATCH %s : tags ignorés en V0 (pas d'axe métier, D140b)", comm_id)
        else: log.debug("PATCH %s : champ ignoré %s", comm_id, k)
    # SYNCHRONISATION MONTANTE (F113) : l'état part vers IMAP hors processus, jamais dans la
    # requête — un serveur IMAP lent ou absent ne doit pas faire échouer un clic (D161).
    # L'émission se fait ICI, au point de passage unique de l'API, et non dans un déclencheur ORM :
    # insérer une ligne pendant le flush d'une autre est un piège (D158, D161).
    if n and not sync.down_sync() and any(k in (patch or {}) for k in ("lu", "drapeau", "dossier", "suppr")):
        from ..modules import events
        await events.emit_async(s, "rattachement.change",
                                       {"comm_id": str(comm_id), "boite_id": str(r.boite_id), "sens": r.sens,
                                        "dossier_avant": str(dossier_avant) if dossier_avant else None})
    await s.commit()
    c = await s.get(Comm, comm_id); boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    etats = await personal.states_of(s, compte.compte_id, [comm_id])
    return {"modifies": n, "message": serialize(r, c, ds, adresse, etat=etats.get((r.comm_id, r.boite_id)),
                                                 twin=bool(await twins(s, [r])))}

async def detach(s: AsyncSession, compte: Compte, comm_id, sens=None) -> bool:
    r = await patch(s, compte, comm_id, {"suppr": True}, sens=sens)
    return r is not None

def atombox_host() -> str:
    """le nom de CETTE instance dans la chaîne de relais — jamais deviné à partir d'une requête"""
    return settings.read("ATOMBOX_HOST") or socket.getfqdn() or "atombox"

def relay_headers(m: email.message.EmailMessage, comm_id, expediteur: str, when: datetime, ip_client: str | None = None) -> None:
    """AtomBox n'est pas un client SMTP : il REÇOIT par son API et REMET au relais. Le Received le
    dit (RFC 5321 § 4.4), avec l'identifiant qui corrèle journal, envoi et DSN (D119).

    L'IP du client n'y est JAMAIS écrite (D162) : un en-tête sortant part chez tous les
    destinataires et géolocalise l'expéditeur à chaque message ; l'IP vit au journal, chez nous.
    Le paramètre existe pour un client qui l'exigerait — verrouillable, désactivé par défaut."""
    trace = ""
    if ip_client and settings.read("ATOMBOX_TRACE_CLIENT_IP") == "1":
        trace = " (client %s)" % ip_client                        # jamais par défaut — D162
    # une seule ligne LOGIQUE : c'est la politique qui replie (elle refuse un CRLF écrit à la main)
    recu = ("from webmail (atombox%s) by %s with HTTPS id %s (authenticated sender: %s); %s"
            % (trace, atombox_host(), comm_id, expediteur, email.utils.format_datetime(when)))
    m["X-Mailer"] = "AtomBox"                                     # sans version : pas de carte des failles
    # un Received se pose EN TÊTE : la chaîne de trace se lit du plus récent au plus ancien, et le
    # relais suivant ajoutera le sien au-dessus du nôtre (RFC 5321 § 4.4)
    anciens = m.items()
    for cle in dict.fromkeys(k for k, _ in anciens): del m[cle]
    m["Received"] = recu
    for cle, valeur in anciens: m[cle] = valeur

def _filename(sujet) -> str:
    """Le nom que verra le destinataire : le sujet du message transféré, rendu inoffensif."""
    propre = re.sub(r"[^\w .()\[\]-]+", "_", str(sujet or "message transfere"), flags=re.UNICODE).strip()
    return (propre or "message transfere")[:80]


async def _source_to_forward(s: AsyncSession, compte: Compte, corps: dict, store):
    """Le message transféré, LU DANS LE MAGASIN — jamais reconstruit depuis ce que l'écran affiche.

    Et lu dans la PORTÉE du compte (D036) : transférer se fait sur ce qu'on a le droit de lire,
    la référence venant du client. Rend (comm_id, octets) ou (None, None)."""
    ref = corps.get("reference")
    if not ref or store is None: return None, None
    try: src_id = uuid.UUID(str(ref))
    except (ValueError, AttributeError, TypeError): return None, None
    boites = [b.boite_id for b in await account_mailboxes(s, compte)]
    if not await s.scalar(select(Rattachement.comm_id).where(Rattachement.comm_id == src_id, _scope(boites)).limit(1)):
        log.warning("transfert refuse : %s hors de la portee de %s", src_id, compte.login)
        return None, None
    if not store.exists(str(src_id)): return src_id, None      # purgé : le transfert part sans lui (Q030)
    return src_id, store.read_message(str(src_id))


async def _add_parts(s: AsyncSession, comm_id, pieces, store, when) -> None:
    """Les pièces d'un message écrit ici entrent en base comme celles d'un message reçu — même
    déduplication par empreinte (D024). Sans ça, un transfert s'envoyait avec son encapsulé dans
    les octets mais se relisait sans rien : la pièce existait et l'écran ne la voyait pas."""
    from ..store import fingerprint as fingerprint_of
    for l in await s.scalars(select(CommPieceJointe).where(CommPieceJointe.comm_id == comm_id)):
        await s.delete(l)
    await s.flush()
    for p in pieces:
        if store is not None: ref, info = store.put(p.raw_bytes)
        else: ref, info = fingerprint_of(p.raw_bytes), {"taille_octets": len(p.raw_bytes), "taille_stockee": len(p.raw_bytes), "compression": "aucune"}
        b = await s.get(Blob, ref)
        if b: b.nb_references += 1
        else: s.add(Blob(empreinte=ref, taille_octets=info["taille_octets"], taille_stockee=info["taille_stockee"],
                         compression=info["compression"], cree_le=when, nb_references=1))
        pj = await s.scalar(select(PieceJointe).where(PieceJointe.blob_ref == ref, PieceJointe.type_detecte == p.type_detecte))
        if pj: pj.nb_references += 1
        else:
            pj = PieceJointe(piece_jointe_id=uuid7(), blob_ref=ref, type_detecte=p.type_detecte, taille_octets=len(p.raw_bytes), nb_references=1)
            s.add(pj); await s.flush()
        s.add(CommPieceJointe(comm_id=comm_id, piece_jointe_id=pj.piece_jointe_id, ordre=p.ordre, nom_declare=p.nom_declare,
                              type_declare=p.type_declare, transfer_encoding=p.transfer_encoding, disposition=p.disposition,
                              content_id=p.content_id, parametres=p.parametres))


async def _add_provenance(s: AsyncSession, comm_id, src_id, when) -> None:
    """La provenance d'un transfert est une RELATION (D067), pas un en-tête. En V0 le bloc source
    est verrouillé : la citation est donc entière et fidèle par construction — part_citee 100,
    part_modifiee 0 (D163). Le jour où le bloc se déverrouille (F133), c'est ici que le degré de
    modification se posera, et l'accès ne suivra pas la provenance (D167)."""
    for c in await s.scalars(select(CommCitation).where(CommCitation.comm_id == comm_id)):
        await s.delete(c)
    await s.flush()
    if src_id is None: return
    src = await s.get(Comm, src_id)
    e = await s.get(CommEmail, src_id) if src is not None else None
    s.add(CommCitation(comm_citation_id=uuid7(), comm_id=comm_id, cite_comm_id=src_id,
                       cite_message_id=(e.message_id if e is not None else None),
                       part_citee=100, part_modifiee=0, position="apres", recette=None,
                       origine="emission", detecte_le=when))


async def _provenance_of(s: AsyncSession, comm_id):
    """L'identifiant du message transféré, s'il y en a un."""
    return await s.scalar(select(CommCitation.cite_comm_id).where(CommCitation.comm_id == comm_id).limit(1))


def _compose(compte: Compte, adresse: str, corps: dict, comm_id, when, ip_client: str | None = None,
              source: bytes | None = None) -> bytes:
    """Les octets d'un message écrit dans le webmail — brouillon ou envoi, même chemin.

    Il y en avait deux, presque identiques : l'un posait les destinataires en base et pas
    l'autre, l'un portait le Cc et pas l'autre. Deux chemins pour un même objet finissent
    toujours par diverger — celui-ci est le seul."""
    m = email.message.EmailMessage(policy=email.policy.SMTP)
    m["From"] = "%s <%s>" % (compte.nom, adresse)
    m["To"] = ", ".join(corps.get("destinataires") or [])
    cc = [a.strip() for a in (corps.get("cc") or "").split(",") if a.strip()] if isinstance(corps.get("cc"), str) else list(corps.get("cc") or [])
    if cc: m["Cc"] = ", ".join(cc)      # sans ça, un brouillon repris perdait ses copies
    m["Subject"] = corps.get("sujet") or "(sans sujet)"
    m["Date"] = email.utils.formatdate(localtime=True)
    m["Message-ID"] = email.utils.make_msgid(domain=adresse.split("@")[-1])
    """Le message transféré est ENCAPSULÉ, pas recopié dans le corps (D066/D167) : le commentaire
    reste dissocié, l'index ne voit que lui (D163), et l'octet du source part intact. Aucun en-tête
    ne porte le lien — la provenance vit en base, jamais dans le message (D067) : un marqueur
    partirait chez le destinataire et ne s'indexerait pas."""
    if source:
        frontiere = "=_AtomBox_" + uuid.uuid4().hex
        m["MIME-Version"] = "1.0"
        m["Content-Type"] = 'multipart/mixed; boundary="%s"' % frontiere
        relay_headers(m, comm_id, adresse, when, ip_client)   # D162
        sujet = email.message_from_bytes(source, policy=email.policy.SMTP)["Subject"]
        return _assemble_forward(m, frontiere, corps.get("corps") or "", source, _filename(sujet) + ".eml")
    m.set_content(corps.get("corps") or "")
    relay_headers(m, comm_id, adresse, when, ip_client)   # D162
    return m.as_bytes()


def _headers(msg) -> bytes:
    """Les en-têtes SEULS, pliés et encodés par la politique (RFC 2047, 2231) — sans le générateur,
    qui ne sait pas écrire un multipart dont on fournit soi-même une partie."""
    return b"".join(msg.policy.fold_binary(k, v) for k, v in msg.items())


def transfer_encoding_of(raw: bytes) -> str:
    """L'encodage qui transporte `brut` SANS LE TOUCHER, quand il existe.

    `7bit` si c'est de l'ASCII à lignes courtes — le cas courant, puisque MIME a déjà encodé
    l'intérieur du message ; `8bit` s'il porte des octets hauts ; `base64` en dernier recours, pour
    ce que SMTP ne transporte pas tel quel : une ligne de plus de 998 octets (RFC 5322 § 2.1.1) ou un
    octet nul. La RFC 2045 § 6.4 n'autorise pas `base64` pour un type `message/`, mais tous les
    clients le lisent — et c'est le seul encodage qui garde encore l'octet exact (Q074)."""
    if b"\0" in raw or any(len(l.rstrip(b"\r")) > 998 for l in raw.split(b"\n")):
        return "base64"
    return "8bit" if any(o > 0x7F for o in raw) else "7bit"


def _assemble_forward(m, frontiere: str, commentaire: str, source: bytes, nom: str) -> bytes:
    """Le multipart écrit À LA MAIN, parce que c'est la seule façon de ne pas re-sérialiser le message
    transmis (RM3213, D025, D148). La bibliothèque le relisait puis le réécrivait : 265 octets en
    entrée, 254 en sortie — la signature DKIM du transmis ne se vérifiait plus chez le destinataire,
    et la déduplication ne retrouvait pas le blob de l'original.

    Le CRLF qui précède une frontière APPARTIENT à la frontière (RFC 2046 § 5.1.1) : il est ajouté
    après la charge, sans quoi le dernier saut de ligne du message transmis serait mangé."""
    texte = email.message.MIMEPart(policy=email.policy.SMTP)
    texte.set_content(commentaire)
    piece = email.message.MIMEPart(policy=email.policy.SMTP)
    piece["Content-Type"] = "message/rfc822"
    piece.add_header("Content-Disposition", "attachment", filename=nom)
    cte = transfer_encoding_of(source)
    piece["Content-Transfer-Encoding"] = cte
    charge = base64.encodebytes(source).replace(b"\n", b"\r\n") if cte == "base64" else source
    F = frontiere.encode("ascii")
    return (_headers(m) + b"\r\n"
            + b"--" + F + b"\r\n" + texte.as_bytes()
            + b"\r\n--" + F + b"\r\n" + _headers(piece) + b"\r\n" + charge
            + b"\r\n--" + F + b"--\r\n")

async def _add_participants(s: AsyncSession, comm_id, participants) -> None:
    """Les destinataires sont une DONNÉE du message, pas un écho de la requête : sans eux,
    un message envoyé se relit sans destinataire (et un brouillon sans personne à qui écrire)."""
    for p in await s.scalars(select(Participant).where(Participant.comm_id == comm_id)):
        await s.delete(p)
    await s.flush()
    for role, nom, adr, ordre in participants:
        s.add(Participant(comm_id=comm_id, role=role, adresse_id=(await _address(s, adr)).adresse_id, nom_affiche=nom, ordre=ordre))


async def replace_draft(s: AsyncSession, compte: Compte, comm_id, corps: dict, store=None, envoi: bool = False) -> dict | None:
    """Un brouillon réenregistré GARDE son identité (D089 : un brouillon est un message marqué).
    Le webmail supprimait puis recréait : le message changeait d'identifiant à chaque frappe
    enregistrée, et l'onglet ouvert pointait sur un mort.

    ENVOYER un brouillon passe par le même chemin, avec `envoi=True` : le message est écrit une
    dernière fois, puis PROMU — il quitte « Brouillons » pour « Envoyés » et part au relais. Le
    webmail créait auparavant un SECOND message puis « détachait » le brouillon, ce qui le mettait à
    la corbeille : on retrouvait chacun de ses brouillons envoyés dans sa Corbeille (RM3246). Deux
    identifiants pour une seule rédaction, et un faux supprimé — alors que D089 dit qu'un brouillon
    est un message marqué, donc un seul objet du début à la fin.

    L'intention est un PARAMÈTRE, pas une déduction. J'avais d'abord lu l'envoi dans l'absence de
    `composition` : or un simple réenregistrement n'en envoie pas non plus, et il serait parti tout
    seul. Une action qui expédie du courrier ne se devine pas."""
    boites = [b.boite_id for b in await account_mailboxes(s, compte)]
    r = await s.scalar(_place(comm_id, boites, "out"))          # un brouillon est une place ÉMISE
    if not r: return None
    c = await s.get(Comm, comm_id); ds = await _folders_by_id(s, boites)
    if c is None or r.sens != "out" or short_folder_id(ds.get(r.dossier_id)) != "drafts":
        return None                       # on ne réécrit QUE des brouillons : un message est un fait (D029)
    boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    now = datetime.now(timezone.utc)
    src_id, source = await _source_to_forward(s, compte, corps, store)
    raw_bytes = _compose(compte, adresse, corps, comm_id, now, None, source)
    from ..ingestion.analysis import analyze
    a = analyze(raw_bytes)
    if store is not None: store.write_message(str(comm_id), raw_bytes, replace=True)   # RM3631 : en squelette
    c.sujet, c.sujet_normalise = a.sujet, a.sujet_normalise
    c.snippet, c.corps_texte, c.taille = a.snippet, a.corps_texte or None, len(raw_bytes)
    c.nb_pieces_jointes = len(a.pieces)
    e = await s.get(CommEmail, comm_id)
    if e is not None: e.message_id, e.headers = a.message_id, a.headers
    await _add_participants(s, comm_id, a.participants)
    await _add_parts(s, comm_id, a.pieces, store, now)
    await _add_provenance(s, comm_id, src_id, now)
    if envoi:
        # La date d'un message parti est celle du DÉPART, pas celle de la première ébauche : sinon
        # il s'enterre dans « Envoyés » sous des messages plus récents que lui.
        c.date_recue = c.date_declaree = now
        cible = next((d for d in ds.values() if short_folder_id(d) == "sent"), None)
        # un déplacement donne un UID NEUF, pris au dossier d'arrivée (sémantique IMAP) — et il
        # s'obtient AVANT de bouger, sinon l'autoflush de la requête envoie l'ancien couple
        from ..served_uid import assign_async as assign_uid
        uid = await assign_uid(s, cible.dossier_id) if cible else None
        r.dossier_id, r.uid_servi = (cible.dossier_id if cible else None), uid
        r.dossier_origine_id = None
        # On remet dans la file en effaçant l'ÉTAT, jamais les dates : « il a été traité le 3 »
        # reste vrai même s'il est revenu. C'est toute la différence entre un état et un fait.
        r.exit_reason = None
        from ..modules import events
        # L'enveloppe vient des participants ANALYSÉS, comme à la création (RM3214) : le `cc` du
        # client n'est pas dans le corps de la requête, il est dans les en-têtes qu'on vient d'écrire.
        seen, enveloppe = set(), []
        for role, _name, adr, _ordre in a.participants:
            if role in ("to", "cc", "bcc") and adr and adr not in seen: seen.add(adr); enveloppe.append(adr)
        await events.emit_async(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(r.boite_id), "destinataires": enveloppe})
    await s.commit()
    log.info("brouillon %s %s par %s", comm_id, "envoyé" if envoi else "réenregistré", compte.login)
    return serialize(r, c, ds, adresse, extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "",
                                                "composition": corps.get("composition"), "reference": str(src_id) if src_id else None})

async def _address(s: AsyncSession, full: str):
    """l'adresse, créée au besoin — version asynchrone de celle de l'ingestion.

    Elle NORMALISE : une adresse saisie porte souvent son nom d'affichage (D126)."""
    from ..schema.models import Domaine
    from ..ingestion.ingestion import normalize_address
    full = normalize_address(full) or (full or "").strip().strip("<>")
    a = await s.scalar(select(Adresse).where(Adresse.adresse_complete == full))
    if a: return a
    local, _, dom = full.partition("@")
    nom = (dom or "invalide").lower()
    d = await s.scalar(select(Domaine).where(Domaine.nom_ascii == nom))
    if d is None:
        d = Domaine(domaine_id=uuid7(), nom_ascii=nom, nom_unicode=nom, heberge_par_nous=False); s.add(d); await s.flush()
    a = Adresse(adresse_id=uuid7(), local=local, local_cmp=local.lower(), domaine_id=d.domaine_id, adresse_complete=full)
    s.add(a); await s.flush()
    return a

async def create(s: AsyncSession, compte: Compte, corps: dict, store=None, ip_client: str | None = None) -> dict | None:
    """POST /messages : un message écrit ici — brouillon (composition présente) ou envoyé.
    V0 : le message est en base et au magasin ; l'émission SMTP (F109) prend le relais par un événement."""
    boites = await account_mailboxes(s, compte)
    adresses = {b.boite_id: (await s.get(Adresse, b.adresse_id)).adresse_complete for b in boites}
    boite = next((b for b in boites if adresses[b.boite_id] == corps.get("boite") or adresses[b.boite_id] == corps.get("from_adresse")), None) or (boites[0] if boites else None)
    if boite is None: return None
    ds = await _folders_by_id(s, [boite.boite_id])
    brouillon = bool(corps.get("composition"))
    cible = next((d for d in ds.values() if short_folder_id(d) == ("drafts" if brouillon else "sent")), None)
    comm_id = uuid7(); now = datetime.now(timezone.utc)
    src_id, source = await _source_to_forward(s, compte, corps, store)
    raw_bytes = _compose(compte, adresses[boite.boite_id], corps, comm_id, now, ip_client, source)
    from ..ingestion.analysis import analyze
    from ..ingestion.identity import identity_fingerprint
    a = analyze(raw_bytes)
    from ..store import fingerprint as fingerprint_of
    from ..schema.models import Blob
    pieces_ecrites = []
    if store is not None:
        # RM3631 : en squelette ; la ligne `blob` de l'empreinte du message est son identité, sans fichier à son nom
        w = store.write_message(str(comm_id), raw_bytes)
        raw, pieces_ecrites = w["empreinte"], w["blobs"]
        info = {"taille_octets": w["taille_octets"], "taille_stockee": w["taille_stockee"], "compression": w["compression"]}
    else:
        raw, info = fingerprint_of(raw_bytes), {"taille_octets": len(raw_bytes), "taille_stockee": len(raw_bytes), "compression": "aucune"}
    for e_, i_ in [(raw, info)] + pieces_ecrites:
        b = await s.get(Blob, e_)
        if b: b.nb_references += 1
        else: s.add(Blob(empreinte=e_, taille_octets=i_["taille_octets"], taille_stockee=i_["taille_stockee"], compression=i_["compression"], cree_le=now, nb_references=1))
        await s.flush()
    c = Comm(comm_id=comm_id, type="email", date_recue=now, date_declaree=now, date_ingestion=now, sens="out", sujet=a.sujet,
             sujet_normalise=a.sujet_normalise, thread_id=comm_id, nature="humain", from_adresse=adresses[boite.boite_id], from_nom=compte.nom,
             taille=len(raw_bytes), nb_pieces_jointes=len(a.pieces), est_chiffre=False, est_signe=False, snippet=a.snippet, corps_texte=a.corps_texte or None)
    s.add(c)
    s.add(CommEmail(comm_id=comm_id, message_id=a.message_id, headers=a.headers, blob_ref=raw, empreinte=identity_fingerprint(a), structure_mime=a.structure_mime, reponse_possible="oui"))
    from ..served_uid import assign_async as assign_uid
    s.add(Rattachement(comm_id=comm_id, boite_id=boite.boite_id, sens="out", compte_id=compte.compte_id,
                       status="new", personnel=False, gele=False,
                       dossier_id=cible.dossier_id if cible else None,
                       uid_servi=await assign_uid(s, cible.dossier_id if cible else None)))
    await s.flush()
    # CE QUE J'ÉCRIS, JE L'AI LU : la ligne de lecture se pose sur MOI (D175), et non plus sur le
    # rattachement. Sans elle, mon propre envoi me reviendrait en gras dans « Envoyés ».
    await s.execute(personal.open_stmt(compte.compte_id, comm_id, boite.boite_id, now))
    await _add_participants(s, comm_id, a.participants)
    await _add_parts(s, comm_id, a.pieces, store, now)
    await _add_provenance(s, comm_id, src_id, now)
    from ..modules import events
    if not brouillon:
        """Les destinataires de l'ENVELOPPE viennent des participants ANALYSÉS, pas du corps de la
        requête : le `cc` du client n'y était pas, et il n'était donc remis à personne — alors que
        l'en-tête du message l'affichait (RM3214)."""
        seen, enveloppe = set(), []
        for role, _name, adr, _ordre in a.participants:
            if role in ("to", "cc", "bcc") and adr and adr not in seen: seen.add(adr); enveloppe.append(adr)
        await events.emit_async(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(boite.boite_id), "destinataires": enveloppe})
    await s.commit()
    r = await s.get(Rattachement, (comm_id, boite.boite_id, "out"))
    return serialize(r, c, ds, adresses[boite.boite_id], extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "",
                                                                 "composition": corps.get("composition"), "reference": str(src_id) if src_id else None})
