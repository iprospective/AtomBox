"""Le cœur de la synchronisation (F113) : la traduction entre l'état AtomBox et les FLAGS IMAP."""
from __future__ import annotations
import contextlib, threading
from datetime import datetime, timezone
from ..journal import journal

log = journal("imap")
_local = threading.local()

def descendante() -> bool:
    """vrai quand le processus applique un changement VENU d'IMAP : on ne le renvoie pas"""
    return getattr(_local, "descendante", False)

@contextlib.contextmanager
def en_descendante():
    avant = descendante(); _local.descendante = True
    try: yield
    finally: _local.descendante = avant

def drapeaux_voulus(ratt, etat=None) -> tuple[list[str], list[str]]:
    """(à poser, à retirer) — la traduction de l'état AtomBox vers les FLAGS IMAP.

    `etat` est la ligne read_state du membre qui relève (D175) : les drapeaux sont PERSONNELS depuis
    que l'IMAP sortant existe, et le fournisseur n'a qu'un jeu de drapeaux pour toute la boîte. On y
    envoie donc l'état de celui qui relève, et à défaut on ne prétend rien : sans ligne, le message
    n'a été ni ouvert ni marqué, donc les deux drapeaux se retirent.

    On ne touche QUE ce qu'on sait traduire : \\Seen et \\Flagged. Les mots-clés d'un autre client
    ne sont jamais effacés (D140b : IMAP est la vérité, pas notre copie)."""
    poser, retirer = [], []
    (poser if (etat and etat.vu) else retirer).append("\\Seen")
    (poser if (etat and etat.flagged) else retirer).append("\\Flagged")
    return poser, retirer

def etat_imap(flags: list[str]) -> dict:
    """la traduction inverse : ce que les FLAGS disent de l'état"""
    return {"lu": "\\Seen" in flags, "drapeau": "\\Flagged" in flags,
            "supprime": "\\Deleted" in flags}

def appliquer_descendante(s, ratt, flags: list[str]) -> list[str]:
    """Met l'état PERSONNEL du membre qui relève au diapason des FLAGS du fournisseur.

    CE N'EST PLUS UNE SOURCE DE VÉRITÉ, c'est une COMPATIBILITÉ (D175 § 3). Deux conséquences qu'il
    faut assumer explicitement :

      * l'état va sur le compte qui relève, pas sur le rattachement — et s'ils sont plusieurs sur la
        boîte, il ne va nulle part : le fournisseur ne dit pas QUI a lu, et on ne l'invente pas ;
      * un `\\Seen` retiré chez le fournisseur ne DÉTRUIT PLUS `opened_at`. Il pose « à revoir ».
        C'est tout le propos de D175 § 2 : le geste « marquer non lu » existe encore, mais il
        n'efface plus la trace que quelqu'un a regardé le message.

    Rend la liste des champs modifiés — vide si rien ne bouge, ce qui est le cas courant et doit
    rester silencieux."""
    from ..services import personal_state as perso
    e = etat_imap(flags); change = []
    compte_id = perso.polling_account(s, ratt.boite_id)
    if compte_id is None:
        log.debug("boîte %s : pas de relève unique, les drapeaux du fournisseur ne sont imputés à personne", ratt.boite_id)
        return change
    etat = perso.state_sync(s, compte_id, ratt.comm_id, ratt.boite_id)
    with en_descendante():
        if e["lu"] and not (etat and etat.opened_at):
            s.execute(perso.open_stmt(compte_id, ratt.comm_id, ratt.boite_id)); change.append("lu")
        elif not e["lu"] and etat and etat.opened_at:
            # on ne rend pas le message « non ouvert » — ça n'existe pas. On dit « à revoir ».
            perso.set_marker_sync(s, compte_id, ratt.comm_id, ratt.boite_id, perso.TO_REVIEW)
            change.append("à revoir")
        if e["drapeau"] != bool(etat.flagged if etat else False):
            s.execute(perso.flag_stmt(compte_id, ratt.comm_id, ratt.boite_id, e["drapeau"]))
            change.append("drapeau")
    return change
