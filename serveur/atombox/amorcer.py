"""L'AMORÇAGE d'une instance (V0) : un compte avec son mot de passe, sa boîte, son accès, ses dossiers
spéciaux, son identité d'expédition — ce qu'il faut pour se connecter au webmail et voir l'ingestion.

    DATABASE_URL=… python3 -m atombox.amorcer --login mathieu --nom "Mathieu" --mot-de-passe … --boite contact@exemple.fr [--partagee]

Idempotent : relancé, il ne crée pas de doublon, il rattache. Le mot de passe n'est jamais journalisé."""
from __future__ import annotations
import argparse, sys
from datetime import datetime, timezone
from sqlalchemy import select
from .api.securite import hacher_mot_de_passe
from .db import session as ouvrir
from .ingestion.ingestion import adresse as adresse_de
from .journal import journal
from .schema.modeles import Acces, Boite, Compte, Dossier, Identite
from .uuid7 import uuid7

log = journal("auth")
SPECIAUX = (("INBOX", "INBOX"), ("Sent", "Envoyés"), ("Drafts", "Brouillons"), ("Junk", "Indésirables"), ("Trash", "Corbeille"))

def amorcer(login: str, nom: str, mot_de_passe: str | None, boite_adresse: str, partagee: bool = False, s=None) -> dict:
    s = s or ouvrir()
    compte = s.scalar(select(Compte).where(Compte.login == login.lower()))
    if compte is None:
        compte = Compte(compte_id=uuid7(), login=login.lower(), nom=nom, actif=True, cree_le=datetime.now(timezone.utc)); s.add(compte)
    if mot_de_passe: compte.mot_de_passe_empreinte = hacher_mot_de_passe(mot_de_passe)
    a = adresse_de(s, boite_adresse.lower())
    boite = s.scalar(select(Boite).where(Boite.adresse_id == a.adresse_id))
    if boite is None:
        boite = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="partagee" if partagee else "personnelle"); s.add(boite)
    s.flush()
    if not s.get(Acces, (compte.compte_id, boite.boite_id)):
        s.add(Acces(compte_id=compte.compte_id, boite_id=boite.boite_id, role="gestionnaire" if not partagee else "membre", debut=datetime.now(timezone.utc), accorde_par=compte.compte_id))
    for alias, nom_d in SPECIAUX:
        if not s.scalar(select(Dossier).where(Dossier.boite_id == boite.boite_id, Dossier.alias_imap == alias)):
            s.add(Dossier(dossier_id=uuid7(), boite_id=boite.boite_id, nom=nom_d, alias_imap=alias, protege=True))
    if not s.scalar(select(Identite).where(Identite.boite_id == boite.boite_id)):
        s.add(Identite(identite_id=uuid7(), boite_id=boite.boite_id, nom_affiche=nom, adresse_id=a.adresse_id, au_nom_de=False, par_defaut=True))
    s.commit()
    log.info("amorçage : compte %s, boîte %s", compte.login, boite_adresse)
    return {"compte_id": compte.compte_id, "boite_id": boite.boite_id}

def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--login", required=True); p.add_argument("--nom", required=True); p.add_argument("--mot-de-passe", default=None)
    p.add_argument("--boite", required=True, help="l'adresse de la boîte (aussi son login IMAP avec le compte master)")
    p.add_argument("--partagee", action="store_true")
    a = p.parse_args(argv)
    r = amorcer(a.login, a.nom, a.mot_de_passe, a.boite, a.partagee)
    print("compte %s, boîte %s" % (r["compte_id"], r["boite_id"]))

if __name__ == "__main__":
    principal()
