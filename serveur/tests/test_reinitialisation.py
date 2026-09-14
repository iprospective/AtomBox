"""F129 / D164 — mot de passe oublié : le lien part à l'adresse de secours, et à elle seule."""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from test_messages import monde  # noqa: F401 — la même base jetable


def _async(coro):
    return asyncio.run(coro)


def test_le_parcours_complet(monde):  # noqa: F811
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    from atombox.api.securite import verifier_mot_de_passe
    from atombox.db import fabrique_async
    from atombox.schema.modeles import Compte, Domaine, Reinitialisation
    from atombox.services import reinitialisation as reinit
    import atombox.db as db
    db._async.clear(); db._sync.clear()
    s = monde["session"]
    compte = s.scalar(select(Compte).where(Compte.login == "mathieu"))
    envoyes = []

    async def parcours():
        async with fabrique_async()() as a:
            # 1. sans adresse de secours : rien ne part, et rien ne le dit
            await reinit.demander(a, "mathieu", "https://exemple.fr", envoyer=lambda o, d: envoyes.append((o, d)))
            assert not envoyes, "sans adresse de secours, aucun lien n'est envoyé (seul un gestionnaire peut réinitialiser)"
            n = len((await a.execute(select(Reinitialisation))).scalars().all())
            assert n == 0, "et aucune ligne n'est créée"

            # 2. une adresse de secours SERVIE PAR ATOMBOX est refusée : le lien serait circulaire
            c = await a.get(Compte, compte.compte_id)
            c.email_secours = "contact@exemple.fr"
            dom = await a.scalar(select(Domaine).where(Domaine.nom_ascii == "exemple.fr"))
            dom.heberge_par_nous = True
            await a.commit()
            await reinit.demander(a, "mathieu", "https://exemple.fr", envoyer=lambda o, d: envoyes.append((o, d)))
            assert not envoyes, "un lien envoyé dans la boîte qu'il protège n'en est pas un (D164)"

            # 3. une vraie adresse externe : un lien part, une ligne existe, le jeton n'est PAS en base
            c = await a.get(Compte, compte.compte_id)
            c.email_secours = "secours@ailleurs.test"
            await a.commit()
            await reinit.demander(a, "mathieu", "https://exemple.fr", ip="10.0.0.9",
                                  envoyer=lambda o, d: envoyes.append((o, d)))
            assert len(envoyes) == 1 and envoyes[0][1] == "secours@ailleurs.test"
            import email as _email
            msg = _email.message_from_bytes(envoyes[0][0], policy=_email.policy.default)
            corps = msg.get_content()          # décodé, comme le ferait un client mail
            jeton = corps.split("#reinitialiser=")[1].split()[0]
            lignes = (await a.execute(select(Reinitialisation))).scalars().all()
            assert len(lignes) == 1 and lignes[0].jeton_empreinte != jeton, "le jeton est stocké HACHÉ"
            assert msg["Auto-Submitted"] == "auto-generated", "ce message ne se répond pas (RFC 3834)"

            # 4. un mot de passe trop court est refusé avant tout le reste
            ok, motif = await reinit.appliquer(a, jeton, "court")
            assert not ok and "court" in motif

            # 5. le bon jeton : le mot de passe change, le jeton est consommé
            ok, _ = await reinit.appliquer(a, jeton, "un-mot-de-passe-neuf")
            assert ok
            ok2, motif2 = await reinit.appliquer(a, jeton, "encore-un-autre-mdp")
            assert not ok2 and "invalide" in motif2, "usage UNIQUE : le second essai échoue"

            # 6. un jeton périmé ne vaut rien
            await reinit.demander(a, "mathieu", "https://exemple.fr", envoyer=lambda o, d: envoyes.append((o, d)))
            m2 = _email.message_from_bytes(envoyes[-1][0], policy=_email.policy.default)
            j2 = m2.get_content().split("#reinitialiser=")[1].split()[0]
            from atombox.api.securite import empreinte_jeton
            r2 = await a.scalar(select(Reinitialisation).where(Reinitialisation.jeton_empreinte == empreinte_jeton(j2)))
            r2.expire_le = datetime.now(timezone.utc) - timedelta(minutes=1)
            await a.commit()
            ok3, motif3 = await reinit.appliquer(a, j2, "encore-un-autre-mdp")
            assert not ok3 and "périmé" in motif3

    _async(parcours())
    s.expire_all()
    compte = s.scalar(select(Compte).where(Compte.login == "mathieu"))
    assert verifier_mot_de_passe("un-mot-de-passe-neuf", compte.mot_de_passe_empreinte), "le mot de passe a bien changé"
    assert not verifier_mot_de_passe("secret", compte.mot_de_passe_empreinte), "l'ancien ne vaut plus rien"


def test_la_reponse_est_constante(monde):  # noqa: F811
    """Un compte inconnu, un compte sans secours et un compte servi rendent la MÊME chose :
    sinon le formulaire devient un annuaire des comptes existants."""
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    import atombox.db as db
    db._async.clear(); db._sync.clear()
    c = TestClient(creer_app())
    reponses = [c.post("/api/v1/session/reinitialisation", json={"utilisateur": qui})
                for qui in ("mathieu", "personne-du-tout", "", "contact@exemple.fr")]
    assert {r.status_code for r in reponses} == {200}
    assert len({r.json()["message"] for r in reponses}) == 1, "une seule phrase, pour tous les cas"


def test_la_limitation_des_essais(monde):  # noqa: F811
    """Prérequis de l'exposition publique : sans limite, un formulaire de connexion sur internet
    se fait marteler, et l'adresse de secours se fait inonder."""
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    from atombox.api import limitation
    import atombox.db as db
    db._async.clear(); db._sync.clear()
    limitation.vider()
    c = TestClient(creer_app())

    codes = [c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "faux"}).status_code
             for _ in range(12)]
    assert codes[0] == 401 and 429 in codes, "après quelques essais ratés, la porte se ferme"
    assert codes.index(429) <= 10, "et elle se ferme avant le onzième"
    r = c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "faux"})
    assert r.headers.get("Retry-After"), "le refus dit quand revenir"

    limitation.vider()
    dem = [c.post("/api/v1/session/reinitialisation", json={"utilisateur": "mathieu"}).status_code
           for _ in range(7)]
    assert 429 in dem, "une demande de réinitialisation ne s'envoie pas en boucle"

    limitation.vider()
