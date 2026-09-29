"""D175 — l'état d'un message sur TROIS PLANS, éprouvé par l'API, de bout en bout.

Deux garanties, et ce sont exactement les deux que le modèle d'hier ne pouvait pas tenir :

  1. **« à revoir » n'efface pas l'ouverture.** C'était LE défaut : « marquer comme non lu »
     détruisait la seule trace que quelqu'un avait regardé le message. Sur une boîte partagée,
     cette trace est l'information la plus utile qu'on ait.

  2. **« traité PUIS archivé » se relit.** L'état courant est unique et exclusif, mais un message
     est généralement traité, puis archivé des années après. Si l'archivage écrasait la date de
     traitement, on perdrait la clé d'archivage (D014) — la donnée qui commande la transition
     suivante. Deux endroits en répondent : les dates sur le rattachement, et le journal (D054)
     pour le chemin parcouru.

CONTRE-ÉPREUVE. Chacun de ces tests a été vérifié en réintroduisant le défaut : remettre
`opened_at = NULL` sur un `lu: false`, ou faire écrire `processed_at` par l'archivage, les fait
rougir. Un test qui ne rougit pas sur le défaut qu'il prétend garder ne garde rien.
"""
import os, re, uuid
from datetime import datetime, timezone
import pytest


@pytest.fixture
def monde(tmp_path):
    """une base jetable, un compte, une boîte à UN membre, un message dedans"""
    if not os.environ.get("DATABASE_URL"): pytest.skip("DATABASE_URL absent")
    import psycopg
    from atombox.db import session as ouvrir
    from atombox.api.securite import hacher_mot_de_passe
    from atombox.ingestion.ingestion import adresse as adresse_de
    from atombox.magasin import Magasin
    from atombox.schema.modeles import Acces, Boite, Comm, Compte, Dossier, Rattachement
    from atombox.schema.semences import semer
    from atombox.uuid7 import uuid7

    nom = "atombox_plans_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", os.environ["DATABASE_URL"], count=1)
    ici = os.path.dirname(os.path.abspath(__file__))
    with psycopg.connect(u) as c:
        c.execute(open(os.path.join(ici, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    avant = {k: os.environ.get(k) for k in ("DATABASE_URL", "ATOMBOX_STORE", "ATOMBOX_IMAP_HOST", "ATOMBOX_IMAP_HOTE")}
    os.environ["DATABASE_URL"] = u
    os.environ["ATOMBOX_STORE"] = str(tmp_path / "magasin")
    # Le harnais ne parle PAS à un vrai serveur IMAP : la création de dossier y enverrait un ordre,
    # et le test dépendrait d'une machine tierce pour éprouver une règle de notre modèle.
    for k in ("ATOMBOX_IMAP_HOST", "ATOMBOX_IMAP_HOTE"): os.environ.pop(k, None)
    s = ouvrir(u); Magasin(os.environ["ATOMBOX_STORE"])
    a = adresse_de(s, "contact@exemple.fr")
    boite = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee"); s.add(boite)
    compte = Compte(compte_id=uuid7(), login="mathieu", nom="Mathieu", actif=True,
                    cree_le=datetime.now(timezone.utc), mot_de_passe_empreinte=hacher_mot_de_passe("secret")); s.add(compte)
    s.add(Acces(compte_id=compte.compte_id, boite_id=boite.boite_id, role="gestionnaire",
                debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
    inbox = Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom="INBOX", alias_imap="INBOX", protege=True)
    s.add(inbox)
    semer(s)
    cid = uuid7()
    s.add(Comm(comm_id=cid, type="email", date_recue=datetime.now(timezone.utc),
               date_ingestion=datetime.now(timezone.utc), sens="in", nature="humain",
               from_adresse="client@x.fr", sujet="Devis", taille=10, nb_pieces_jointes=0,
               est_chiffre=False, est_signe=False))
    s.add(Rattachement(comm_id=cid, boite_id=boite.boite_id, status="new", personnel=False,
                       gele=False, dossier_id=inbox.dossier_id, uid_servi=1))
    s.commit()

    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    import atombox.db as db; db._async.clear(); db._sync.clear()
    client = TestClient(creer_app())
    r = client.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["jeton"]}
    try:
        yield {"client": client, "h": h, "id": str(cid), "comm_id": cid,
               "compte_id": compte.compte_id, "boite_id": boite.boite_id, "session": s}
    finally:
        s.close()
        for k, v in avant.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        import asyncio
        db.moteur(u).dispose(); db._sync.clear()
        for m in list(db._async.values()):
            try: asyncio.run(m.dispose())
            except Exception: pass
        db._async.clear()
        admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
        admin.execute('DROP DATABASE "%s"' % nom); admin.close()


def _patch(monde, corps):
    r = monde["client"].patch("/api/v1/messages/%s/rattachement" % monde["id"], json=corps, headers=monde["h"])
    assert r.status_code == 200, r.text
    return r.json()["message"]


def test_a_revoir_n_efface_pas_l_ouverture(monde):
    """LE DÉFAUT QUE D175 CORRIGE. « Marquer comme non lu » est devenu « à revoir » : le geste est le
    même côté utilisateur — même bouton, même gras dans la liste —, mais il n'efface plus le fait.

    Contre-épreuve : rendre `lu: false` à son ancien comportement (`opened_at = NULL`) fait rougir
    la deuxième assertion. C'est la ligne qui garde la promesse."""
    from atombox.schema.modeles import ReadState
    m = _patch(monde, {"lu": True})
    assert m["lu"] is True and m["a_revoir"] is False
    s = monde["session"]; s.expire_all()
    etat = s.get(ReadState, (monde["compte_id"], monde["comm_id"], monde["boite_id"]))
    ouvert_le = etat.opened_at
    assert ouvert_le is not None and etat.open_count == 1

    m = _patch(monde, {"lu": False})
    assert m["a_revoir"] is True, "le geste dit désormais « j'y suis passé, il faut y retourner »"
    assert m["lu"] is True, "et il reste LU : l'ouverture a eu lieu, on ne la dément pas"
    s.expire_all()
    etat = s.get(ReadState, (monde["compte_id"], monde["comm_id"], monde["boite_id"]))
    assert etat.opened_at == ouvert_le, \
        "un FAIT ne s'efface pas pour exprimer une INTENTION (D175 § 1) — c'était tout le défaut"

    # et le gras revient : la liste « non lus » montre ce qui est à revoir
    l = monde["client"].get("/api/v1/messages", params={"dossier": "inbox", "filtre": "non_lus"},
                            headers=monde["h"]).json()
    assert [x["id"] for x in l["messages"]] == [monde["id"]], \
        "« à revoir » remet le message dans ce que la liste met en avant"

    m = _patch(monde, {"a_revoir": False})
    assert m["a_revoir"] is False and m["lu"] is True, "on retire l'intention, jamais le fait"


def test_rouvrir_compte_les_passages_sans_deplacer_la_premiere_fois(monde):
    """`opened_at` est la PREMIÈRE ouverture, `last_seen_at` la dernière, `open_count` les deux
    ensemble. Une clé (compte, message, statut) aurait interdit d'être « ouvert cinq fois »."""
    from atombox.schema.modeles import ReadState
    _patch(monde, {"lu": True})
    s = monde["session"]; s.expire_all()
    e1 = s.get(ReadState, (monde["compte_id"], monde["comm_id"], monde["boite_id"]))
    premier, compte1 = e1.opened_at, e1.open_count
    _patch(monde, {"lu": True})
    s.expire_all()
    e2 = s.get(ReadState, (monde["compte_id"], monde["comm_id"], monde["boite_id"]))
    assert e2.opened_at == premier, "la première ouverture ne se réécrit pas"
    assert e2.open_count == compte1 + 1 and e2.last_seen_at >= premier


def test_traite_puis_archive_se_relit(monde):
    """« Généralement un email est traité PUIS archivé quelques années après » — la phrase qui a
    obligé à garder QUATRE couples de dates au lieu d'un seul.

    Deux endroits en répondent, et le test vérifie les deux : le rattachement garde `processed_at`
    (sans quoi l'archivage automatique de D014 n'a plus de clé), et le journal garde le chemin.

    Contre-épreuve : faire écraser `processed_at` par l'archivage fait rougir l'assertion du
    milieu, et supprimer l'écriture au journal fait rougir la dernière."""
    m = _patch(monde, {"statut": "processed", "motif_sortie": "processed"})
    assert m["motif_sortie"] == "processed" and m["traite_le"], "la date suit la transition"
    traite_le = m["traite_le"]

    m = _patch(monde, {"motif_sortie": "archived"})
    assert m["motif_sortie"] == "archived", "l'état COURANT est unique et exclusif"
    assert m["traite_le"] == traite_le, \
        "archiver n'efface PAS la date de traitement : c'est la clé d'archivage (D014, D175 § 4 bis)"
    assert m["archive_le"] and m["archive_le"] != traite_le
    assert m["sorti_le"] == m["archive_le"], "« sorti_le » est la date de l'état où il se trouve"

    # LE CHEMIN PARCOURU : il n'est plus sur la ligne, il est au journal, qui n'est jamais purgé
    import asyncio
    lignes = asyncio.run(_journal(monde["comm_id"]))
    actions = [x["action"] for x in lignes]
    assert actions[:2] == ["archived", "processed"], \
        "le journal (D054) relit « traité, puis archivé » — l'état courant ne le dit plus (%r)" % actions
    archive = next(x for x in lignes if x["action"] == "archived")
    assert archive["details"]["avant"] == "processed" and archive["details"]["apres"] == "archived", \
        "chaque transition écrit d'où elle vient : sans cela l'historique est une liste, pas un chemin"


async def _journal(comm_id):
    """on lit par le MÊME chemin que la future route : `trace.lire`, pas un SELECT écrit ici —
    un test qui recompose la requête ne prouve pas que le lecteur du produit fonctionne"""
    from atombox.db import fabrique_async
    from atombox.services import trace
    async with fabrique_async()() as s:
        return await trace.lire(s, comm_id)


def test_remettre_en_file_efface_l_etat_et_garde_les_dates(monde):
    """Remettre dans la file, c'est retirer l'ÉTAT. Les dates restent : « il a été traité le 3 »
    reste vrai même s'il est revenu. C'est toute la différence entre un état et un fait."""
    _patch(monde, {"statut": "processed", "motif_sortie": "processed"})
    m = _patch(monde, {"motif_sortie": None})
    assert m["motif_sortie"] is None, "il est de retour dans l'INBOX"
    assert m["traite_le"], "et il porte toujours la trace de son passage par « traité »"
    assert m["sorti_le"] is None, "mais il n'est plus SORTI : l'état courant est vide"
