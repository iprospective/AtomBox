"""LES APPLICATIONS CONNECTÉES (F048 — D019, D020, D021, D108 ; RM3517).

Une application (le module Dolibarr d'une instance) appelle l'API SANS session humaine : elle
présente un jeton d'application. Ce jeton n'ouvre que sa PORTÉE — des boîtes, ou des domaines
entiers — et ne pose de tags que sur les axes que son application DÉCLARE.

Ce que l'application peut faire est volontairement étroit : LIRE (liste, message, fil, pièce
jointe, recherche) et ÉTIQUETER. Elle ne classe pas, ne supprime pas, n'envoie pas : ces routes
restent à la session d'une personne. Hors portée = 404, jamais 403 (D108).

Le jeton est montré UNE fois, à la création, et seule son empreinte est gardée — comme une session.

    DATABASE_URL=… python3 -m atombox.applications create --name dolibarr-demo --type dolibarr \\
        --domain exemple.fr --axis propal --axis commande
    DATABASE_URL=… python3 -m atombox.applications list
    DATABASE_URL=… python3 -m atombox.applications revoke --name dolibarr-demo
"""
from __future__ import annotations
import argparse, secrets, sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from sqlalchemy import select
from .journal import journal
from .schema.models import Adresse, Application, Axe, Boite, Domaine
from .uuid7 import uuid7

log = journal("auth")

# Un préfixe dit, à la lecture d'un journal ou d'un fichier de réglages, qu'il s'agit d'un jeton
# d'APPLICATION et non d'une session — sans rien révéler du secret.
PREFIX = "abxapp_"


def new_token() -> str: return PREFIX + secrets.token_urlsafe(32)


@dataclass
class AppPrincipal:
    """Celui qui appelle, quand c'est une application. Il a la FORME d'un compte là où les services
    en lisent un — `compte_id`, `login`, `preferences` — pour que la portée passe par le même
    chemin (`account_mailboxes`) au lieu d'un second, qui divergerait. Son `compte_id` est
    l'identifiant de l'application : aucune ligne d'état personnel n'y correspond, et l'application
    n'en écrit pas (elle n'a accès à aucune route qui en écrive)."""
    application: Application
    compte_id: object = None
    login: str = ""
    nom: str = ""
    actif: bool = True
    preferences: dict = field(default_factory=dict)

    def __post_init__(self):
        self.compte_id = self.application.application_id
        self.login = "application:" + self.application.nom
        self.nom = self.application.nom


async def mailboxes(s, app: Application) -> list[Boite]:
    """LA PORTÉE : {"boites": [adresses], "domaines": [noms]} → les boîtes, résolues à chaque appel.
    Une boîte ajoutée à un domaine de la portée y entre sans toucher à l'application."""
    portee = app.portee or {}
    adresses = [a.lower() for a in portee.get("boites", [])]
    domaines = [d.lower() for d in portee.get("domaines", [])]
    if not adresses and not domaines: return []
    q = select(Boite).join(Adresse, Adresse.adresse_id == Boite.adresse_id)
    conds = []
    if adresses: conds.append(Adresse.adresse_complete.in_(adresses))
    if domaines:
        conds.append(Boite.domaine_id.in_(select(Domaine.domaine_id).where(Domaine.nom_ascii.in_(domaines))))
    from sqlalchemy import or_
    return list(await s.scalars(q.where(or_(*conds))))


def declared_axes(app: Application) -> list[str]:
    return [a.lower() for a in (app.axes or [])]


# ---- l'administration, en ligne de commande (une page d'administration viendra) -----------------

def create(s, nom: str, type_connecteur: str, boites=(), domaines=(), axes=()) -> tuple[Application, str]:
    if s.scalar(select(Application).where(Application.nom == nom)):
        raise ValueError("une application « %s » existe déjà — révoquez-la ou choisissez un autre nom" % nom)
    jeton = new_token()
    from .api.security import token_fingerprint
    app = Application(application_id=uuid7(), type_connecteur=type_connecteur, nom=nom,
                      jeton_empreinte=token_fingerprint(jeton),
                      portee={"boites": [b.lower() for b in boites], "domaines": [d.lower() for d in domaines]},
                      axes=[a.lower() for a in axes], actif=True, cree_le=datetime.now(timezone.utc))
    s.add(app); s.flush()
    # Les axes DÉCLARÉS appartiennent à l'application (D019) : elle seule y pose des tags par jeton.
    # Un axe du même nom, créé à la main avant, lui est rattaché plutôt que dédoublé.
    for nom_axe in app.axes:
        axe = s.scalar(select(Axe).where(Axe.nom == nom_axe))
        if axe is None:
            n = s.scalar(select(Axe).order_by(Axe.ordre.desc()).limit(1))
            s.add(Axe(axe_id=uuid7(), nom=nom_axe, application_id=app.application_id, acl={}, derive=False,
                      ordre=((n.ordre or 0) + 1) if n else 1))
            s.flush()
        elif axe.application_id is None:
            axe.application_id = app.application_id
        elif axe.application_id != app.application_id:
            raise ValueError("l'axe « %s » appartient déjà à une autre application" % nom_axe)
    s.commit()
    log.info("application « %s » (%s) créée : portée %s, axes %s", nom, type_connecteur, app.portee, app.axes)
    return app, jeton


def revoke(s, nom: str) -> bool:
    app = s.scalar(select(Application).where(Application.nom == nom))
    if app is None: return False
    app.actif = False; s.commit()
    log.warning("application « %s » révoquée : son jeton ne passe plus", nom)
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description="Les applications connectées et leurs jetons (F048).")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--name", required=True); c.add_argument("--type", required=True, help="type de connecteur : dolibarr…")
    c.add_argument("--mailbox", action="append", default=[], help="une boîte de la portée (répétable)")
    c.add_argument("--domain", action="append", default=[], help="un domaine entier de la portée (répétable)")
    c.add_argument("--axis", action="append", default=[], help="un axe que l'application déclare (répétable)")
    r = sub.add_parser("revoke"); r.add_argument("--name", required=True)
    sub.add_parser("list")
    a = p.parse_args(argv)
    from .db import session as ouvrir
    s = ouvrir()
    if a.cmd == "create":
        if not a.mailbox and not a.domain: p.error("une portée est obligatoire : --mailbox ou --domain")
        try: app, jeton = create(s, a.name, a.type, a.mailbox, a.domain, a.axis)
        except ValueError as e: print("refusé : %s" % e, file=sys.stderr); return 1
        # Le jeton sort sur la sortie standard, et nulle part ailleurs : il n'est pas journalisé.
        print(jeton)
        print("(montré une seule fois — à mettre dans la configuration du module)", file=sys.stderr)
    elif a.cmd == "revoke":
        if not revoke(s, a.name): print("aucune application « %s »" % a.name, file=sys.stderr); return 1
    else:
        for app in s.scalars(select(Application).order_by(Application.nom)):
            print("%s\t%s\t%s\tportée=%s\taxes=%s\tdernier appel=%s" % (
                app.nom, app.type_connecteur, "actif" if app.actif else "RÉVOQUÉ", app.portee, app.axes,
                app.dernier_appel.isoformat() if app.dernier_appel else "jamais"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
