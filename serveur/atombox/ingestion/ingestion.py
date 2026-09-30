"""L'INGESTION d'un message dans la base et le magasin (F001, F002 — D158 : par l'ORM).

Une transaction par message. Le message brut va au magasin sous l'UUID de sa comm (D145) ;
les pièces jointes y vont sous leur empreinte, dédupliquées (D011) ; l'identité (D064) décide
si la comm existe déjà — alors on n'ajoute qu'un rattachement (D010 : un exemplaire, N boîtes).
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..uuid7 import uuid7
from ..magasin import Magasin
from ..schema.modeles import Adresse, Blob, Comm, CommEmail, CommPieceJointe, Domaine, Dossier, Participant, PieceJointe, Rattachement
from .analyse import analyser
from .identite import empreinte_identite
from ..journal import journal
from ..modules.accroches import accroches
from ..modules import evenements
from ..filtres import appliquer as appliquer_filtres, filtres_de

log = journal("ingestion")

def domaine(s: Session, nom: str) -> Domaine:
    nom_ascii = nom.lower()
    try: nom_ascii = nom.encode("idna").decode()
    except Exception: pass
    d = s.scalar(select(Domaine).where(Domaine.nom_ascii == nom_ascii))
    if d: return d
    d = Domaine(domaine_id=uuid7(), nom_ascii=nom_ascii, nom_unicode=nom, heberge_par_nous=False)
    s.add(d); s.flush()
    return d

def normaliser_adresse(brut: str) -> str:
    """« Florian HENRY <florian.henry@scopen.fr> » → « florian.henry@scopen.fr ».

    Une adresse vient TOUJOURS de l'extérieur — d'un en-tête reçu ou d'un champ de saisie — donc
    on ne la croit pas sur parole. Sans ce passage, une adresse entière avec son nom d'affichage
    est entrée en base (`local = "Florian HENRY <florian.henry"`) : smtplib parsait à la remise, le
    courrier partait, et le suivi d'envoi pointait une adresse qui n'existe pas."""
    import email.utils
    _, adr = email.utils.parseaddr((brut or "").strip())
    adr = (adr or "").strip().strip("<>")
    return adr if "@" in adr else ""      # `parseaddr` rend volontiers du texte quelconque


def adresse(s: Session, complete: str) -> Adresse:
    complete = normaliser_adresse(complete) or (complete or "").strip().strip("<>")
    a = s.scalar(select(Adresse).where(Adresse.adresse_complete == complete))
    if a: return a
    local, _, dom = complete.partition("@")
    a = Adresse(adresse_id=uuid7(), local=local, local_cmp=local.lower(), domaine_id=domaine(s, dom or "invalide").domaine_id, adresse_complete=complete)
    s.add(a); s.flush()
    return a

def blob(s: Session, magasin: Magasin, octets: bytes) -> Blob:
    e, info = magasin.deposer(octets)
    b = s.get(Blob, e)
    if b: b.nb_references += 1; return b
    b = Blob(empreinte=e, taille_octets=info["taille_octets"], taille_stockee=info["taille_stockee"], compression=info["compression"],
             cree_le=datetime.now(timezone.utc), nb_references=1)
    s.add(b); s.flush()
    return b

def ingerer(s: Session, magasin: Magasin, boite_id, octets: bytes, *, uid=None, uid_validity=None, dossier_id=None,
            date_recue: datetime | None = None, sens: str = "in", dossier_alias: str | None = None) -> dict:
    a = analyser(octets)
    ctx = accroches.emettre("message.avant_ingestion", analyse=a, boite_id=boite_id, octets=octets, tags=[])
    if ctx.get("ignorer"):
        log.info("ignoré par un module : %s (%s)", a.message_id, ctx.get("raison", "sans raison")); return {"comm_id": None, "nouveau": False, "ignore": True, "identite": None, "nature": a.nature, "pieces": len(a.pieces)}
    identite = empreinte_identite(a)
    existant = s.scalar(select(CommEmail).where(CommEmail.empreinte == identite))
    if existant:
        comm_id, nouveau = existant.comm_id, False
        log.debug("déjà connu %s (%s) → rattachement à %s", comm_id, a.message_id, boite_id)
    else:
        nouveau = True; comm_id = uuid7()
        # le fil (D055) : par In-Reply-To / References vers une comm connue, sinon soi-même
        thread_id = comm_id
        refs = ([a.in_reply_to] if a.in_reply_to else []) + list(reversed(a.references))
        if refs:
            parent = s.scalar(select(Comm).join(CommEmail, CommEmail.comm_id == Comm.comm_id).where(CommEmail.message_id.in_(refs)).limit(1))
            if parent and parent.thread_id: thread_id = parent.thread_id
        magasin.ecrire(str(comm_id), octets)               # le message brut, sous l'UUID de la comm (D145)
        brut = blob(s, magasin, octets)                    # et son blob, pour la reconstruction à l'octet (D025)
        s.add(Comm(comm_id=comm_id, type="email", date_recue=date_recue or a.date_declaree or datetime.now(timezone.utc),
                   date_declaree=a.date_declaree, date_ingestion=datetime.now(timezone.utc), sens=sens, sujet=a.sujet,
                   sujet_normalise=a.sujet_normalise, thread_id=thread_id, nature=a.nature, from_adresse=a.from_adresse,
                   from_nom=a.from_nom, taille=a.taille, nb_pieces_jointes=len(a.pieces), langue=None,
                   est_chiffre=a.est_chiffre, est_signe=a.est_signe, snippet=a.snippet, corps_texte=(a.corps_texte or "")[:200000] or None))
        s.add(CommEmail(comm_id=comm_id, message_id=a.message_id, in_reply_to=a.in_reply_to, references=" ".join(a.references) or None,
                        return_path=a.return_path, list_id=a.list_id, list_unsubscribe=a.list_unsubscribe, headers=a.headers,
                        blob_ref=brut.empreinte, empreinte=identite, structure_mime=a.structure_mime, uid=uid, uid_validity=uid_validity,
                        reponse_possible=a.reponse_possible))
        for role, nom, adr, ordre in a.participants:
            s.add(Participant(comm_id=comm_id, role=role, adresse_id=adresse(s, adr).adresse_id, nom_affiche=nom, ordre=ordre))
        for p in a.pieces:
            b = blob(s, magasin, p.octets)
            pj = s.scalar(select(PieceJointe).where(PieceJointe.blob_ref == b.empreinte, PieceJointe.type_detecte == p.type_detecte))
            if pj: pj.nb_references += 1
            else:
                pj = PieceJointe(piece_jointe_id=uuid7(), blob_ref=b.empreinte, type_detecte=p.type_detecte, taille_octets=len(p.octets), nb_references=1)
                s.add(pj); s.flush()
            s.add(CommPieceJointe(comm_id=comm_id, piece_jointe_id=pj.piece_jointe_id, ordre=p.ordre, nom_declare=p.nom_declare,
                                  type_declare=p.type_declare, transfer_encoding=p.transfer_encoding, disposition=p.disposition,
                                  content_id=p.content_id, parametres=p.parametres))
        s.flush()
        evenements.emettre(s, "message.ingere", {"comm_id": str(comm_id), "boite_id": str(boite_id), "nature": a.nature, "sujet": a.sujet}, cible=None)
    r = s.get(Rattachement, (comm_id, boite_id))
    if r is None:
        # LE MOTEUR DE FILTRES (F016, D074) : il décide du dossier et de l'état d'arrivée. Il ne
        # tourne qu'à la PREMIÈRE arrivée dans une boîte : rejouer les règles sur un message déjà
        # rattaché défferait ce que l'utilisateur a fait depuis.
        regles = appliquer_filtres(s, filtres_de(s, boite_id), a, {"dossier": dossier_alias or ""})
        if regles["ignorer"]:
            log.info("ignoré par une règle (%s) : %s", ", ".join(regles["regles"]), a.message_id)
            s.commit(); return {"comm_id": comm_id, "nouveau": nouveau, "ignore": True, "identite": identite, "nature": a.nature, "pieces": len(a.pieces)}
        p = regles["patch"]
        cible = dossier_id
        if regles["dossier"]:
            d2 = s.scalar(select(Dossier).where(Dossier.boite_id == boite_id, Dossier.alias_imap == regles["dossier"]))
            if d2 is not None: cible = d2.dossier_id
            else: log.warning("règle « %s » : dossier %r inconnu dans cette boîte", ", ".join(regles["regles"]), regles["dossier"])
        from ..uid_servi import attribuer as attribuer_uid
        s.add(Rattachement(comm_id=comm_id, boite_id=boite_id, uid_servi=attribuer_uid(s, cible),
                           status=p.get("statut", "new"), personnel=False, gele=False,
                           dossier_id=cible, uid_imap=uid))
        # CE QU'UNE RÈGLE POSE COMME ÉTAT PERSONNEL (lu, drapeau) VA SUR UNE PERSONNE, pas sur le
        # rattachement (D175). À l'arrivée, la seule personne qu'on connaisse est celle qui relève —
        # et s'ils sont plusieurs sur la boîte, la règle ne marque personne : « lu » voudrait dire
        # « lu par tous », ce qui est faux, et écrase la seule information qu'on aurait pu garder.
        from ..services import personal_state as perso
        releveur = perso.polling_account(s, boite_id) if (p.get("lu") or p.get("drapeau")) else None
        if releveur is not None:
            s.flush()
            if p.get("lu"): s.execute(perso.open_stmt(releveur, comm_id, boite_id))
            if p.get("drapeau"): s.execute(perso.flag_stmt(releveur, comm_id, boite_id, True))
        elif p.get("lu") or p.get("drapeau"):
            log.info("règle avec lu/drapeau sur une boîte à plusieurs membres : état personnel non imputé (D175)")
        # CE QU'UNE RÈGLE POSE DOIT PARTIR VERS IMAP (RM3188). Sans cet ordre, la synchronisation
        # descendante — qui tourne dans la MÊME relève — lisait un IMAP sans \Flagged ni \Seen, et
        # « IMAP fait foi » défaisait la règle 50 ms après qu'elle eut agi. Tant que l'ordre est en
        # vol, la descendante l'épargne : c'est la garde qu'elle a déjà. Un classement suit le même
        # chemin, et le message est DÉPLACÉ côté IMAP — sinon Thunderbird ne voyait rien du tri.
        if uid is not None and (p.get("lu") or p.get("drapeau") or cible != dossier_id):
            s.flush()
            evenements.emettre(s, "rattachement.change", {"comm_id": str(comm_id), "boite_id": str(boite_id),
                               "dossier_avant": str(dossier_id) if cible != dossier_id else None}, cible=None)
    elif r.uid_imap is None and uid is not None:
        r.uid_imap = uid
    s.commit()
    if nouveau: log.info("nouveau %s : %s, de %s, %d octets, %d pièce(s), nature %s", comm_id, a.sujet or "(sans sujet)", a.from_adresse, a.taille, len(a.pieces), a.nature)
    accroches.emettre("message.ingere", comm_id=comm_id, nouveau=nouveau, analyse=a, boite_id=boite_id, tags=ctx.get("tags", []))
    return {"comm_id": comm_id, "nouveau": nouveau, "identite": identite, "nature": a.nature, "pieces": len(a.pieces)}
