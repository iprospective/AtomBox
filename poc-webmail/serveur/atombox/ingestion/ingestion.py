"""L'INGESTION d'un message dans la base et le magasin (F001, F002).

Une transaction par message. Le message brut va au magasin sous l'UUID de sa comm (D145) ;
les pièces jointes y vont sous leur empreinte, dédupliquées (D011) ; l'identité (D064) décide
si la comm existe déjà — alors on n'ajoute qu'un rattachement (D010 : un exemplaire, N boîtes).
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from ..uuid7 import uuid7
from ..magasin import Magasin, empreinte
from .analyse import analyser
from .identite import empreinte_identite

def _domaine_id(cur, nom: str):
    nom_ascii = nom.lower()
    try: nom_ascii = nom.encode("idna").decode()
    except Exception: pass
    r = cur.execute('select domaine_id from domaine where nom_ascii=%s', (nom_ascii,)).fetchone()
    if r: return r["domaine_id"]
    did = uuid7()
    cur.execute('insert into domaine (domaine_id, nom_ascii, nom_unicode, heberge_par_nous) values (%s,%s,%s,false)', (did, nom_ascii, nom))
    return did

def _adresse_id(cur, adresse: str):
    r = cur.execute('select adresse_id from adresse where adresse_complete=%s', (adresse,)).fetchone()
    if r: return r["adresse_id"]
    local, _, dom = adresse.partition("@")
    aid = uuid7()
    cur.execute('insert into adresse (adresse_id, local, local_cmp, domaine_id, adresse_complete) values (%s,%s,%s,%s,%s)',
                (aid, local, local.lower(), _domaine_id(cur, dom or "invalide"), adresse))
    return aid

def _blob(cur, magasin: Magasin, octets: bytes) -> str:
    e, info = magasin.deposer(octets)
    cur.execute('''insert into blob (empreinte, taille_octets, taille_stockee, compression, cree_le, nb_references)
                   values (%s,%s,%s,%s,now(),1) on conflict (empreinte) do update set nb_references = blob.nb_references + 1''',
                (e, info["taille_octets"], info["taille_stockee"], info["compression"]))
    return e

def ingerer(cnx, magasin: Magasin, boite_id, octets: bytes, *, uid=None, uid_validity=None, dossier_id=None,
            date_recue: datetime | None = None, sens: str = "in") -> dict:
    a = analyser(octets)
    identite = empreinte_identite(a)
    with cnx.transaction():
        cur = cnx.cursor()
        r = cur.execute('select comm_id from comm_email where empreinte=%s', (identite,)).fetchone()
        if r:
            comm_id = r["comm_id"]; nouveau = False
        else:
            nouveau = True; comm_id = uuid7()
            # le fil (D055) : par In-Reply-To / References vers une comm connue, sinon soi-même
            thread_id = comm_id
            refs = ([a.in_reply_to] if a.in_reply_to else []) + list(reversed(a.references))
            if refs:
                t = cur.execute('select c.thread_id from comm_email e join comm c using (comm_id) where e.message_id = any(%s) limit 1', (refs,)).fetchone()
                if t and t["thread_id"]: thread_id = t["thread_id"]
            magasin.ecrire(str(comm_id), octets)            # le message brut, sous l'UUID de la comm (D145)
            brut = _blob(cur, magasin, octets)              # et son blob, pour la reconstruction à l'octet (D025)
            cur.execute('''insert into comm (comm_id, type, date_recue, date_declaree, date_ingestion, sens, sujet, sujet_normalise, thread_id,
                             nature, from_adresse, from_nom, taille, nb_pieces_jointes, langue, est_chiffre, est_signe, snippet)
                           values (%s,'email',%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s)''',
                        (comm_id, date_recue or a.date_declaree or datetime.now(timezone.utc), a.date_declaree, sens, a.sujet, a.sujet_normalise,
                         thread_id, a.nature, a.from_adresse, a.from_nom, a.taille, len(a.pieces), a.est_chiffre, a.est_signe, a.snippet))
            cur.execute('''insert into comm_email (comm_id, message_id, in_reply_to, "references", return_path, list_id, list_unsubscribe, headers,
                             blob_ref, empreinte, structure_mime, uid, uid_validity, reponse_possible)
                           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                        (comm_id, a.message_id, a.in_reply_to, " ".join(a.references) or None, a.return_path, a.list_id, a.list_unsubscribe,
                         a.headers, brut, identite, json.dumps(a.structure_mime), uid, uid_validity, a.reponse_possible))
            for role, nom, adr, ordre in a.participants:
                cur.execute('insert into participant (comm_id, role, adresse_id, nom_affiche, ordre) values (%s,%s,%s,%s,%s) on conflict do nothing',
                            (comm_id, role, _adresse_id(cur, adr), nom, ordre))
            for p in a.pieces:
                e = _blob(cur, magasin, p.octets)
                pj = cur.execute('select piece_jointe_id from piece_jointe where blob_ref=%s and type_detecte=%s', (e, p.type_detecte)).fetchone()
                if pj: pj_id = pj["piece_jointe_id"]; cur.execute('update piece_jointe set nb_references = nb_references + 1 where piece_jointe_id=%s', (pj_id,))
                else:
                    pj_id = uuid7()
                    cur.execute('insert into piece_jointe (piece_jointe_id, blob_ref, type_detecte, taille_octets, nb_references) values (%s,%s,%s,%s,1)',
                                (pj_id, e, p.type_detecte, len(p.octets)))
                cur.execute('''insert into comm_piece_jointe (comm_id, piece_jointe_id, ordre, nom_declare, type_declare, transfer_encoding, disposition, content_id, parametres)
                               values (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                            (comm_id, pj_id, p.ordre, p.nom_declare, p.type_declare, p.transfer_encoding, p.disposition, p.content_id, json.dumps(p.parametres)))
        cur.execute('''insert into rattachement (comm_id, boite_id, drapeau, statut, personnel, gele, dossier_id)
                       values (%s,%s,false,'nouveau',false,false,%s) on conflict (comm_id, boite_id) do nothing''', (comm_id, boite_id, dossier_id))
    return {"comm_id": comm_id, "nouveau": nouveau, "identite": identite, "nature": a.nature, "pieces": len(a.pieces)}
