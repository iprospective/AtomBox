"""L'ÉCOUTEUR IMAP (D180, D183) — asyncio, une tâche par client.

    python3 -m atombox.imap.server

Réglages, tous préfixés `ATOMBOX_IMAPD_` pour ne PAS se confondre avec `ATOMBOX_IMAP_*`, qui
désigne le serveur du FOURNISSEUR qu'AtomBox relève (F001). La même confusion avait déjà coûté cher
sur les UID ; on ne la refait pas :

| Réglage | Défaut | Rôle |
|---|---|---|
| `ATOMBOX_IMAPD_LISTEN` | `127.0.0.1` | l'interface, ou plusieurs séparées par des virgules (`0.0.0.0,::` : IPv4 ET IPv6 — un nom qui a une adresse IPv6 l'exige). **En conteneur, cette boucle locale est celle DU CONTENEUR** — un client sur la machine hôte ne voit rien ; il faut alors écouter sur l'adresse du conteneur, ce qui exige TLS |
| `ATOMBOX_IMAPD_PORT` | `1143` | **pas 143** : un Dovecot tourne déjà sur cette machine. Avec TLS, l'usage est **1993** |
| `ATOMBOX_IMAPD_CERT` / `_KEY` | — | si les deux sont donnés, le port sert du TLS IMPLICITE dès le premier octet. Un certificat auto-signé se pose avec `tools/make-imapd-cert.sh` |
| `ATOMBOX_IMAPD_ALLOW_CLEAR` | — | `1` pour accepter le clair HORS de la boucle locale. Sans lui, l'écouteur refuse de démarrer : les mots de passe passeraient en clair sur le réseau |
| `ATOMBOX_IMAPD_MAX` | `20` | connexions simultanées ; au-delà, on refuse proprement au lieu de s'effondrer |

Une tâche par client, et une session de base par tâche : un client qui télécharge un gros message
ne doit pas faire attendre les autres.
"""
from __future__ import annotations
import asyncio
import os
import re
import unicodedata
import ssl
from ..journal import journal
from .session import Session
from .view import View
from .. import settings

log = journal("imap")

LINE_LIMIT = 64 * 1024        # une commande IMAP raisonnable ; au-delà, on coupe la connexion


class Listener:
    def __init__(self, db_session_factory, store, maximum: int | None = None, tls: bool = False):
        self.factory, self.store, self.tls = db_session_factory, store, tls
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
            log.info("connexion IMAP de %s (%d vivante(s), %s)", peer, self.live, "TLS" if self.tls else "clair")
            try:
                await self._send(writer, session.greeting())
                expected = 0
                while not session.done:
                    if expected:
                        # LES OCTETS DU LITTÉRAL, INTACTS, puis la FIN DE LIGNE qui le suit. Elle
                        # n'est pas un CRLF à jeter : elle porte la suite de la commande, parfois un
                        # second littéral. Et les octets ne passent plus par un décodage UTF-8 avec
                        # remplacement, qui aurait corrompu tout message 8 bits déposé par APPEND.
                        data = await reader.readexactly(expected)
                        expected = 0
                        rest = await reader.readline()
                        if len(rest) > LINE_LIMIT:
                            await self._send(writer, ["* BYE ligne trop longue"]); break
                        responses = session.literal(data, rest.decode("utf-8", "replace").rstrip("\r\n"))
                    elif session.idling is not None:
                        # IDLE : on attend le DONE du client, et pendant ce temps on interroge la base
                        # à intervalle court pour lui pousser ce qui a changé. Le réglage est relu à
                        # chaque attente : il se change sans redémarrer.
                        pause = float(settings.read("ATOMBOX_IMAPD_IDLE_POLL", "3"))
                        try:
                            line = await asyncio.wait_for(reader.readline(), timeout=pause)
                        except asyncio.TimeoutError:
                            pushed = session.idle_poll()
                            session.view.release()
                            if pushed: await self._send(writer, pushed)
                            continue
                        if not line: break
                        responses = session.line(line.decode("utf-8", "replace").rstrip("\r\n"))
                    else:
                        line = await reader.readline()
                        if not line: break
                        if len(line) > LINE_LIMIT:
                            await self._send(writer, ["* BYE ligne trop longue"]); break
                        responses = session.line(line.decode("utf-8", "replace").rstrip("\r\n"))
                    if responses and responses[0].startswith("+ "):
                        expected = session.awaiting_literal[1] if session.awaiting_literal else 0
                    await self._send(writer, responses)
                    if not expected:
                        session.view.release()      # pas de transaction ouverte pendant que le client réfléchit
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
            writer.write(ascii_status(l).encode("latin-1", "replace") + b"\r\n")
        await writer.drain()


# Une réponse d'ÉTAT : étiquetée ou non, OK / NO / BAD / BYE / PREAUTH — jamais une réponse de données.
_ETAT = re.compile(r"^(?:\*|[^ ]+) (?:OK|NO|BAD|BYE|PREAUTH)\b")
_LITTERAL = re.compile(r"\{\d+\}\r\n")
_ASCII = str.maketrans({"—": "-", "–": "-", "«": '"', "»": '"', "’": "'", "\u00a0": " ", "\u202f": " "})


def ascii_status(line: str) -> str:
    """LE TEXTE D'ÉTAT EN ASCII, et lui seul (RM3516).

    La RFC 3501 veut le texte d'une réponse (`resp-text`) en ASCII 7 bits. Nos messages sont en
    français : « AtomBox prêt » partait avec un octet 0xEA, et un client strict — l'application mail
    d'Android, le 04/11 — abandonnait dès l'accueil. On retire donc les accents des réponses d'ÉTAT
    (« prêt » → « pret »). Jamais d'une réponse de DONNÉES (FETCH, littéraux) : ses caractères sont
    les octets du message, décodés en latin-1, et les toucher fausserait le contenu et les tailles."""
    if not _ETAT.match(line) or _LITTERAL.search(line):
        return line
    t = unicodedata.normalize("NFKD", line.translate(_ASCII))
    return "".join(ch for ch in t if ord(ch) < 128)


def listen_hosts(value: str | None) -> list[str]:
    """`ATOMBOX_IMAPD_LISTEN` : une ou plusieurs adresses, séparées par des virgules (RM3516).

    `0.0.0.0` n'écoute qu'en IPv4 : un nom qui a aussi une adresse IPv6 envoie alors les clients
    IPv6 (un téléphone en 4G, souvent) sur un port fermé. `0.0.0.0,::` écoute sur les deux."""
    hosts = [h.strip() for h in (value or "").split(",") if h.strip()]
    return list(dict.fromkeys(hosts)) or ["127.0.0.1"]


def tls_context(cert: str | None = None, key: str | None = None):
    """le contexte TLS du serveur, ou None s'il n'a pas de certificat.

    UN SEUL DES DEUX EST UNE ERREUR, pas un repli sur le clair : qui a posé un certificat croit
    avoir chiffré, et le découvrirait chez le client — ou jamais."""
    cert = cert if cert is not None else settings.read("ATOMBOX_IMAPD_CERT")
    key = key if key is not None else settings.read("ATOMBOX_IMAPD_KEY")
    if not cert and not key: return None
    if not (cert and key):
        raise SystemExit("ATOMBOX_IMAPD_CERT et ATOMBOX_IMAPD_KEY vont ensemble : un seul est donné")
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    return ctx


def check_transport(host: str, tls: bool, allow_clear: bool = False) -> None:
    """REFUSER DE DÉMARRER plutôt que d'exposer des mots de passe.

    Le 20/10, mesuré : l'écouteur servait 10.0.3.11:1143 en clair, et la session — qui se croyait
    sous TLS — acceptait LOGIN et AUTH=PLAIN sans rien annoncer. Rien n'était faux dans chaque
    morceau ; c'est l'assemblage qui l'était, et personne ne le voyait. On tranche donc ici, au
    seul endroit qui connaît à la fois l'adresse et le transport : en clair, la boucle locale
    seulement (le développement, les tests) — sauf décision explicite."""
    import ipaddress
    if tls: return
    try:
        locale = host in ("localhost",) or ipaddress.ip_address(host).is_loopback
    except ValueError:
        locale = False
    if locale or allow_clear: return
    raise SystemExit(
        "IMAP en CLAIR sur %s refusé : les mots de passe passeraient en clair sur le réseau. "
        "Poser un certificat (tools/make-imapd-cert.sh, puis ATOMBOX_IMAPD_CERT/_KEY), ou "
        "assumer le clair avec ATOMBOX_IMAPD_ALLOW_CLEAR=1." % host)


async def main():
    from ..db import session as open_db
    from ..store import Store
    url = os.environ["DATABASE_URL"]
    store = Store(settings.read("ATOMBOX_STORE", "./magasin"))
    hosts = listen_hosts(settings.read("ATOMBOX_IMAPD_LISTEN", "127.0.0.1"))
    port = int(settings.read("ATOMBOX_IMAPD_PORT", "1143"))
    tls = tls_context()
    clair = settings.read("ATOMBOX_IMAPD_ALLOW_CLEAR", "") == "1"
    for h in hosts:                       # le clair n'est permis que si TOUTES sont locales
        check_transport(h, tls is not None, allow_clear=clair)
    host = hosts[0] if len(hosts) == 1 else hosts
    listener = Listener(lambda: open_db(url), store, tls=tls is not None)
    server = await asyncio.start_server(listener.client, host, port, ssl=tls)
    if tls is None and clair:
        log.warning("IMAP en CLAIR sur %s:%d, ASSUMÉ (ATOMBOX_IMAPD_ALLOW_CLEAR=1) : les mots de passe passent en clair", host, port)
    log.info("IMAP sur %s port %d (%s)", ", ".join(hosts), port, "TLS implicite" if tls else "clair")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
