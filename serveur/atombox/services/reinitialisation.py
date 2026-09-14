"""MOT DE PASSE OUBLIÉ (F129 — D164).

Sur un webmail, envoyer un lien de réinitialisation dans la boîte qu'il protège n'est pas une
réinitialisation : qui a le mot de passe ouvre la boîte et lit le lien. Le lien part donc à
l'ADRESSE DE SECOURS du compte, hors d'AtomBox — et le service REFUSE d'envoyer à un domaine
qu'il héberge, parce qu'une adresse de secours mal saisie ne doit pas rendre la porte circulaire.

Trois règles qui tiennent tout :
  — la réponse est CONSTANTE, quoi qu'il arrive : sans elle, le formulaire devient un annuaire
    des comptes existants ;
  — le jeton est stocké HACHÉ et à usage unique : une fuite de base ne donne pas les liens en cours ;
  — à la réinitialisation, TOUTES les sessions du compte tombent : un mot de passe changé après une
    intrusion ne vaut rien si la session de l'intrus survit.
"""
from __future__ import annotations

import email.message
import email.policy
import email.utils
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.securite import empreinte_jeton, hacher_mot_de_passe, nouveau_jeton
from ..journal import journal
from ..schema.modeles import Adresse, Boite, Compte, Domaine, Reinitialisation, Session as SessionModele
from ..uuid7 import uuid7

log = journal("api")
DUREE = timedelta(minutes=30)          # D164
MIN_MOT_DE_PASSE = 10


async def _compte_de(s: AsyncSession, qui: str) -> Compte | None:
    """par login, ou par l'adresse d'une boîte à laquelle le compte accède."""
    qui = (qui or "").strip().lower()
    if not qui:
        return None
    c = await s.scalar(select(Compte).where(Compte.login == qui))
    if c:
        return c
    a = await s.scalar(select(Adresse).where(Adresse.adresse_complete == qui))
    if a is None:
        return None
    from ..schema.modeles import Acces
    b = await s.scalar(select(Boite).where(Boite.adresse_id == a.adresse_id))
    if b is None:
        return None
    acces = await s.scalar(select(Acces).where(Acces.boite_id == b.boite_id).limit(1))
    return await s.get(Compte, acces.compte_id) if acces else None


async def _heberge_ici(s: AsyncSession, adresse: str) -> bool:
    """AtomBox sert-il ce domaine ? Si oui, ce n'est pas une adresse de SECOURS."""
    dom = (adresse or "").rpartition("@")[2].lower()
    if not dom:
        return True
    d = await s.scalar(select(Domaine).where(Domaine.nom_ascii == dom))
    return bool(d and d.heberge_par_nous)


def _message(destinataire: str, compte: Compte, lien: str, expire: datetime, expediteur: str) -> bytes:
    m = email.message.EmailMessage(policy=email.policy.SMTP)
    m["From"] = expediteur
    m["To"] = destinataire
    m["Subject"] = "AtomBox — réinitialiser votre mot de passe"
    m["Date"] = email.utils.formatdate(localtime=True)
    m["Message-ID"] = email.utils.make_msgid()
    m["Auto-Submitted"] = "auto-generated"          # RFC 3834 : ce message ne se répond pas
    m.set_content(
        "Bonjour %s,\n\n"
        "Une réinitialisation du mot de passe a été demandée pour le compte « %s ».\n"
        "Si c'est bien vous, ouvrez ce lien avant %s :\n\n%s\n\n"
        "Le lien ne sert qu'une fois. Si ce n'est pas vous, ignorez ce message : rien n'a changé,\n"
        "et personne n'apprend par ce courrier si ce compte existe.\n"
        % (compte.nom, compte.login, expire.strftime("%d/%m/%Y à %H:%M UTC"), lien))
    return m.as_bytes()


async def demander(s: AsyncSession, qui: str, base_lien: str, ip: str | None = None, envoyer=None) -> None:
    """Rend TOUJOURS None : l'appelant répond la même chose dans tous les cas (D164)."""
    compte = await _compte_de(s, qui)
    if compte is None or not compte.actif:
        log.info("réinitialisation demandée pour un compte inconnu ou inactif (rien envoyé)")
        return None
    secours = (compte.email_secours or "").strip()
    if not secours:
        log.warning("réinitialisation impossible pour %s : aucune adresse de secours — "
                    "seul un gestionnaire peut réinitialiser (D164)", compte.login)
        return None
    if await _heberge_ici(s, secours):
        log.warning("réinitialisation refusée pour %s : l'adresse de secours est servie par AtomBox — "
                    "un lien envoyé dans la boîte qu'il protège n'en est pas un (D164)", compte.login)
        return None

    jeton = nouveau_jeton()
    maintenant = datetime.now(timezone.utc)
    expire = maintenant + DUREE
    s.add(Reinitialisation(reinitialisation_id=uuid7(), compte_id=compte.compte_id,
                           jeton_empreinte=empreinte_jeton(jeton), envoye_a=secours,
                           demande_le=maintenant, expire_le=expire, demande_par_ip=ip))
    await s.commit()
    lien = base_lien.rstrip("/") + "/#reinitialiser=" + jeton
    expediteur = await _expediteur(s, compte)
    octets = _message(secours, compte, lien, expire, expediteur)
    try:
        (envoyer or _remettre)(octets, secours)
        log.info("réinitialisation envoyée pour %s à son adresse de secours", compte.login)
    except Exception as ex:                      # le relais peut être indisponible : on le dit au journal
        log.error("réinitialisation pour %s : le relais a refusé (%s)", compte.login, ex)
    return None


async def _expediteur(s: AsyncSession, compte: Compte) -> str:
    """L'adresse d'envoi du service. Configurée, sinon `no-reply@` du domaine de la boîte du
    compte : un message de service parti d'un domaine étranger est refusé par SPF, et arrive
    dans les indésirables quand il n'est pas refusé — c'est-à-dire jamais lu."""
    configure = os.environ.get("ATOMBOX_EXPEDITEUR_SERVICE")
    if configure:
        return configure
    from ..schema.modeles import Acces
    acces = await s.scalar(select(Acces).where(Acces.compte_id == compte.compte_id).limit(1))
    if acces:
        b = await s.get(Boite, acces.boite_id)
        a = await s.get(Adresse, b.adresse_id) if b else None
        if a:
            return "no-reply@" + a.adresse_complete.rpartition("@")[2]
    return "no-reply@localhost"


def _remettre(octets: bytes, destinataire: str) -> None:
    from ..emission.smtp import remettre, config
    import email as _e
    exp = _e.message_from_bytes(octets)["From"]
    remettre(octets, exp, [destinataire], config())


async def appliquer(s: AsyncSession, jeton: str, nouveau: str) -> tuple[bool, str]:
    """(ok, motif). Le jeton est consommé, et toutes les sessions du compte tombent."""
    if len(nouveau or "") < MIN_MOT_DE_PASSE:
        return False, "mot de passe trop court (%d caractères au minimum)" % MIN_MOT_DE_PASSE
    r = await s.scalar(select(Reinitialisation).where(Reinitialisation.jeton_empreinte == empreinte_jeton(jeton or "")))
    maintenant = datetime.now(timezone.utc)
    if r is None or r.utilise_le is not None or r.expire_le < maintenant:
        log.warning("réinitialisation refusée : jeton inconnu, déjà utilisé ou périmé")
        return False, "lien invalide ou périmé"
    compte = await s.get(Compte, r.compte_id)
    if compte is None or not compte.actif:
        return False, "lien invalide ou périmé"
    compte.mot_de_passe_empreinte = hacher_mot_de_passe(nouveau)
    r.utilise_le = maintenant
    await s.execute(delete(SessionModele).where(SessionModele.compte_id == compte.compte_id))
    await s.commit()
    log.info("mot de passe réinitialisé pour %s ; toutes ses sessions sont tombées", compte.login)
    return True, "mot de passe changé"
