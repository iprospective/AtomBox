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
from ..schema.modeles import Acces, Adresse, Blob, Boite, Comm, CommCitation, CommEmail, CommPieceJointe, Compte, Dossier, Filtre, Participant, PieceJointe, Rattachement
from ..uuid7 import uuid7
from ..journal import journal
from ..sync import sync
from . import mailbox
from . import personal_state as perso
from . import trace
from .. import settings

log = journal("api")

SPECIAUX = [ {"id": "inbox", "label": "Boîte de réception", "icon": "📥", "alias": ("INBOX",)},
             {"id": "sent", "label": "Envoyés", "icon": "📤", "alias": ("SENT", "SENT ITEMS", "ENVOYÉS", "ENVOYES"), "sortant": True},
             {"id": "drafts", "label": "Brouillons", "icon": "📝", "alias": ("DRAFTS", "BROUILLONS")},
             {"id": "junk", "label": "Indésirables", "icon": "🚫", "alias": ("JUNK", "SPAM", "INDÉSIRABLES")},
             {"id": "trash", "label": "Corbeille", "icon": "🗑", "alias": ("TRASH", "DELETED ITEMS", "CORBEILLE")},
             {"id": "traites", "label": "Traités", "icon": "✓", "vue": True, "alias": ()},
             {"id": "archives", "label": "Archives", "icon": "🗄", "vue": True, "alias": ()} ]
# Les identifiants sont en anglais (D181), les libellés en français : c'est le code qui voyage
# entre le serveur, le webmail et la base, pas le mot affiché.
STATUTS = [ {"id": "new", "label": "Nouveau"}, {"id": "todo", "label": "À faire"}, {"id": "doing", "label": "En cours"},
            {"id": "waiting", "label": "En attente"}, {"id": "processed", "label": "Traité"} ]
EN_TRAVAIL = ("todo", "doing")           # ce que le compteur « à faire » compte (D176 § 4)
VUES = ["trash", "junk", "archives", "traites"]

def special_de(alias: str | None) -> str | None:
    a = (alias or "").upper().split("/")[-1]
    for s in SPECIAUX:
        if a in s["alias"]: return s["id"]
    return None

# Les quatre boîtes d'état (D183) sont des lignes de `dossier` : sans cette table, elles
# apparaîtraient dans l'arborescence comme des dossiers utilisateur nommés « Processed ».
COURT_DE_L_ETAT = {"processed": "traites", "archived": "archives", "deleted": "trash", "junk": "junk"}

def dossier_id_court(d: Dossier | None) -> str | None:
    if d is None: return None
    if d.exit_reason: return COURT_DE_L_ETAT.get(d.exit_reason, d.exit_reason)
    return special_de(d.alias_imap) or str(d.dossier_id)

def iso(t: datetime | None) -> str | None: return t.astimezone(timezone.utc).isoformat() if t else None

# Les quatre transitions, et la date/l'auteur que chacune pose. UNE seule colonne d'état courant
# (`exit_reason`), mais quatre couples de dates : un message est généralement traité PUIS archivé
# des années après, et si l'archivage écrasait la date de traitement on perdrait la clé d'archivage
# (D014) — la donnée qui commande la transition suivante (D175 § 4 bis).
SORTIES = { "processed": ("processed_at", "processed_by"), "archived": ("archived_at", "archived_by"),
            "deleted": ("deleted_at", "deleted_by"), "junk": ("junk_at", "junk_by") }

def sorti_le(r: Rattachement) -> datetime | None:
    """la date de l'état COURANT — ce que l'ancien `sorti_le` disait, sans l'écraser au passage"""
    champ = SORTIES.get(r.exit_reason or "")
    return getattr(r, champ[0]) if champ else None

def quand(v) -> datetime | None:
    """ce que le webmail envoie : un nombre de millisecondes, ou une ISO 8601, ou null"""
    if v is None or v is False: return None
    if isinstance(v, (int, float)): return datetime.fromtimestamp(v / 1000, tz=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))

async def boites_du_compte(s: AsyncSession, compte: Compte) -> list[Boite]:
    return list(await s.scalars(select(Boite).join(Acces, Acces.boite_id == Boite.boite_id)
                                .where(Acces.compte_id == compte.compte_id, Acces.fin.is_(None))))

async def _axes_et_valeurs(s: AsyncSession) -> dict:
    """Les axes de classement et leurs valeurs (D002, D016) — ils étaient rendus `[]` et `{}` EN DUR.
    Conséquence visible : le formulaire « mes dossiers + » faisait `axes[0].id` sur une liste vide,
    levait, et le clic mourait en silence. Un référentiel vide n'est pas un référentiel neutre :
    tout ce qui s'appuie dessus casse sans le dire.

    Une seule requête pour les deux : un axe sans valeur existe (on vient de le créer), une valeur
    sans axe n'existe pas."""
    from ..schema.modeles import Axe, Tag
    axes = list(await s.scalars(select(Axe).order_by(Axe.ordre, Axe.nom)))
    lignes = (await s.execute(select(Axe.nom, Tag.valeur).join(Tag, Tag.axe_id == Axe.axe_id)
                              .where(Tag.actif.is_(True)).order_by(Axe.nom, Tag.valeur))).all()
    valeurs: dict = {a.nom: [] for a in axes}
    for nom, val in lignes:
        valeurs.setdefault(nom, []).append({"id": "%s:%s" % (nom, val), "label": val, "axe": nom})
    return {"axes": [{"id": a.nom, "label": a.nom.capitalize(), "derive": a.derive} for a in axes],
            "valeurs": valeurs}


def _tag_du_dossier(dossier: str):
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


async def referentiels(s: AsyncSession, compte: Compte) -> dict:
    boites = await boites_du_compte(s, compte)
    adresses = {b.boite_id: (await s.get(Adresse, b.adresse_id)).adresse_complete for b in boites}
    dossiers = list(await s.scalars(select(Dossier).where(Dossier.boite_id.in_([b.boite_id for b in boites])).order_by(Dossier.ordre, Dossier.nom)))
    util = [ {"id": str(d.dossier_id), "label": d.nom, "icon": "📁", "boite": adresses.get(d.boite_id)}
             for d in dossiers if not special_de(d.alias_imap) and not d.exit_reason ]
    # `action` sans action : NULL SQL, ou le JSON `null` des lignes écrites avant le correctif —
    # les deux veulent dire « ce filtre est un dossier virtuel, pas une règle » (D143).
    sans_action = or_(Filtre.action.is_(None), func.jsonb_typeof(Filtre.action) == "null")
    virtuels = list(await s.scalars(select(Filtre).where(Filtre.portee_type == "compte", Filtre.portee_id == compte.compte_id, sans_action, Filtre.actif.is_(True)).order_by(Filtre.ordre)))
    return { "moi": {"nom": compte.nom, "login": compte.login, "boites": [{"id": str(b.boite_id), "adresse": adresses[b.boite_id], "label": adresses[b.boite_id].split("@")[0]} for b in boites]},
             "speciaux": [{"id": x["id"], "label": x["label"], "icon": x["icon"], **({"vue": True} if x.get("vue") else {}), **({"sortant": True} if x.get("sortant") else {})} for x in SPECIAUX],
             "util": util, **(await _axes_et_valeurs(s)), "statuts": STATUTS, "vues": VUES,
             "virtuels": [{"id": "perso:" + str(f.filtre_id), "label": f.nom, "criteres": (f.predicat or {}).get("criteres", [])} for f in virtuels] }

def _condition_tag(axe: str, val: str | None):
    """Un dossier virtuel sur un TAG — sa raison d'être (D143). `val` absente = toute la FAMILLE :
    « tout ce qui porte un client », quel qu'il soit. C'est ce que demande « un dossier virtuel
    depuis un tag OU une famille de tags ».

    EXISTS plutôt qu'une jointure : un message portant trois tags du même axe doit apparaître une
    fois, pas trois — et la liste ne doit pas avoir à dédupliquer après coup."""
    from ..schema.modeles import Axe, CommTag, Tag
    sous = (select(CommTag.comm_id).join(Tag, Tag.tag_id == CommTag.tag_id)
            .join(Axe, Axe.axe_id == Tag.axe_id)
            .where(CommTag.comm_id == Comm.comm_id, Axe.nom == (axe or "").strip().lower()))
    if val and str(val).strip():
        sous = sous.where(Tag.valeur == str(val).strip())
    return sous.exists()


def _portee(compte_boites):
    return Rattachement.boite_id.in_(compte_boites)

async def _dossiers_par_id(s: AsyncSession, boites) -> dict:
    ds = list(await s.scalars(select(Dossier).where(Dossier.boite_id.in_(boites))))
    return {d.dossier_id: d for d in ds}

async def compteurs(s: AsyncSession, compte: Compte) -> dict:
    """UNE passe (D078) : par dossier, total / non lus / à faire — et les vues trash, archives, traites"""
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    if not boites: return {"compteurs": {}, "virtuels": [], "epingles": []}
    ds = await _dossiers_par_id(s, boites)
    # LE « NON LU » N'EST PLUS UNE COLONNE (D175) : c'est « moi, je ne l'ai pas ouvert », donc un
    # EXISTS sur read_state. Il entre dans le GROUP BY comme le faisait `lu_le IS NULL` — même forme,
    # même nombre de requêtes ; ce qui change, c'est que deux personnes ne lisent plus le même chiffre.
    non_lu = perso.a_voir_par(compte.compte_id).label("non_lu")
    rows = (await s.execute(select(Rattachement.dossier_id, Rattachement.exit_reason, non_lu,
                                   Rattachement.status, func.count().label("n"))
                            .where(_portee(boites)).group_by(Rattachement.dossier_id, Rattachement.exit_reason, non_lu, Rattachement.status))).all()
    c: dict = {}
    def bump(k, n, non_lu, statut):
        x = c.setdefault(k, {"t": 0, "u": 0, "f": 0}); x["t"] += n
        if non_lu: x["u"] += n
        if statut in EN_TRAVAIL: x["f"] += n
    # L'ORDRE COMPTE : l'état de sortie prime sur le dossier, parce qu'il EST la boîte aux lettres
    # (D175 § 4). Un message archivé rangé dans un dossier utilisateur se compte dans Archives, pas
    # dans son dossier — sinon le compteur annonce ce que la liste ne montre pas (D166).
    for dossier_id, sortie, non_lu, statut, n in rows:
        d = ds.get(dossier_id); k = dossier_id_court(d) or "inbox"
        if sortie == "archived": bump("archives", n, non_lu, statut); continue
        if sortie == "processed": bump("traites", n, non_lu, statut); continue
        if sortie == "junk": bump("junk", n, non_lu, statut); continue
        if sortie == "deleted" or k == "trash": bump("trash", n, non_lu, statut); continue
        bump(k, n, non_lu, statut)
    prefs = compte.preferences or {}
    ref = await referentiels(s, compte)
    c.update(await _compteurs_axes(s, boites, ds, compte))
    c.update(await _compteurs_virtuels(s, boites, ds, compte, ref["virtuels"]))
    return {"compteurs": c, "virtuels": ref["virtuels"], "epingles": prefs.get("epingles", [])}


async def _compteurs_axes(s: AsyncSession, boites, ds: dict, compte) -> dict:
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
    from ..schema.modeles import Axe, CommTag, Tag
    corbeilles = [d.dossier_id for d in ds.values() if dossier_id_court(d) == "trash"]
    non_lu = perso.a_voir_par(compte.compte_id)
    q = (select(Axe.nom, Tag.valeur,
                func.count(func.distinct(Rattachement.comm_id)).label("t"),
                func.count(func.distinct(case((non_lu, Rattachement.comm_id)))).label("u"),
                func.count(func.distinct(case((Rattachement.status.in_(EN_TRAVAIL), Rattachement.comm_id)))).label("f"))
         .select_from(CommTag)
         .join(Tag, Tag.tag_id == CommTag.tag_id).join(Axe, Axe.axe_id == Tag.axe_id)
         .join(Rattachement, Rattachement.comm_id == CommTag.comm_id)
         .where(_portee(boites)).group_by(Axe.nom, Tag.valeur))
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
                 func.count(func.distinct(case((Rattachement.status.in_(EN_TRAVAIL), Rattachement.comm_id)))).label("f"))
          .select_from(CommTag)
          .join(Tag, Tag.tag_id == CommTag.tag_id).join(Axe, Axe.axe_id == Tag.axe_id)
          .join(Rattachement, Rattachement.comm_id == CommTag.comm_id)
          .where(_portee(boites)).group_by(Axe.nom))
    if corbeilles:
        qa = qa.where(Rattachement.dossier_id.notin_(corbeilles))
    for nom, total, non_lus, a_faire in (await s.execute(qa)).all():
        out["axe:" + nom] = {"t": total, "u": non_lus, "f": a_faire}
    return out


async def _compteurs_virtuels(s: AsyncSession, boites, ds: dict, compte, virtuels: list) -> dict:
    """Un dossier virtuel n'est pas un dossier : il n'apparaît dans aucun `GROUP BY dossier_id`,
    donc il affichait **0/0** en portant des messages. On le compte avec la MÊME condition que
    celle qui le liste — sinon le compteur et la liste diraient deux choses.

    Toujours une seule passe (D078) : un agrégat conditionnel par dossier virtuel dans la même
    requête, plutôt qu'une requête par dossier."""
    if not virtuels:
        return {}
    colonnes, cles = [], []
    for v in virtuels:
        conds = []
        for crit in (v.get("criteres") or []):
            axe = crit.get("axe")
            if not axe:
                continue
            if axe == "dossier" and crit.get("val"): conds.append(_condition_dossier(crit["val"], None, ds, compte))
            elif axe == "from" and crit.get("val"): conds.append(Comm.from_adresse.ilike("%" + crit["val"] + "%"))
            elif axe == "sujet" and crit.get("val"): conds.append(Comm.sujet.ilike("%" + crit["val"] + "%"))
            else: conds.append(_condition_tag(axe, crit.get("val")))
        if not conds:
            continue
        ou = and_(*conds)
        cles.append(v["id"])
        colonnes.append(func.count().filter(ou).label("t%d" % len(cles)))
        colonnes.append(func.count().filter(and_(ou, perso.a_voir_par(compte.compte_id))).label("u%d" % len(cles)))
        colonnes.append(func.count().filter(and_(ou, Rattachement.status.in_(EN_TRAVAIL))).label("f%d" % len(cles)))
    if not cles:
        return {}
    corbeilles = [d.dossier_id for d in ds.values() if dossier_id_court(d) == "trash"]
    q = (select(*colonnes).select_from(Rattachement).join(Comm, Comm.comm_id == Rattachement.comm_id)
         .where(_portee(boites)))
    if corbeilles:
        q = q.where(Rattachement.dossier_id.notin_(corbeilles))     # la corbeille ne compte pas
    ligne = (await s.execute(q)).one()
    return {cle: {"t": ligne[i * 3], "u": ligne[i * 3 + 1], "f": ligne[i * 3 + 2]} for i, cle in enumerate(cles)}

def _condition_dossier(dossier: str, kind: str | None, ds: dict, compte):
    """la condition SQL d'un dossier du webmail"""
    par_court = {}
    for d in ds.values(): par_court.setdefault(dossier_id_court(d), []).append(d.dossier_id)
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
    branche = _tag_du_dossier(dossier)
    if branche: return _condition_tag(branche[0], branche[1])
    try: return Rattachement.dossier_id == __import__("uuid").UUID(dossier)
    except Exception: return Rattachement.dossier_id.is_(None) & (Rattachement.comm_id.is_(None))   # rien

TRIS = { "date_desc": Comm.date_recue.desc(), "date_asc": Comm.date_recue.asc(), "from_nom": Comm.from_nom.asc(), "subj": Comm.sujet.asc(), "taille": Comm.taille.desc() }

async def liste(s: AsyncSession, compte: Compte, dossier: str, kind: str | None, filtre: str | None, tri: str | None, sens: str | None, statut: str | None, tout: bool = False) -> list[dict]:
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    if not boites: return []
    ds = await _dossiers_par_id(s, boites)
    q = select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id).where(_portee(boites))
    if kind == "perso":
        f = await s.get(Filtre, __import__("uuid").UUID(dossier.split(":", 1)[1])) if dossier.startswith("perso:") else None
        conds = []
        for c in ((f.predicat or {}).get("criteres", []) if f else []):
            if c.get("axe") == "dossier" and c.get("val"): conds.append(_condition_dossier(c["val"], None, ds, compte))
            elif c.get("axe") == "from" and c.get("val"): conds.append(Comm.from_adresse.ilike("%" + c["val"] + "%"))
            elif c.get("axe") == "sujet" and c.get("val"): conds.append(Comm.sujet.ilike("%" + c["val"] + "%"))
            elif c.get("axe"): conds.append(_condition_tag(c["axe"], c.get("val")))
        q = q.where(and_(*conds)) if conds else q.where(Comm.comm_id.is_(None))
        q = q.where(Rattachement.dossier_id.notin_([d.dossier_id for d in ds.values() if dossier_id_court(d) == "trash"]))
    else:
        q = q.where(_condition_dossier(dossier, kind, ds, compte))
    est_vue = dossier in VUES
    if not tout:
        if sens in ("in", "out"): q = q.where(Comm.sens == sens)
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
        if filtre == "non_lus": q = q.where(perso.a_voir_par(compte.compte_id))
        if filtre == "recents": q = q.where(Comm.date_recue >= datetime.now(timezone.utc) - timedelta(days=30))
        if filtre == "pj": q = q.where(Comm.nb_pieces_jointes > 0)
        if filtre == "lourds": q = q.where(Comm.taille > 2048 * 1024)
    q = q.order_by(TRIS.get(tri or "date_desc", TRIS["date_desc"])).limit(500)
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    lignes = (await s.execute(q)).all()
    # les tags de TOUTE la liste en une passe (D078) : une requête par message rendrait la
    # deuxième page inutilisable, et c'est le tag qui porte le classement (D002)
    from .tags import tags_de
    tags = await tags_de(s, [c.comm_id for _, c in lignes])
    etats = await perso.etats_de(s, compte.compte_id, [c.comm_id for _, c in lignes])
    return [serialiser(r, c, ds, adresses.get(r.boite_id), extra={"tags": tags.get(c.comm_id, [])},
                       etat=etats.get((r.comm_id, r.boite_id)))
            for r, c in lignes]

def serialiser(r: Rattachement, c: Comm, ds: dict, boite_adresse: str | None, complet: bool = False, extra: dict | None = None, etat: dict | None = None) -> dict:
    """`etat` est l'état PERSONNEL du compte qui regarde (D175) : il ne se lit plus sur le
    rattachement, donc il ne peut plus être deviné ici — il se passe. Absent = personne n'y a
    touché, ce qui est le cas de la grande majorité des lignes."""
    origine = dossier_id_court(ds.get(r.dossier_origine_id)) if r.dossier_origine_id else dossier_id_court(ds.get(r.dossier_id))
    courant = dossier_id_court(ds.get(r.dossier_id))
    o = { "id": str(c.comm_id), "sujet": c.sujet, "from_nom": c.from_nom, "from_adresse": c.from_adresse,
          "date_recue": iso(c.date_recue), "thread_id": str(c.thread_id) if c.thread_id else None,
          "nb_pieces_jointes": c.nb_pieces_jointes, "taille": c.taille, "sens": c.sens, "nature": c.nature, "snippet": c.snippet,
          "boite": boite_adresse, "statut": r.status, "sorti_le": iso(sorti_le(r)), "motif_sortie": r.exit_reason,
          "statut_le": iso(r.status_at), "traite_le": iso(r.processed_at), "archive_le": iso(r.archived_at),
          **perso.serialiser_etat(etat),
          "dossier_origine": origine or "inbox", "dossier": courant if courant != origine else None,
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
    if dossier_id_court(ds.get(r.dossier_id)) != "drafts":
        return None
    return {"mode": "tr" if ref else "new", "src": ref, "de": adresse,
            "a": ", ".join(dest), "cc": ", ".join(copies), "sujet": c.sujet or "",
            "corps": corps, "pieces_jointes": [], "reference": ref}

async def detail(s: AsyncSession, compte: Compte, comm_id, magasin=None) -> dict | None:
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, _portee(boites)).limit(1))
    if not r: return None
    c = await s.get(Comm, comm_id); e = await s.get(CommEmail, comm_id); ds = await _dossiers_par_id(s, boites)
    boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    lignes = (await s.execute(select(Participant.role, Adresse.adresse_complete).join(Adresse, Participant.adresse_id == Adresse.adresse_id)
                              .where(Participant.comm_id == comm_id, Participant.role.in_(("to", "cc"))).order_by(Participant.ordre))).all()
    dest = [a for role, a in lignes if role == "to"]
    copies = [a for role, a in lignes if role == "cc"]
    pjs = (await s.execute(select(CommPieceJointe, PieceJointe).join(PieceJointe, PieceJointe.piece_jointe_id == CommPieceJointe.piece_jointe_id)
                           .where(CommPieceJointe.comm_id == comm_id).order_by(CommPieceJointe.ordre))).all()
    corps = ""
    if magasin is not None and magasin.existe(str(comm_id)):
        try:
            from ..ingestion.analyse import analyser
            corps = analyser(magasin.lire(str(comm_id))).corps_texte
        except Exception as ex: log.warning("corps de %s illisible : %s", comm_id, ex)
    from .tags import tags_de
    provenance = await _provenance_de(s, comm_id)
    ref = str(provenance) if provenance else None
    vers = await _messages_des_encapsules(s, comm_id, boites, pjs)      # D168
    etats = await perso.etats_de(s, compte.compte_id, [comm_id])
    return serialiser(r, c, ds, adresse, True, etat=etats.get((r.comm_id, r.boite_id)), extra={
        "tags": (await tags_de(s, [comm_id])).get(comm_id, []), "reference": ref,
        "destinataires": list(dest) + list(copies), "composition": _composition(r, c, ds, adresse, dest, copies, corps, ref),
        "corps": corps, "reponse_possible": e.reponse_possible if e else None, "list_id": e.list_id if e else None,
        "pieces_jointes": [ {"pj_id": str(p.piece_jointe_id), "ordre": l.ordre, "nom": l.nom_declare or ("piece-%d" % l.ordre), "octets": p.taille_octets,
                             "mime_declare": l.type_declare, "mime_detecte": p.type_detecte, "sha256": p.blob_ref, "partage_par": p.nb_references,
                             "content_id": l.content_id, "disposition": l.disposition,
                             "comm_id": vers.get(str(p.piece_jointe_id))} for l, p in pjs ] })

async def piece_jointe(s: AsyncSession, compte: Compte, comm_id, pj_id, magasin=None) -> dict | None:
    """Les OCTETS d'une pièce jointe (F136), dans la portée du compte (D036) — hors portée : None,
    donc 404, jamais 403 (D108).

    Le type rendu est le type DÉTECTÉ (D032), jamais le déclaré : c'est la seule règle qui empêche
    qu'un exécutable nommé `facture.pdf` s'ouvre comme un PDF. Et le nom est nettoyé avant de partir
    dans un en-tête — un nom de fichier vient du message, donc de l'extérieur."""
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, _portee(boites)).limit(1))
    if not r: return None
    ligne = await s.scalar(select(CommPieceJointe).where(CommPieceJointe.comm_id == comm_id,
                                                        CommPieceJointe.piece_jointe_id == pj_id).limit(1))
    if ligne is None: return None
    p = await s.get(PieceJointe, pj_id)
    if p is None or magasin is None or not magasin.existe(p.blob_ref): return None
    return {"octets": magasin.lire(p.blob_ref), "type": p.type_detecte or "application/octet-stream",
            "nom": _nom_de_fichier(ligne.nom_declare or ("piece-%d" % ligne.ordre)),
            "disposition": ligne.disposition or "attachment"}


async def _messages_des_encapsules(s: AsyncSession, comm_id, boites: list, pjs: list) -> dict:
    """D168 — une partie `message/rfc822` dont l'original est EN BASE et DANS LA PORTÉE du lecteur
    se rend comme une référence, pas comme un fichier. La résolution n'accorde aucun droit : elle
    ne regarde que ce que le lecteur peut déjà voir.

    Deux chemins, dans cet ordre : la provenance posée à l'émission (D067), puis le `Message-ID` du
    message encapsulé — le seul indice quand il vient de l'extérieur (D064). Un encapsulé non résolu
    aujourd'hui se résoudra le jour où son original sera ingéré (D163)."""
    encapsules = [(l, p) for l, p in pjs if (p.type_detecte or "") == "message/rfc822"]
    if not encapsules: return {}
    cite = await s.scalar(select(CommCitation.cite_comm_id).where(CommCitation.comm_id == comm_id).limit(1))
    if cite is not None and not await s.scalar(select(Rattachement.comm_id).where(Rattachement.comm_id == cite, _portee(boites)).limit(1)):
        cite = None                      # l'original existe, mais pas pour ce lecteur : un contenu, pas un lien
    out = {}
    for l, p in encapsules:
        vise = cite
        if vise is None:
            vise = await _resoudre_par_message_id(s, p, boites)
        if vise is not None: out[str(p.piece_jointe_id)] = str(vise)
        cite = None                      # la provenance ne vaut que pour la PREMIÈRE pièce encapsulée
    return out


async def _resoudre_par_message_id(s: AsyncSession, p: PieceJointe, boites: list):
    """Le `Message-ID` lu dans les octets de l'encapsulé, confronté à ce que le lecteur possède."""
    from ..magasin import Magasin
    try:
        m = Magasin(settings.read("ATOMBOX_STORE", "./magasin"))
        if not m.existe(p.blob_ref): return None
        interne = email.message_from_bytes(m.lire(p.blob_ref), policy=email.policy.SMTP)
        mid = (interne["Message-ID"] or "").strip()
    except Exception as ex:
        log.debug("encapsulé illisible %s : %s", p.piece_jointe_id, ex); return None
    if not mid: return None
    return await s.scalar(select(Rattachement.comm_id).join(CommEmail, CommEmail.comm_id == Rattachement.comm_id)
                          .where(CommEmail.message_id == mid, _portee(boites)).limit(1))


async def fil(s: AsyncSession, compte: Compte, comm_id) -> list[dict]:
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    c = await s.get(Comm, comm_id)
    if not c: return []
    ds = await _dossiers_par_id(s, boites)
    q = select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id).where(_portee(boites), Comm.thread_id == (c.thread_id or c.comm_id)).order_by(Comm.date_recue.asc())
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    lignes = (await s.execute(q)).all()
    etats = await perso.etats_de(s, compte.compte_id, [cc.comm_id for _, cc in lignes])
    vus, out = set(), []
    for r, cc in lignes:
        if cc.comm_id in vus: continue
        vus.add(cc.comm_id)
        out.append(serialiser(r, cc, ds, adresses.get(r.boite_id), etat=etats.get((r.comm_id, r.boite_id))))
    return out

async def patcher(s: AsyncSession, compte: Compte, comm_id, patch: dict) -> dict | None:
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
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, _portee(boites)).limit(1))
    if not r: return None
    ds = await _dossiers_par_id(s, boites)
    n = 0; dossier_avant = r.dossier_id
    maintenant = datetime.now(timezone.utc)

    async def sortir(valeur: str | None):
        """Le déplacement vit dans `services/mailbox.py` : trois chemins y mènent — ce clic, un
        `UID MOVE` d'un client IMAP, une règle à l'ingestion — et ils doivent écrire exactement la
        même chose (D183). Ici on ne fait que compter le changement."""
        nonlocal n
        await mailbox.deplacer(s, r, valeur, compte.compte_id)
        n += 1

    for k, v in (patch or {}).items():
        if k == "lu":
            if v:
                await perso.ouvrir(s, compte.compte_id, comm_id, r.boite_id)
                await perso.retirer(s, compte.compte_id, comm_id, r.boite_id, perso.A_REVOIR)
                trace.tracer(s, compte.compte_id, "opened", "rattachement", comm_id, {"boite_id": str(r.boite_id)})
            else:
                # « NON LU » N'EXISTE PLUS (D175 § 2) : le geste veut dire « j'y suis passé, il faut
                # que j'y retourne ». On le dit, au lieu d'effacer la preuve du passage.
                await perso.poser(s, compte.compte_id, comm_id, r.boite_id, perso.A_REVOIR)
                trace.tracer(s, compte.compte_id, "marked", "rattachement", comm_id,
                             {"boite_id": str(r.boite_id), "marqueur": perso.A_REVOIR, "pose": True})
            n += 1
        elif k == "a_revoir":
            if v: await perso.poser(s, compte.compte_id, comm_id, r.boite_id, perso.A_REVOIR)
            else: await perso.retirer(s, compte.compte_id, comm_id, r.boite_id, perso.A_REVOIR)
            trace.tracer(s, compte.compte_id, "marked", "rattachement", comm_id,
                         {"boite_id": str(r.boite_id), "marqueur": perso.A_REVOIR, "pose": bool(v)})
            n += 1
        elif k == "sommeil":
            await perso.poser(s, compte.compte_id, comm_id, r.boite_id, perso.SOMMEIL, due_at=quand(v)) if v \
                else await perso.retirer(s, compte.compte_id, comm_id, r.boite_id, perso.SOMMEIL)
            n += 1
        elif k == "statut" and v in [x["id"] for x in STATUTS]:
            if v != r.status:
                trace.tracer(s, compte.compte_id, "status_changed", "rattachement", comm_id,
                             {"boite_id": str(r.boite_id), "avant": r.status, "apres": v})
            r.status, r.status_at, r.status_by = v, maintenant, compte.compte_id; n += 1
        elif k == "motif_sortie": await sortir(v or None)
        elif k == "sorti_le":
            # La date ne se pose plus de l'extérieur : c'est la TRANSITION qui la pose, dans la case
            # de l'état où elle a eu lieu. Accepter un `sorti_le` nu, c'était pouvoir dater un
            # traitement sans dire qu'il avait eu lieu.
            log.debug("PATCH %s : sorti_le ignoré — la date suit la transition (D175)", comm_id)
        elif k == "drapeau":
            await perso.toucher(s, compte.compte_id, comm_id, r.boite_id, flagged=bool(v)); n += 1
        elif k == "personnel": r.personnel = bool(v); n += 1
        elif k == "dossier":
            # RANGER DANS UNE BOÎTE D'ÉTAT, C'EST CHANGER D'ÉTAT (D183). Le webmail envoie encore
            # `{dossier: "trash"}` pour mettre à la corbeille : ce n'est pas un rangement, c'est une
            # transition, et elle doit poser sa date, son auteur et sa trace comme les autres.
            cible = next((d for d in ds.values() if d.boite_id == r.boite_id and dossier_id_court(d) == v), None) if v else None
            if v is not None and cible is None:
                log.warning("PATCH %s : boîte aux lettres inconnue %r", comm_id, v); continue
            if (cible is not None and cible.exit_reason) or v is None:
                await sortir(cible.exit_reason if cible is not None else None)
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
            from ..uid_servi import attribuer_async as attribuer_uid
            uid = await attribuer_uid(s, cible.dossier_id)
            r.dossier_id, r.uid_servi = cible.dossier_id, uid
            n += 1
        elif k == "suppr" and v:
            await sortir("deleted")
        elif k == "tags": log.info("PATCH %s : tags ignorés en V0 (pas d'axe métier, D140b)", comm_id)
        else: log.debug("PATCH %s : champ ignoré %s", comm_id, k)
    # SYNCHRONISATION MONTANTE (F113) : l'état part vers IMAP hors processus, jamais dans la
    # requête — un serveur IMAP lent ou absent ne doit pas faire échouer un clic (D161).
    # L'émission se fait ICI, au point de passage unique de l'API, et non dans un déclencheur ORM :
    # insérer une ligne pendant le flush d'une autre est un piège (D158, D161).
    if n and not sync.descendante() and any(k in (patch or {}) for k in ("lu", "drapeau", "dossier", "suppr")):
        from ..modules import evenements
        await evenements.emettre_async(s, "rattachement.change",
                                       {"comm_id": str(comm_id), "boite_id": str(r.boite_id),
                                        "dossier_avant": str(dossier_avant) if dossier_avant else None})
    await s.commit()
    c = await s.get(Comm, comm_id); boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    etats = await perso.etats_de(s, compte.compte_id, [comm_id])
    return {"modifies": n, "message": serialiser(r, c, ds, adresse, etat=etats.get((r.comm_id, r.boite_id)))}

async def detacher(s: AsyncSession, compte: Compte, comm_id) -> bool:
    r = await patcher(s, compte, comm_id, {"suppr": True})
    return r is not None

def hote_atombox() -> str:
    """le nom de CETTE instance dans la chaîne de relais — jamais deviné à partir d'une requête"""
    return settings.read("ATOMBOX_HOST") or socket.getfqdn() or "atombox"

def entetes_de_relais(m: email.message.EmailMessage, comm_id, expediteur: str, quand: datetime, ip_client: str | None = None) -> None:
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
            % (trace, hote_atombox(), comm_id, expediteur, email.utils.format_datetime(quand)))
    m["X-Mailer"] = "AtomBox"                                     # sans version : pas de carte des failles
    # un Received se pose EN TÊTE : la chaîne de trace se lit du plus récent au plus ancien, et le
    # relais suivant ajoutera le sien au-dessus du nôtre (RFC 5321 § 4.4)
    anciens = m.items()
    for cle in dict.fromkeys(k for k, _ in anciens): del m[cle]
    m["Received"] = recu
    for cle, valeur in anciens: m[cle] = valeur

def _nom_de_fichier(sujet) -> str:
    """Le nom que verra le destinataire : le sujet du message transféré, rendu inoffensif."""
    propre = re.sub(r"[^\w .()\[\]-]+", "_", str(sujet or "message transfere"), flags=re.UNICODE).strip()
    return (propre or "message transfere")[:80]


async def _source_a_transferer(s: AsyncSession, compte: Compte, corps: dict, magasin):
    """Le message transféré, LU DANS LE MAGASIN — jamais reconstruit depuis ce que l'écran affiche.

    Et lu dans la PORTÉE du compte (D036) : transférer se fait sur ce qu'on a le droit de lire,
    la référence venant du client. Rend (comm_id, octets) ou (None, None)."""
    ref = corps.get("reference")
    if not ref or magasin is None: return None, None
    try: src_id = uuid.UUID(str(ref))
    except (ValueError, AttributeError, TypeError): return None, None
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    if not await s.scalar(select(Rattachement.comm_id).where(Rattachement.comm_id == src_id, _portee(boites)).limit(1)):
        log.warning("transfert refuse : %s hors de la portee de %s", src_id, compte.login)
        return None, None
    if not magasin.existe(str(src_id)): return src_id, None      # purgé : le transfert part sans lui (Q030)
    return src_id, magasin.lire(str(src_id))


async def _poser_pieces(s: AsyncSession, comm_id, pieces, magasin, quand) -> None:
    """Les pièces d'un message écrit ici entrent en base comme celles d'un message reçu — même
    déduplication par empreinte (D024). Sans ça, un transfert s'envoyait avec son encapsulé dans
    les octets mais se relisait sans rien : la pièce existait et l'écran ne la voyait pas."""
    from ..magasin import empreinte as empreinte_de
    for l in await s.scalars(select(CommPieceJointe).where(CommPieceJointe.comm_id == comm_id)):
        await s.delete(l)
    await s.flush()
    for p in pieces:
        if magasin is not None: ref, info = magasin.deposer(p.octets)
        else: ref, info = empreinte_de(p.octets), {"taille_octets": len(p.octets), "taille_stockee": len(p.octets), "compression": "aucune"}
        b = await s.get(Blob, ref)
        if b: b.nb_references += 1
        else: s.add(Blob(empreinte=ref, taille_octets=info["taille_octets"], taille_stockee=info["taille_stockee"],
                         compression=info["compression"], cree_le=quand, nb_references=1))
        pj = await s.scalar(select(PieceJointe).where(PieceJointe.blob_ref == ref, PieceJointe.type_detecte == p.type_detecte))
        if pj: pj.nb_references += 1
        else:
            pj = PieceJointe(piece_jointe_id=uuid7(), blob_ref=ref, type_detecte=p.type_detecte, taille_octets=len(p.octets), nb_references=1)
            s.add(pj); await s.flush()
        s.add(CommPieceJointe(comm_id=comm_id, piece_jointe_id=pj.piece_jointe_id, ordre=p.ordre, nom_declare=p.nom_declare,
                              type_declare=p.type_declare, transfer_encoding=p.transfer_encoding, disposition=p.disposition,
                              content_id=p.content_id, parametres=p.parametres))


async def _poser_provenance(s: AsyncSession, comm_id, src_id, quand) -> None:
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
                       origine="emission", detecte_le=quand))


async def _provenance_de(s: AsyncSession, comm_id):
    """L'identifiant du message transféré, s'il y en a un."""
    return await s.scalar(select(CommCitation.cite_comm_id).where(CommCitation.comm_id == comm_id).limit(1))


def _composer(compte: Compte, adresse: str, corps: dict, comm_id, quand, ip_client: str | None = None,
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
        entetes_de_relais(m, comm_id, adresse, quand, ip_client)   # D162
        sujet = email.message_from_bytes(source, policy=email.policy.SMTP)["Subject"]
        return _assembler_transfert(m, frontiere, corps.get("corps") or "", source, _nom_de_fichier(sujet) + ".eml")
    m.set_content(corps.get("corps") or "")
    entetes_de_relais(m, comm_id, adresse, quand, ip_client)   # D162
    return m.as_bytes()


def _entetes(msg) -> bytes:
    """Les en-têtes SEULS, pliés et encodés par la politique (RFC 2047, 2231) — sans le générateur,
    qui ne sait pas écrire un multipart dont on fournit soi-même une partie."""
    return b"".join(msg.policy.fold_binary(k, v) for k, v in msg.items())


def encodage_de_transport(brut: bytes) -> str:
    """L'encodage qui transporte `brut` SANS LE TOUCHER, quand il existe.

    `7bit` si c'est de l'ASCII à lignes courtes — le cas courant, puisque MIME a déjà encodé
    l'intérieur du message ; `8bit` s'il porte des octets hauts ; `base64` en dernier recours, pour
    ce que SMTP ne transporte pas tel quel : une ligne de plus de 998 octets (RFC 5322 § 2.1.1) ou un
    octet nul. La RFC 2045 § 6.4 n'autorise pas `base64` pour un type `message/`, mais tous les
    clients le lisent — et c'est le seul encodage qui garde encore l'octet exact (Q074)."""
    if b"\0" in brut or any(len(l.rstrip(b"\r")) > 998 for l in brut.split(b"\n")):
        return "base64"
    return "8bit" if any(o > 0x7F for o in brut) else "7bit"


def _assembler_transfert(m, frontiere: str, commentaire: str, source: bytes, nom: str) -> bytes:
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
    cte = encodage_de_transport(source)
    piece["Content-Transfer-Encoding"] = cte
    charge = base64.encodebytes(source).replace(b"\n", b"\r\n") if cte == "base64" else source
    F = frontiere.encode("ascii")
    return (_entetes(m) + b"\r\n"
            + b"--" + F + b"\r\n" + texte.as_bytes()
            + b"\r\n--" + F + b"\r\n" + _entetes(piece) + b"\r\n" + charge
            + b"\r\n--" + F + b"--\r\n")

async def _poser_participants(s: AsyncSession, comm_id, participants) -> None:
    """Les destinataires sont une DONNÉE du message, pas un écho de la requête : sans eux,
    un message envoyé se relit sans destinataire (et un brouillon sans personne à qui écrire)."""
    for p in await s.scalars(select(Participant).where(Participant.comm_id == comm_id)):
        await s.delete(p)
    await s.flush()
    for role, nom, adr, ordre in participants:
        s.add(Participant(comm_id=comm_id, role=role, adresse_id=(await _adresse(s, adr)).adresse_id, nom_affiche=nom, ordre=ordre))


async def remplacer_brouillon(s: AsyncSession, compte: Compte, comm_id, corps: dict, magasin=None, envoi: bool = False) -> dict | None:
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
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, Rattachement.boite_id.in_(boites)).limit(1))
    if not r: return None
    c = await s.get(Comm, comm_id); ds = await _dossiers_par_id(s, boites)
    if c is None or c.sens != "out" or dossier_id_court(ds.get(r.dossier_id)) != "drafts":
        return None                       # on ne réécrit QUE des brouillons : un message est un fait (D029)
    boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    maintenant = datetime.now(timezone.utc)
    src_id, source = await _source_a_transferer(s, compte, corps, magasin)
    octets = _composer(compte, adresse, corps, comm_id, maintenant, None, source)
    from ..ingestion.analyse import analyser
    a = analyser(octets)
    if magasin is not None: magasin.ecrire(str(comm_id), octets, remplacer=True)
    c.sujet, c.sujet_normalise = a.sujet, a.sujet_normalise
    c.snippet, c.corps_texte, c.taille = a.snippet, a.corps_texte or None, len(octets)
    c.nb_pieces_jointes = len(a.pieces)
    e = await s.get(CommEmail, comm_id)
    if e is not None: e.message_id, e.headers = a.message_id, a.headers
    await _poser_participants(s, comm_id, a.participants)
    await _poser_pieces(s, comm_id, a.pieces, magasin, maintenant)
    await _poser_provenance(s, comm_id, src_id, maintenant)
    if envoi:
        # La date d'un message parti est celle du DÉPART, pas celle de la première ébauche : sinon
        # il s'enterre dans « Envoyés » sous des messages plus récents que lui.
        c.date_recue = c.date_declaree = maintenant
        cible = next((d for d in ds.values() if dossier_id_court(d) == "sent"), None)
        # un déplacement donne un UID NEUF, pris au dossier d'arrivée (sémantique IMAP) — et il
        # s'obtient AVANT de bouger, sinon l'autoflush de la requête envoie l'ancien couple
        from ..uid_servi import attribuer_async as attribuer_uid
        uid = await attribuer_uid(s, cible.dossier_id) if cible else None
        r.dossier_id, r.uid_servi = (cible.dossier_id if cible else None), uid
        r.dossier_origine_id = None
        # On remet dans la file en effaçant l'ÉTAT, jamais les dates : « il a été traité le 3 »
        # reste vrai même s'il est revenu. C'est toute la différence entre un état et un fait.
        r.exit_reason = None
        from ..modules import evenements
        # L'enveloppe vient des participants ANALYSÉS, comme à la création (RM3214) : le `cc` du
        # client n'est pas dans le corps de la requête, il est dans les en-têtes qu'on vient d'écrire.
        vus, enveloppe = set(), []
        for role, _nom, adr, _ordre in a.participants:
            if role in ("to", "cc", "bcc") and adr and adr not in vus: vus.add(adr); enveloppe.append(adr)
        await evenements.emettre_async(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(r.boite_id), "destinataires": enveloppe})
    await s.commit()
    log.info("brouillon %s %s par %s", comm_id, "envoyé" if envoi else "réenregistré", compte.login)
    return serialiser(r, c, ds, adresse, extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "",
                                                "composition": corps.get("composition"), "reference": str(src_id) if src_id else None})

async def _adresse(s: AsyncSession, complete: str):
    """l'adresse, créée au besoin — version asynchrone de celle de l'ingestion.

    Elle NORMALISE : une adresse saisie porte souvent son nom d'affichage (D126)."""
    from ..schema.modeles import Domaine
    from ..ingestion.ingestion import normaliser_adresse
    complete = normaliser_adresse(complete) or (complete or "").strip().strip("<>")
    a = await s.scalar(select(Adresse).where(Adresse.adresse_complete == complete))
    if a: return a
    local, _, dom = complete.partition("@")
    nom = (dom or "invalide").lower()
    d = await s.scalar(select(Domaine).where(Domaine.nom_ascii == nom))
    if d is None:
        d = Domaine(domaine_id=uuid7(), nom_ascii=nom, nom_unicode=nom, heberge_par_nous=False); s.add(d); await s.flush()
    a = Adresse(adresse_id=uuid7(), local=local, local_cmp=local.lower(), domaine_id=d.domaine_id, adresse_complete=complete)
    s.add(a); await s.flush()
    return a

async def creer(s: AsyncSession, compte: Compte, corps: dict, magasin=None, ip_client: str | None = None) -> dict | None:
    """POST /messages : un message écrit ici — brouillon (composition présente) ou envoyé.
    V0 : le message est en base et au magasin ; l'émission SMTP (F109) prend le relais par un événement."""
    boites = await boites_du_compte(s, compte)
    adresses = {b.boite_id: (await s.get(Adresse, b.adresse_id)).adresse_complete for b in boites}
    boite = next((b for b in boites if adresses[b.boite_id] == corps.get("boite") or adresses[b.boite_id] == corps.get("from_adresse")), None) or (boites[0] if boites else None)
    if boite is None: return None
    ds = await _dossiers_par_id(s, [boite.boite_id])
    brouillon = bool(corps.get("composition"))
    cible = next((d for d in ds.values() if dossier_id_court(d) == ("drafts" if brouillon else "sent")), None)
    comm_id = uuid7(); maintenant = datetime.now(timezone.utc)
    src_id, source = await _source_a_transferer(s, compte, corps, magasin)
    octets = _composer(compte, adresses[boite.boite_id], corps, comm_id, maintenant, ip_client, source)
    from ..ingestion.analyse import analyser
    from ..ingestion.identite import empreinte_identite
    a = analyser(octets)
    from ..magasin import empreinte as empreinte_de
    from ..schema.modeles import Blob
    if magasin is not None:
        magasin.ecrire(str(comm_id), octets)
        brut, info = magasin.deposer(octets)
    else:
        brut, info = empreinte_de(octets), {"taille_octets": len(octets), "taille_stockee": len(octets), "compression": "aucune"}
    b = await s.get(Blob, brut)
    if b: b.nb_references += 1
    else: s.add(Blob(empreinte=brut, taille_octets=info["taille_octets"], taille_stockee=info["taille_stockee"], compression=info["compression"], cree_le=maintenant, nb_references=1))
    c = Comm(comm_id=comm_id, type="email", date_recue=maintenant, date_declaree=maintenant, date_ingestion=maintenant, sens="out", sujet=a.sujet,
             sujet_normalise=a.sujet_normalise, thread_id=comm_id, nature="humain", from_adresse=adresses[boite.boite_id], from_nom=compte.nom,
             taille=len(octets), nb_pieces_jointes=len(a.pieces), est_chiffre=False, est_signe=False, snippet=a.snippet, corps_texte=a.corps_texte or None)
    s.add(c)
    s.add(CommEmail(comm_id=comm_id, message_id=a.message_id, headers=a.headers, blob_ref=brut, empreinte=empreinte_identite(a), structure_mime=a.structure_mime, reponse_possible="oui"))
    from ..uid_servi import attribuer_async as attribuer_uid
    s.add(Rattachement(comm_id=comm_id, boite_id=boite.boite_id, compte_id=compte.compte_id,
                       status="new", personnel=False, gele=False,
                       dossier_id=cible.dossier_id if cible else None,
                       uid_servi=await attribuer_uid(s, cible.dossier_id if cible else None)))
    await s.flush()
    # CE QUE J'ÉCRIS, JE L'AI LU : la ligne de lecture se pose sur MOI (D175), et non plus sur le
    # rattachement. Sans elle, mon propre envoi me reviendrait en gras dans « Envoyés ».
    await s.execute(perso.ordre_ouvrir(compte.compte_id, comm_id, boite.boite_id, maintenant))
    await _poser_participants(s, comm_id, a.participants)
    await _poser_pieces(s, comm_id, a.pieces, magasin, maintenant)
    await _poser_provenance(s, comm_id, src_id, maintenant)
    from ..modules import evenements
    if not brouillon:
        """Les destinataires de l'ENVELOPPE viennent des participants ANALYSÉS, pas du corps de la
        requête : le `cc` du client n'y était pas, et il n'était donc remis à personne — alors que
        l'en-tête du message l'affichait (RM3214)."""
        vus, enveloppe = set(), []
        for role, _nom, adr, _ordre in a.participants:
            if role in ("to", "cc", "bcc") and adr and adr not in vus: vus.add(adr); enveloppe.append(adr)
        await evenements.emettre_async(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(boite.boite_id), "destinataires": enveloppe})
    await s.commit()
    r = await s.get(Rattachement, (comm_id, boite.boite_id))
    return serialiser(r, c, ds, adresses[boite.boite_id], extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "",
                                                                 "composition": corps.get("composition"), "reference": str(src_id) if src_id else None})
