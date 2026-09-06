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
from ..schema.modeles import Adresse, Blob, Comm, CommEmail, CommPieceJointe, Domaine, Participant, PieceJointe, Rattachement
from .analyse import analyser
from .identite import empreinte_identite
from ..journal import journal
from ..modules.accroches import accroches

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

def adresse(s: Session, complete: str) -> Adresse:
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
            date_recue: datetime | None = None, sens: str = "in") -> dict:
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
                   est_chiffre=a.est_chiffre, est_signe=a.est_signe, snippet=a.snippet))
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
    if not s.get(Rattachement, (comm_id, boite_id)):
        s.add(Rattachement(comm_id=comm_id, boite_id=boite_id, drapeau=False, statut="nouveau", personnel=False, gele=False, dossier_id=dossier_id))
    s.commit()
    if nouveau: log.info("nouveau %s : %s, de %s, %d octets, %d pièce(s), nature %s", comm_id, a.sujet or "(sans sujet)", a.from_adresse, a.taille, len(a.pieces), a.nature)
    accroches.emettre("message.ingere", comm_id=comm_id, nouveau=nouveau, analyse=a, boite_id=boite_id, tags=ctx.get("tags", []))
    return {"comm_id": comm_id, "nouveau": nouveau, "identite": identite, "nature": a.nature, "pieces": len(a.pieces)}
