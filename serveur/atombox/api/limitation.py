"""LIMITATION DES TENTATIVES (D164, prérequis de l'exposition publique).

Un formulaire de connexion joignable depuis internet se fait marteler : sans limite, un mot de
passe faible tombe en quelques heures, et l'adresse de secours d'un compte se fait inonder de
liens de réinitialisation.

Fenêtre glissante, en MÉMOIRE DU PROCESSUS. Deux limites assumées, écrites ici pour qu'on ne les
découvre pas en incident :
  — elle repart à zéro au redémarrage du service ;
  — avec plusieurs travailleurs, chacun compte pour soi (le seuil réel est N × travailleurs).
C'est suffisant pour ralentir une attaque au point de la rendre inutile ; ce n'est pas un
pare-feu. Une limitation qui survit au redémarrage passera par la base, quand le besoin sera
mesuré plutôt que supposé.

La clé de comptage est (action, identifiant, IP) : viser une seule adresse ne sert à rien, et
essayer mille comptes depuis une adresse ne sert à rien non plus.
"""
from __future__ import annotations

import time
from collections import defaultdict

from ..journal import journal

log = journal("auth")

FENETRE_S = 15 * 60          # on oublie au bout d'un quart d'heure
SEUILS = {                   # action → (essais tolérés, message)
    "session": 10,
    "reinitialisation": 5,
}
_essais: dict[tuple, list] = defaultdict(list)


def _nettoyer(cle, maintenant):
    garde = [t for t in _essais[cle] if maintenant - t < FENETRE_S]
    if garde:
        _essais[cle] = garde
    else:
        _essais.pop(cle, None)
    return garde


def verifier(action: str, identifiant: str | None, ip: str | None) -> int:
    """Rend 0 si le geste est permis, sinon le nombre de secondes à attendre."""
    maintenant = time.time()
    seuil = SEUILS.get(action, 10)
    for cle in ((action, (identifiant or "").lower(), None), (action, None, ip)):
        essais = _nettoyer(cle, maintenant)
        if len(essais) >= seuil:
            attente = int(FENETRE_S - (maintenant - essais[0])) + 1
            log.warning("limitation : %s bloqué %d s (clé %s, %d essais)", action, attente,
                        "identifiant" if cle[1] is not None else "ip", len(essais))
            return attente
    return 0


def compter(action: str, identifiant: str | None, ip: str | None) -> None:
    """À appeler sur un essai RATÉ — un succès ne compte pas : on ne punit pas qui se connecte."""
    maintenant = time.time()
    _essais[(action, (identifiant or "").lower(), None)].append(maintenant)
    _essais[(action, None, ip)].append(maintenant)


def oublier(action: str, identifiant: str | None, ip: str | None) -> None:
    """Après un succès : le compteur de cet identifiant repart à zéro."""
    _essais.pop((action, (identifiant or "").lower(), None), None)


def vider() -> None:
    _essais.clear()
