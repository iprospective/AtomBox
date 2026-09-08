"""L'ÉTAT D'EXPLOITATION (F122 — D152) : ce qui se supervise, en une lecture.

La règle de D152 : « échouer bruyamment plutôt que deux fois ». Cette page rassemble les nombres
qui disent qu'AtomBox va bien — ou pas : le retard d'ingestion par boîte (`uid_next` connu contre
`uid_suivant` ingéré, D043), les files (événements en attente, en échec, abandonnés), le magasin,
le ramasse-miettes, et les règles muettes (D075 § 1). Les mêmes nombres sortent en texte lisible
par une supervision, sans adaptateur : AtomBox ne supervise pas, il se laisse superviser."""
from __future__ import annotations
import os
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from ..journal import dossier as dossier_journaux
from ..schema.modeles import Adresse, Blob, Boite, Comm, Dossier, Evenement, Filtre, PieceJointe, Rattachement
from ..journal import journal
from .messages import boites_du_compte, iso

log = journal("etat")

async def etat(s: AsyncSession, compte) -> dict:
    maintenant = datetime.now(timezone.utc)
    boites = await boites_du_compte(s, compte)
    ids = [b.boite_id for b in boites]

    # --- l'ingestion : le retard, boîte par boîte (D043 : uid_suivant contre uid_next connu)
    ingestion = []
    for b in boites:
        adresse = (await s.get(Adresse, b.adresse_id)).adresse_complete
        for d in await s.scalars(select(Dossier).where(Dossier.boite_id == b.boite_id).order_by(Dossier.alias_imap)):
            n = await s.scalar(select(func.count()).select_from(Rattachement).where(Rattachement.dossier_id == d.dossier_id))
            ingestion.append({"boite": adresse, "dossier": d.alias_imap or d.nom,
                              "uid_validity": d.uid_validity, "uid_suivant": d.uid_suivant,
                              "messages": n, "jamais_releve": d.uid_suivant is None})

    # --- les files (D161) : ce qui attend, ce qui a échoué, ce qui a été abandonné
    async def compter(**where):
        q = select(func.count()).select_from(Evenement)
        for k, v in where.items(): q = q.where(v)
        return await s.scalar(q)
    files = {
        "en_attente": await compter(a=Evenement.traite_le.is_(None), b=Evenement.tentatives == 0),
        "en_echec": await compter(a=Evenement.traite_le.is_(None), b=Evenement.tentatives > 0),
        "abandonnes": await compter(a=Evenement.abandonne.is_(True)),
        "traites": await compter(a=Evenement.traite_le.isnot(None)),
    }
    prochaine = await s.scalar(select(func.min(Evenement.prochaine_tentative)).where(Evenement.traite_le.is_(None)))
    plus_vieux = await s.scalar(select(func.min(Evenement.cree_le)).where(Evenement.traite_le.is_(None)))
    files["prochaine_tentative"] = iso(prochaine)
    files["plus_vieux_en_attente"] = iso(plus_vieux)
    files["retard_secondes"] = int((maintenant - plus_vieux).total_seconds()) if plus_vieux else 0
    derniers = [{"type": e.type, "tentatives": e.tentatives, "erreur": e.erreur, "cree_le": iso(e.cree_le)}
                for e in await s.scalars(select(Evenement).where(Evenement.traite_le.is_(None), Evenement.tentatives > 0)
                                         .order_by(Evenement.cree_le.desc()).limit(5))]

    # --- le magasin (D005, D087) : ce qu'il pèse, et ce que le ramasse-miettes doit reprendre
    magasin_dir = os.environ.get("ATOMBOX_MAGASIN", "./magasin")
    blobs = await s.scalar(select(func.count()).select_from(Blob)) or 0
    octets = await s.scalar(select(func.coalesce(func.sum(Blob.taille_stockee), 0)))
    bruts = await s.scalar(select(func.coalesce(func.sum(Blob.taille_octets), 0)))
    orphelins = await s.scalar(select(func.count()).select_from(Blob).where(Blob.nb_references <= 0)) or 0

    # --- les règles muettes (D075 § 1) : celles qui n'ont jamais rien attrapé
    muettes = [{"nom": f.nom, "cree": iso(None)} for f in await s.scalars(
        select(Filtre).where(Filtre.action.isnot(None), Filtre.actif.is_(True),
                             func.coalesce(Filtre.nb_declenchements, 0) == 0).limit(20))]

    if muettes: log.info("%d règle(s) active(s) n'ont jamais rien attrapé (D075 § 1)", len(muettes))
    if files["abandonnes"]: log.warning("%d événement(s) abandonné(s) — à regarder", files["abandonnes"])
    messages = await s.scalar(select(func.count()).select_from(Comm)) or 0
    pieces = await s.scalar(select(func.count()).select_from(PieceJointe)) or 0
    return {
        "quand": iso(maintenant),
        "ingestion": ingestion,
        "files": files, "en_echec": derniers,
        "magasin": {"chemin": magasin_dir, "blobs": blobs, "octets_stockes": int(octets or 0),
                    "octets_bruts": int(bruts or 0), "orphelins": orphelins,
                    "gain": round(1 - (octets or 0) / (bruts or 1), 3)},
        "contenu": {"messages": messages, "pieces_jointes": pieces,
                    "rattachements": await s.scalar(select(func.count()).select_from(Rattachement)) or 0,
                    "boites": len(boites)},
        "regles_muettes": muettes,
        "journaux": dossier_journaux(),
    }

def metriques(e: dict) -> str:
    """les mêmes nombres au format d'exposition standard — AtomBox ne supervise pas, il se laisse
    superviser (D152). Pas de bibliothèque : quatre lignes de texte suffisent."""
    l = []
    def m(nom, valeur, aide, etiquettes=""):
        l.append("# HELP atombox_%s %s" % (nom, aide)); l.append("# TYPE atombox_%s gauge" % nom)
        l.append("atombox_%s%s %s" % (nom, etiquettes, valeur))
    m("evenements_en_attente", e["files"]["en_attente"], "événements pas encore traités")
    m("evenements_en_echec", e["files"]["en_echec"], "événements en échec, en attente de reprise")
    m("evenements_abandonnes", e["files"]["abandonnes"], "événements abandonnés après toutes les tentatives")
    m("file_retard_secondes", e["files"]["retard_secondes"], "âge du plus vieux événement non traité")
    m("messages", e["contenu"]["messages"], "messages en base")
    m("magasin_octets", e["magasin"]["octets_stockes"], "octets stockés (après compression)")
    m("magasin_orphelins", e["magasin"]["orphelins"], "blobs sans porteur — le ramasse-miettes doit passer")
    m("regles_muettes", len(e["regles_muettes"]), "règles actives qui n'ont jamais rien attrapé")
    for d in e["ingestion"]:
        if d["uid_suivant"] is not None:
            m("dossier_messages", d["messages"], "messages ingérés par dossier",
              '{boite="%s",dossier="%s"}' % (d["boite"], d["dossier"]))
    return "\n".join(l) + "\n"
