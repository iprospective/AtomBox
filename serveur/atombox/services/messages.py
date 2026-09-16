"""LE SERVICE DES MESSAGES — ce que le webmail lit (le contrat : les noms de champs.yml, D141),
depuis les modèles (D158), dans la portée du compte (D036 : le rattachement EST la portée).

Les dossiers du webmail : des identifiants courts pour les spéciaux (inbox, sent, drafts, junk,
trash — les alias IMAP protégés, D047), des vues calculées (traites, archives — D051), l'UUID
d'un dossier utilisateur, et les dossiers virtuels personnels (perso:…, D143)."""
from __future__ import annotations
import email.message, email.policy, email.utils, os, re, socket, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, case, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.modeles import Acces, Adresse, Blob, Boite, Comm, CommCitation, CommEmail, CommPieceJointe, Compte, Dossier, Filtre, Participant, PieceJointe, Rattachement
from ..uuid7 import uuid7
from ..journal import journal
from ..sync import sync

log = journal("api")

SPECIAUX = [ {"id": "inbox", "label": "Boîte de réception", "icon": "📥", "alias": ("INBOX",)},
             {"id": "sent", "label": "Envoyés", "icon": "📤", "alias": ("SENT", "SENT ITEMS", "ENVOYÉS", "ENVOYES"), "sortant": True},
             {"id": "drafts", "label": "Brouillons", "icon": "📝", "alias": ("DRAFTS", "BROUILLONS")},
             {"id": "junk", "label": "Indésirables", "icon": "🚫", "alias": ("JUNK", "SPAM", "INDÉSIRABLES")},
             {"id": "trash", "label": "Corbeille", "icon": "🗑", "alias": ("TRASH", "DELETED ITEMS", "CORBEILLE")},
             {"id": "traites", "label": "Traités", "icon": "✓", "vue": True, "alias": ()},
             {"id": "archives", "label": "Archives", "icon": "🗄", "vue": True, "alias": ()} ]
STATUTS = [ {"id": "nouveau", "label": "Nouveau"}, {"id": "a_faire", "label": "À faire"}, {"id": "en_cours", "label": "En cours"},
            {"id": "attente", "label": "En attente"}, {"id": "traite", "label": "Traité"} ]
VUES = ["trash", "archives", "traites"]

def special_de(alias: str | None) -> str | None:
    a = (alias or "").upper().split("/")[-1]
    for s in SPECIAUX:
        if a in s["alias"]: return s["id"]
    return None

def dossier_id_court(d: Dossier | None) -> str | None:
    if d is None: return None
    return special_de(d.alias_imap) or str(d.dossier_id)

def iso(t: datetime | None) -> str | None: return t.astimezone(timezone.utc).isoformat() if t else None

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
             for d in dossiers if not special_de(d.alias_imap) ]
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
    rows = (await s.execute(select(Rattachement.dossier_id, Rattachement.motif_sortie, Rattachement.lu_le.is_(None).label("non_lu"),
                                   Rattachement.statut, func.count().label("n"))
                            .where(_portee(boites)).group_by(Rattachement.dossier_id, Rattachement.motif_sortie, Rattachement.lu_le.is_(None), Rattachement.statut))).all()
    c: dict = {}
    def bump(k, n, non_lu, statut):
        x = c.setdefault(k, {"t": 0, "u": 0, "f": 0}); x["t"] += n
        if non_lu: x["u"] += n
        if statut in ("a_faire", "en_cours"): x["f"] += n
    for dossier_id, motif, non_lu, statut, n in rows:
        d = ds.get(dossier_id); k = dossier_id_court(d) or "inbox"
        if k == "trash": bump("trash", n, non_lu, statut); continue
        if motif == "archive": bump("archives", n, non_lu, statut); continue
        if motif == "traite": bump("traites", n, non_lu, statut); continue
        if motif == "supprime": continue
        bump(k, n, non_lu, statut)
    prefs = compte.preferences or {}
    ref = await referentiels(s, compte)
    c.update(await _compteurs_axes(s, boites, ds))
    c.update(await _compteurs_virtuels(s, boites, ds, compte, ref["virtuels"]))
    return {"compteurs": c, "virtuels": ref["virtuels"], "epingles": prefs.get("epingles", [])}


async def _compteurs_axes(s: AsyncSession, boites, ds: dict) -> dict:
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
    q = (select(Axe.nom, Tag.valeur,
                func.count(func.distinct(Rattachement.comm_id)).label("t"),
                func.count(func.distinct(case((Rattachement.lu_le.is_(None), Rattachement.comm_id)))).label("u"),
                func.count(func.distinct(case((Rattachement.statut.in_(("a_faire", "en_cours")), Rattachement.comm_id)))).label("f"))
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
                 func.count(func.distinct(case((Rattachement.lu_le.is_(None), Rattachement.comm_id)))).label("u"),
                 func.count(func.distinct(case((Rattachement.statut.in_(("a_faire", "en_cours")), Rattachement.comm_id)))).label("f"))
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
        colonnes.append(func.count().filter(and_(ou, Rattachement.lu_le.is_(None))).label("u%d" % len(cles)))
        colonnes.append(func.count().filter(and_(ou, Rattachement.statut.in_(("a_faire", "en_cours")))).label("f%d" % len(cles)))
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
    if dossier == "trash": return Rattachement.dossier_id.in_(par_court.get("trash", [uuid7()]))
    if dossier == "archives": return and_(Rattachement.motif_sortie == "archive", Rattachement.dossier_id.notin_(par_court.get("trash", [])))
    if dossier == "traites": return and_(Rattachement.motif_sortie == "traite", Rattachement.dossier_id.notin_(par_court.get("trash", [])))
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
        if statut and statut != "tous": q = q.where(Rattachement.statut == statut)
        # « tous » : rien n'est exclu — c'est le défaut d'une branche de CLASSEMENT (D166). La
        # règle « traité sort de la file » (D014/D030) vaut pour une file de travail ; appliquée
        # à un tag, elle fait disparaître un projet entier dès qu'il est terminé.
        if not est_vue and filtre != "tous":
            q = q.where(Rattachement.motif_sortie.isnot(None)) if filtre == "sortis" else q.where(Rattachement.motif_sortie.is_(None))
        if filtre == "non_lus": q = q.where(Rattachement.lu_le.is_(None))
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
    return [serialiser(r, c, ds, adresses.get(r.boite_id), extra={"tags": tags.get(c.comm_id, [])})
            for r, c in lignes]

def serialiser(r: Rattachement, c: Comm, ds: dict, boite_adresse: str | None, complet: bool = False, extra: dict | None = None) -> dict:
    origine = dossier_id_court(ds.get(r.dossier_origine_id)) if r.dossier_origine_id else dossier_id_court(ds.get(r.dossier_id))
    courant = dossier_id_court(ds.get(r.dossier_id))
    o = { "id": str(c.comm_id), "sujet": c.sujet, "from_nom": c.from_nom, "from_adresse": c.from_adresse,
          "date_recue": iso(c.date_recue), "thread_id": str(c.thread_id) if c.thread_id else None,
          "nb_pieces_jointes": c.nb_pieces_jointes, "taille": c.taille, "sens": c.sens, "nature": c.nature, "snippet": c.snippet,
          "boite": boite_adresse, "lu": r.lu_le is not None, "statut": r.statut, "sorti_le": iso(r.sorti_le), "motif_sortie": r.motif_sortie,
          "dossier_origine": origine or "inbox", "dossier": courant if courant != origine else None,
          "tags": [], "connu": False, "usurpation": False, "valide": False, "suppr": r.motif_sortie == "supprime",
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
    return serialiser(r, c, ds, adresse, True, {
        "tags": (await tags_de(s, [comm_id])).get(comm_id, []), "reference": ref,
        "destinataires": list(dest) + list(copies), "composition": _composition(r, c, ds, adresse, dest, copies, corps, ref),
        "corps": corps, "reponse_possible": e.reponse_possible if e else None, "list_id": e.list_id if e else None,
        "pieces_jointes": [ {"pj_id": str(p.piece_jointe_id), "ordre": l.ordre, "nom": l.nom_declare or ("piece-%d" % l.ordre), "octets": p.taille_octets,
                             "mime_declare": l.type_declare, "mime_detecte": p.type_detecte, "sha256": p.blob_ref, "partage_par": p.nb_references,
                             "content_id": l.content_id, "disposition": l.disposition} for l, p in pjs ] })

async def fil(s: AsyncSession, compte: Compte, comm_id) -> list[dict]:
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    c = await s.get(Comm, comm_id)
    if not c: return []
    ds = await _dossiers_par_id(s, boites)
    q = select(Rattachement, Comm).join(Comm, Comm.comm_id == Rattachement.comm_id).where(_portee(boites), Comm.thread_id == (c.thread_id or c.comm_id)).order_by(Comm.date_recue.asc())
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    vus, out = set(), []
    for r, cc in (await s.execute(q)).all():
        if cc.comm_id in vus: continue
        vus.add(cc.comm_id); out.append(serialiser(r, cc, ds, adresses.get(r.boite_id)))
    return out

async def patcher(s: AsyncSession, compte: Compte, comm_id, patch: dict) -> dict | None:
    """le rattachement du compte (D036) : lu, statut, sortie, dossier, drapeau — jamais le message"""
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, _portee(boites)).limit(1))
    if not r: return None
    ds = await _dossiers_par_id(s, boites)
    n = 0; dossier_avant = r.dossier_id
    for k, v in (patch or {}).items():
        if k == "lu": r.lu_le = datetime.now(timezone.utc) if v else None; n += 1
        elif k == "statut" and v in [x["id"] for x in STATUTS]: r.statut = v; n += 1
        elif k == "motif_sortie": r.motif_sortie = v; n += 1
        elif k == "sorti_le": r.sorti_le = quand(v); n += 1
        elif k == "drapeau": r.drapeau = bool(v); n += 1
        elif k == "personnel": r.personnel = bool(v); n += 1
        elif k == "dossier":
            if r.dossier_origine_id is None: r.dossier_origine_id = r.dossier_id
            if v is None: r.dossier_id = r.dossier_origine_id
            else:
                cible = next((d for d in ds.values() if d.boite_id == r.boite_id and dossier_id_court(d) == v), None)
                if cible is None: log.warning("PATCH %s : dossier inconnu %r", comm_id, v); continue
                r.dossier_id = cible.dossier_id
            n += 1
        elif k == "suppr" and v:
            r.motif_sortie = "supprime"; r.sorti_le = datetime.now(timezone.utc); r.supprime_par = compte.compte_id
            r.restaurable_jusqu_au = datetime.now(timezone.utc) + timedelta(days=30); n += 1
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
    return {"modifies": n, "message": serialiser(r, c, ds, adresse)}

async def detacher(s: AsyncSession, compte: Compte, comm_id) -> bool:
    r = await patcher(s, compte, comm_id, {"suppr": True})
    return r is not None

def hote_atombox() -> str:
    """le nom de CETTE instance dans la chaîne de relais — jamais deviné à partir d'une requête"""
    return os.environ.get("ATOMBOX_HOTE") or socket.getfqdn() or "atombox"

def entetes_de_relais(m: email.message.EmailMessage, comm_id, expediteur: str, quand: datetime, ip_client: str | None = None) -> None:
    """AtomBox n'est pas un client SMTP : il REÇOIT par son API et REMET au relais. Le Received le
    dit (RFC 5321 § 4.4), avec l'identifiant qui corrèle journal, envoi et DSN (D119).

    L'IP du client n'y est JAMAIS écrite (D162) : un en-tête sortant part chez tous les
    destinataires et géolocalise l'expéditeur à chaque message ; l'IP vit au journal, chez nous.
    Le paramètre existe pour un client qui l'exigerait — verrouillable, désactivé par défaut."""
    trace = ""
    if ip_client and os.environ.get("ATOMBOX_TRACER_IP_CLIENT") == "1":
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
    m.set_content(corps.get("corps") or "")
    """Le message transféré est ENCAPSULÉ, pas recopié dans le corps (D066/D167) : le commentaire
    reste dissocié, l'index ne voit que lui (D163), et l'octet du source part intact. Aucun en-tête
    ne porte le lien — la provenance vit en base, jamais dans le message (D067) : un marqueur
    partirait chez le destinataire et ne s'indexerait pas."""
    if source:
        src = email.message_from_bytes(source, policy=email.policy.SMTP)
        m.add_attachment(src, filename=(_nom_de_fichier(src["Subject"]) + ".eml"))
    entetes_de_relais(m, comm_id, adresse, quand, ip_client)   # D162
    return m.as_bytes()

async def _poser_participants(s: AsyncSession, comm_id, participants) -> None:
    """Les destinataires sont une DONNÉE du message, pas un écho de la requête : sans eux,
    un message envoyé se relit sans destinataire (et un brouillon sans personne à qui écrire)."""
    for p in await s.scalars(select(Participant).where(Participant.comm_id == comm_id)):
        await s.delete(p)
    await s.flush()
    for role, nom, adr, ordre in participants:
        s.add(Participant(comm_id=comm_id, role=role, adresse_id=(await _adresse(s, adr)).adresse_id, nom_affiche=nom, ordre=ordre))


async def remplacer_brouillon(s: AsyncSession, compte: Compte, comm_id, corps: dict, magasin=None) -> dict | None:
    """Un brouillon réenregistré GARDE son identité (D089 : un brouillon est un message marqué).
    Le webmail supprimait puis recréait : le message changeait d'identifiant à chaque frappe
    enregistrée, et l'onglet ouvert pointait sur un mort."""
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
    await s.commit()
    log.info("brouillon %s réenregistré par %s", comm_id, compte.login)
    return serialiser(r, c, ds, adresse, extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "",
                                                "composition": corps.get("composition"), "reference": str(src_id) if src_id else None})

async def _adresse(s: AsyncSession, complete: str):
    """l'adresse, créée au besoin — version asynchrone de celle de l'ingestion"""
    from ..schema.modeles import Domaine
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
    s.add(Rattachement(comm_id=comm_id, boite_id=boite.boite_id, compte_id=compte.compte_id, lu_le=maintenant, drapeau=False, statut="nouveau", personnel=False, gele=False,
                       dossier_id=cible.dossier_id if cible else None))
    await s.flush()
    await _poser_participants(s, comm_id, a.participants)
    await _poser_pieces(s, comm_id, a.pieces, magasin, maintenant)
    await _poser_provenance(s, comm_id, src_id, maintenant)
    from ..modules import evenements
    if not brouillon:
        await evenements.emettre_async(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(boite.boite_id), "destinataires": corps.get("destinataires") or []})
    await s.commit()
    r = await s.get(Rattachement, (comm_id, boite.boite_id))
    return serialiser(r, c, ds, adresses[boite.boite_id], extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "",
                                                                 "composition": corps.get("composition"), "reference": str(src_id) if src_id else None})
