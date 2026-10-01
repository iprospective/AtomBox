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
from .view import View
from .. import settings

log = journal("imap")

LINE_LIMIT = 64 * 1024        # une commande IMAP raisonnable ; au-delà, on coupe la connexion


class Listener:
    def __init__(self, db_session_factory, store, maximum: int | None = None):
        self.factory, self.store = db_session_factory, store
        self.slots = asyncio.Semaphore(maximum or int(settings.read("ATOMBOX_IMAPD_MAX", "20")))
        self.live = 0

    async def client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        if self.slots.locked():
            # REFUSER FRANCHEMENT VAUT MIEUX QU'ACCEPTER ET RAMER : un client qui reçoit BYE
            # réessaie plus tard ; un client accepté puis ignoré reste pendu, et l'utilisateur
            # conclut que le serveur est mort.
            writer.write(b"* BYE trop de connexions, reessayez\r\n")
            await writer.drain(); writer.close()
            log.warning("connexion refusee (%s) : plafond atteint", peer)
            return
        async with self.slots:
            self.live += 1
            db = self.factory()
            session = Session(View(db, self.store), self.store)
            log.info("connexion IMAP de %s (%d vivante(s))", peer, self.live)
            try:
                await self._send(writer, session.greeting())
                expected = 0
                while not session.done:
                    if expected:
                        data = await reader.readexactly(expected)
                        expected = 0
                        await reader.readline()                 # le CRLF qui suit le littéral
                        responses = session.line(data.decode("utf-8", "replace"))
                    else:
                        line = await reader.readline()
                        if not line: break
                        if len(line) > LINE_LIMIT:
                            await self._send(writer, ["* BYE ligne trop longue"]); break
                        responses = session.line(line.decode("utf-8", "replace").rstrip("\r\n"))
                    if responses and responses[0].startswith("+ "):
                        expected = session.awaiting_literal[1] if session.awaiting_literal else 0
                    await self._send(writer, responses)
            except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
                log.info("client %s parti", peer)
            except Exception:
                log.exception("session IMAP de %s en echec", peer)
            finally:
                self.live -= 1
                try: db.close()
                except Exception: pass
                try:
                    writer.close(); await writer.wait_closed()
                except Exception: pass

    async def _send(self, writer, lines):
        """Les lignes sont encodées en LATIN-1, et ce n'est pas un choix de langue.

        IMAP transporte des OCTETS. Les corps de messages arrivent bruts du magasin, et on les
        glisse dans une `str` par `.decode("latin-1")` — la seule correspondance qui fasse
        correspondre un octet à un caractère, sans rien interpréter. L'encodage inverse doit donc
        être le même, sinon les octets changent en chemin.

        Avec un `.encode("utf-8")`, l'octet 0xC3 d'un « é » devenait le caractère « Ã », qui se
        réencode en DEUX octets : le client recevait du double-encodé (« DÃ©veloppement »), et —
        bien pire — la taille annoncée du littéral ne correspondait plus aux octets envoyés.
        Trente annoncés, trente-deux transmis : le client lit deux octets de trop, et tout ce qui
        suit est décalé. Le symptôme visible était l'accent ; le symptôme grave était la
        désynchronisation.

        Le texte du protocole est de l'ASCII, donc indifférent au choix. Les quelques mots français
        des réponses tiennent dans le latin-1 ; `replace` couvre le reste sans fausser le compte."""
        for l in lines:
            writer.write(l.encode("latin-1", "replace") + b"\r\n")
        await writer.drain()


def tls_context():
    cert, key = settings.read("ATOMBOX_IMAPD_CERT"), settings.read("ATOMBOX_IMAPD_KEY")
    if not (cert and key): return None
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(cert, key)
    return ctx


async def main():
    from ..db import session as open_db
    from ..store import Store
    url = os.environ["DATABASE_URL"]
    store = Store(settings.read("ATOMBOX_STORE", "./magasin"))
    listener = Listener(lambda: open_db(url), store)
    host = settings.read("ATOMBOX_IMAPD_LISTEN", "127.0.0.1")
    port = int(settings.read("ATOMBOX_IMAPD_PORT", "1143"))
    tls = tls_context()
    server = await asyncio.start_server(listener.client, host, port, ssl=tls)
    log.info("IMAP en LECTURE SEULE sur %s:%d%s", host, port, " (TLS)" if tls else " (clair)")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
