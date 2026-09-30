"""L'AMORÇAGE d'une instance (V0) : un compte avec son mot de passe, sa boîte, son accès, ses dossiers
spéciaux, son identité d'expédition — ce qu'il faut pour se connecter au webmail et voir l'ingestion.

    DATABASE_URL=… python3 -m atombox.amorcer --login mathieu --name "Mathieu" --password … --mailbox contact@exemple.fr [--shared]

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

def amorcer(login: str, nom: str, mot_de_passe: str | None, boite_adresse: str, partagee: bool = False, s=None, email_secours: str | None = None) -> dict:
    s = s or ouvrir()
    compte = s.scalar(select(Compte).where(Compte.login == login.lower()))
    if compte is None:
        compte = Compte(compte_id=uuid7(), login=login.lower(), nom=nom, actif=True, cree_le=datetime.now(timezone.utc)); s.add(compte)
    if mot_de_passe: compte.mot_de_passe_empreinte = hacher_mot_de_passe(mot_de_passe)
    if email_secours: compte.email_secours = email_secours.strip().lower()   # D164 — hors d'AtomBox
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
    # LE VOCABULAIRE DU PRODUIT, pas de la configuration : sans les marqueurs intégrés, « à revoir »
    # et « me le rappeler le… » existent dans l'interface et ne font rien (D178).
    from .schema.seeds import seed_builtins
    n = seed_builtins(s)
    # …et les quatre boîtes aux lettres d'état, sans quoi « Archiver » n'a nulle part où aller (D183)
    from .services.mailbox import ensure_mailboxes
    ensure_mailboxes(s, boite.boite_id)
    s.commit()
    log.info("amorçage : compte %s, boîte %s%s", compte.login, boite_adresse,
             (", %d marqueur(s) intégré(s) posé(s)" % n) if n else "")
    return {"compte_id": compte.compte_id, "boite_id": boite.boite_id}

def principal(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    # Les options sont en anglais (D181), SANS alias vers les anciennes — contrairement aux
    # variables d'environnement, qui gardent un repli. Les deux risques n'ont rien à voir : une
    # option inconnue échoue TOUT DE SUITE, bruyamment, avec la liste des options valides ; une
    # variable absente retombe en silence sur un défaut, et la panne se découvre trois jours plus
    # tard. On ne met un filet que là où la chute est silencieuse.
    p.add_argument("--login", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--password", default=None)
    p.add_argument("--mailbox", required=True, help="l'adresse de la boîte (aussi son login IMAP avec le compte master)")
    p.add_argument("--shared", action="store_true")
    p.add_argument("--recovery-email", default=None, help="l'adresse de RÉCUPÉRATION, hors d'AtomBox (D164)")
    a = p.parse_args(argv)
    r = amorcer(a.login, a.name, a.password, a.mailbox, a.shared, email_secours=a.recovery_email)
    print("compte %s, boîte %s" % (r["compte_id"], r["boite_id"]))

if __name__ == "__main__":
    principal()
