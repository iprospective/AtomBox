"""LE RELAIS SMTP (D114) — smtplib de la bibliothèque standard, STARTTLS si possible, une remise = un
appel ; la corrélation fine (DSN, VERP) est V2 (D119)."""
from __future__ import annotations
import os, smtplib, ssl
from ..journal import journal

log = journal("apps")

def config() -> dict:
    return { "hote": os.environ.get("ATOMBOX_SMTP_HOTE"), "port": int(os.environ.get("ATOMBOX_SMTP_PORT", "587")),
             "utilisateur": os.environ.get("ATOMBOX_SMTP_UTILISATEUR"), "mot_de_passe": os.environ.get("ATOMBOX_SMTP_MOT_DE_PASSE"),
             "tls": os.environ.get("ATOMBOX_SMTP_TLS", "starttls") }     # starttls | ssl | aucun

def remettre(octets: bytes, expediteur: str, destinataires: list[str], cfg: dict | None = None) -> dict:
    """rend {refuses: {adresse: (code, message)}, id: la réponse du relais} ; lève si le relais est injoignable"""
    c = cfg or config()
    if not c["hote"]: raise RuntimeError("ATOMBOX_SMTP_HOTE absent : aucun relais configuré (D114)")
    if c["tls"] == "ssl": cnx = smtplib.SMTP_SSL(c["hote"], c["port"], timeout=30, context=ssl.create_default_context())
    else: cnx = smtplib.SMTP(c["hote"], c["port"], timeout=30)
    try:
        cnx.ehlo()
        if c["tls"] == "starttls" and cnx.has_extn("starttls"): cnx.starttls(context=ssl.create_default_context()); cnx.ehlo()
        if c["utilisateur"]: cnx.login(c["utilisateur"], c["mot_de_passe"] or "")
        refuses = cnx.sendmail(expediteur, destinataires, octets)
        log.info("remis au relais %s : %s → %d destinataire(s), %d refusé(s)", c["hote"], expediteur, len(destinataires), len(refuses))
        return {"refuses": refuses}
    finally:
        try: cnx.quit()
        except Exception: pass
