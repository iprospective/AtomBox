"""LE SERVICE DES MESSAGES — ce que le webmail lit (le contrat : les noms de champs.yml, D141),
depuis les modèles (D158), dans la portée du compte (D036 : le rattachement EST la portée).

Les dossiers du webmail : des identifiants courts pour les spéciaux (inbox, sent, drafts, junk,
trash — les alias IMAP protégés, D047), des vues calculées (traites, archives — D051), l'UUID
d'un dossier utilisateur, et les dossiers virtuels personnels (perso:…, D143)."""
from __future__ import annotations
import email.message, email.policy, email.utils, os, socket
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, case, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..schema.modeles import Acces, Adresse, Boite, Comm, CommEmail, CommPieceJointe, Compte, Dossier, Filtre, Participant, PieceJointe, Rattachement
from ..uuid7 import uuid7
from ..journal import journal

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

async def referentiels(s: AsyncSession, compte: Compte) -> dict:
    boites = await boites_du_compte(s, compte)
    adresses = {b.boite_id: (await s.get(Adresse, b.adresse_id)).adresse_complete for b in boites}
    dossiers = list(await s.scalars(select(Dossier).where(Dossier.boite_id.in_([b.boite_id for b in boites])).order_by(Dossier.ordre, Dossier.nom)))
    util = [ {"id": str(d.dossier_id), "label": d.nom, "icon": "📁", "boite": adresses.get(d.boite_id)}
             for d in dossiers if not special_de(d.alias_imap) ]
    virtuels = list(await s.scalars(select(Filtre).where(Filtre.portee_type == "compte", Filtre.portee_id == compte.compte_id, Filtre.action.is_(None), Filtre.actif.is_(True)).order_by(Filtre.ordre)))
    return { "moi": {"nom": compte.nom, "login": compte.login, "boites": [{"id": str(b.boite_id), "adresse": adresses[b.boite_id], "label": adresses[b.boite_id].split("@")[0]} for b in boites]},
             "speciaux": [{"id": x["id"], "label": x["label"], "icon": x["icon"], **({"vue": True} if x.get("vue") else {}), **({"sortant": True} if x.get("sortant") else {})} for x in SPECIAUX],
             "util": util, "axes": [], "valeurs": {}, "statuts": STATUTS, "vues": VUES,
             "virtuels": [{"id": "perso:" + str(f.filtre_id), "label": f.nom, "criteres": (f.predicat or {}).get("criteres", [])} for f in virtuels] }

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
    return {"compteurs": c, "virtuels": ref["virtuels"], "epingles": prefs.get("epingles", [])}

def _condition_dossier(dossier: str, kind: str | None, ds: dict, compte):
    """la condition SQL d'un dossier du webmail"""
    par_court = {}
    for d in ds.values(): par_court.setdefault(dossier_id_court(d), []).append(d.dossier_id)
    if dossier == "trash": return Rattachement.dossier_id.in_(par_court.get("trash", [uuid7()]))
    if dossier == "archives": return and_(Rattachement.motif_sortie == "archive", Rattachement.dossier_id.notin_(par_court.get("trash", [])))
    if dossier == "traites": return and_(Rattachement.motif_sortie == "traite", Rattachement.dossier_id.notin_(par_court.get("trash", [])))
    if dossier in par_court: return Rattachement.dossier_id.in_(par_court[dossier])
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
        q = q.where(and_(*conds)) if conds else q.where(Comm.comm_id.is_(None))
        q = q.where(Rattachement.dossier_id.notin_([d.dossier_id for d in ds.values() if dossier_id_court(d) == "trash"]))
    else:
        q = q.where(_condition_dossier(dossier, kind, ds, compte))
    est_vue = dossier in VUES
    if not tout:
        if sens in ("in", "out"): q = q.where(Comm.sens == sens)
        if statut and statut != "tous": q = q.where(Rattachement.statut == statut)
        if not est_vue: q = q.where(Rattachement.motif_sortie.isnot(None)) if filtre == "sortis" else q.where(Rattachement.motif_sortie.is_(None))
        if filtre == "non_lus": q = q.where(Rattachement.lu_le.is_(None))
        if filtre == "recents": q = q.where(Comm.date_recue >= datetime.now(timezone.utc) - timedelta(days=30))
        if filtre == "pj": q = q.where(Comm.nb_pieces_jointes > 0)
        if filtre == "lourds": q = q.where(Comm.taille > 2048 * 1024)
    q = q.order_by(TRIS.get(tri or "date_desc", TRIS["date_desc"])).limit(500)
    adresses = {b: (await s.get(Adresse, (await s.get(Boite, b)).adresse_id)).adresse_complete for b in boites}
    return [serialiser(r, c, ds, adresses.get(r.boite_id)) for r, c in (await s.execute(q)).all()]

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

async def detail(s: AsyncSession, compte: Compte, comm_id, magasin=None) -> dict | None:
    boites = [b.boite_id for b in await boites_du_compte(s, compte)]
    r = await s.scalar(select(Rattachement).where(Rattachement.comm_id == comm_id, _portee(boites)).limit(1))
    if not r: return None
    c = await s.get(Comm, comm_id); e = await s.get(CommEmail, comm_id); ds = await _dossiers_par_id(s, boites)
    boite = await s.get(Boite, r.boite_id); adresse = (await s.get(Adresse, boite.adresse_id)).adresse_complete
    dest = (await s.execute(select(Adresse.adresse_complete).join(Participant, Participant.adresse_id == Adresse.adresse_id)
                            .where(Participant.comm_id == comm_id, Participant.role.in_(("to", "cc"))).order_by(Participant.ordre))).scalars().all()
    pjs = (await s.execute(select(CommPieceJointe, PieceJointe).join(PieceJointe, PieceJointe.piece_jointe_id == CommPieceJointe.piece_jointe_id)
                           .where(CommPieceJointe.comm_id == comm_id).order_by(CommPieceJointe.ordre))).all()
    corps = ""
    if magasin is not None and magasin.existe(str(comm_id)):
        try:
            from ..ingestion.analyse import analyser
            corps = analyser(magasin.lire(str(comm_id))).corps_texte
        except Exception as ex: log.warning("corps de %s illisible : %s", comm_id, ex)
    return serialiser(r, c, ds, adresse, True, {
        "destinataires": list(dest), "corps": corps, "reponse_possible": e.reponse_possible if e else None, "list_id": e.list_id if e else None,
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
    n = 0
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
    m = email.message.EmailMessage(policy=email.policy.SMTP)
    m["From"] = "%s <%s>" % (compte.nom, adresses[boite.boite_id]); m["To"] = ", ".join(corps.get("destinataires") or [])
    m["Subject"] = corps.get("sujet") or "(sans sujet)"; m["Date"] = email.utils.formatdate(localtime=True)
    m["Message-ID"] = email.utils.make_msgid(domain=adresses[boite.boite_id].split("@")[-1])
    if corps.get("reference"): m["X-AtomBox-Reference"] = str(corps["reference"])
    m.set_content(corps.get("corps") or "")
    comm_id = uuid7(); maintenant = datetime.now(timezone.utc)
    entetes_de_relais(m, comm_id, adresses[boite.boite_id], maintenant, ip_client)   # D162
    octets = m.as_bytes()
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
             taille=len(octets), nb_pieces_jointes=0, est_chiffre=False, est_signe=False, snippet=a.snippet, corps_texte=a.corps_texte or None)
    s.add(c)
    s.add(CommEmail(comm_id=comm_id, message_id=a.message_id, headers=a.headers, blob_ref=brut, empreinte=empreinte_identite(a), structure_mime=a.structure_mime, reponse_possible="oui"))
    s.add(Rattachement(comm_id=comm_id, boite_id=boite.boite_id, compte_id=compte.compte_id, lu_le=maintenant, drapeau=False, statut="nouveau", personnel=False, gele=False,
                       dossier_id=cible.dossier_id if cible else None))
    await s.flush()
    from ..modules import evenements
    if not brouillon:
        evenements.emettre(s, "message.a_envoyer", {"comm_id": str(comm_id), "boite_id": str(boite.boite_id), "destinataires": corps.get("destinataires") or []})
    await s.commit()
    r = await s.get(Rattachement, (comm_id, boite.boite_id))
    return serialiser(r, c, ds, adresses[boite.boite_id], extra={"destinataires": corps.get("destinataires") or [], "corps": corps.get("corps") or "", "composition": corps.get("composition")})
