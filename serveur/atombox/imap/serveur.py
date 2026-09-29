"""L'ÉCOUTEUR IMAP (D180) — asyncio, une tâche par client, lecture seule.

    python3 -m atombox.imap.serveur

Réglages, tous préfixés `ATOMBOX_IMAPD_` pour ne PAS se confondre avec `ATOMBOX_IMAP_*`, qui
désigne le serveur du FOURNISSEUR qu'AtomBox relève (F001). La même confusion avait déjà coûté cher
sur les UID ; on ne la refait pas :

| Réglage | Défaut | Rôle |
|---|---|---|
| `ATOMBOX_IMAPD_LISTEN` | `127.0.0.1` | l'interface. Locale par défaut : sans TLS, ce service n'a rien à faire sur un réseau. **En conteneur, cette boucle locale est celle DU CONTENEUR** — un client sur la machine hôte ne voit rien ; il faut alors écouter sur l'adresse du conteneur, et tout passe en clair |
| `ATOMBOX_IMAPD_PORT` | `1143` | **pas 143** : un Dovecot tourne déjà sur cette machine, et deux serveurs sur le même port, c'est le second qui ne démarre pas |
| `ATOMBOX_IMAPD_CERT` / `_CLE` | — | si les deux sont donnés, le port sert du TLS implicite (à mettre alors sur 1993) |
| `ATOMBOX_IMAPD_MAX` | `20` | connexions simultanées ; au-delà, on refuse proprement au lieu de s'effondrer |

Une tâche par client, et une session de base par tâche : un client qui télécharge un gros message
ne doit pas faire attendre les autres.
"""
from __future__ import annotations
import asyncio
import os
import ssl
from ..journal import journal
from .session import Session
from .vue import Vue
from .. import settings

log = journal("imap")

LIMITE_LIGNE = 64 * 1024        # une commande IMAP raisonnable ; au-delà, on coupe la connexion


class Ecouteur:
    def __init__(self, fabrique_session_bd, magasin, maximum: int | None = None):
        self.fabrique, self.magasin = fabrique_session_bd, magasin
        self.places = asyncio.Semaphore(maximum or int(settings.read("ATOMBOX_IMAPD_MAX", "20")))
        self.vivantes = 0

    async def client(self, lecteur: asyncio.StreamReader, ecrivain: asyncio.StreamWriter):
        pair = ecrivain.get_extra_info("peername")
        if self.places.locked():
            # REFUSER FRANCHEMENT VAUT MIEUX QU'ACCEPTER ET RAMER : un client qui reçoit BYE
            # réessaie plus tard ; un client accepté puis ignoré reste pendu, et l'utilisateur
            # conclut que le serveur est mort.
            ecrivain.write(b"* BYE trop de connexions, reessayez\r\n")
            await ecrivain.drain(); ecrivain.close()
            log.warning("connexion refusee (%s) : plafond atteint", pair)
            return
        async with self.places:
            self.vivantes += 1
            bd = self.fabrique()
            session = Session(Vue(bd, self.magasin), self.magasin)
            log.info("connexion IMAP de %s (%d vivante(s))", pair, self.vivantes)
            try:
                await self._envoyer(ecrivain, session.accueil())
                attendu = 0
                while not session.fini:
                    if attendu:
                        donnees = await lecteur.readexactly(attendu)
                        attendu = 0
                        await lecteur.readline()                 # le CRLF qui suit le littéral
                        reponses = session.ligne(donnees.decode("utf-8", "replace"))
                    else:
                        ligne = await lecteur.readline()
                        if not ligne: break
                        if len(ligne) > LIMITE_LIGNE:
                            await self._envoyer(ecrivain, ["* BYE ligne trop longue"]); break
                        reponses = session.ligne(ligne.decode("utf-8", "replace").rstrip("\r\n"))
                    if reponses and reponses[0].startswith("+ "):
                        attendu = session.attente_litteral[1] if session.attente_litteral else 0
                    await self._envoyer(ecrivain, reponses)
            except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
                log.info("client %s parti", pair)
            except Exception:
                log.exception("session IMAP de %s en echec", pair)
            finally:
                self.vivantes -= 1
                try: bd.close()
                except Exception: pass
                try:
                    ecrivain.close(); await ecrivain.wait_closed()
                except Exception: pass

    async def _envoyer(self, ecrivain, lignes):
        for l in lignes:
            ecrivain.write(l.encode("utf-8", "replace") + b"\r\n")
        await ecrivain.drain()


def contexte_tls():
    cert, cle = settings.read("ATOMBOX_IMAPD_CERT"), settings.read("ATOMBOX_IMAPD_KEY")
    if not (cert and cle): return None
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(cert, cle)
    return ctx


async def principal():
    from ..db import session as ouvrir
    from ..magasin import Magasin
    url = os.environ["DATABASE_URL"]
    magasin = Magasin(settings.read("ATOMBOX_STORE", "./magasin"))
    ecouteur = Ecouteur(lambda: ouvrir(url), magasin)
    hote = settings.read("ATOMBOX_IMAPD_LISTEN", "127.0.0.1")
    port = int(settings.read("ATOMBOX_IMAPD_PORT", "1143"))
    tls = contexte_tls()
    serveur = await asyncio.start_server(ecouteur.client, hote, port, ssl=tls)
    log.info("IMAP en LECTURE SEULE sur %s:%d%s", hote, port, " (TLS)" if tls else " (clair)")
    async with serveur:
        await serveur.serve_forever()


if __name__ == "__main__":
    asyncio.run(principal())
