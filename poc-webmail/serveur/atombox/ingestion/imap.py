"""LA RELÈVE IMAP (F001 — D046, D043) : PEEK (jamais de \\Seen posé par nous), compte master,
reprise par UID, IDLE. Bibliothèque standard `imaplib`, synchrone : le démon l'appelle dans
un thread par boîte (asyncio.to_thread). L'IDLE n'est pas dans imaplib : on l'écrit — trois
lignes de protocole (RFC 2177)."""
from __future__ import annotations
import email.utils, imaplib, re, socket, ssl
from datetime import datetime
from ..journal import journal

log = journal("imap")

class Releve:
    def __init__(self, hote: str, port: int = 993, tls: bool = True, delai: int = 60):
        self.hote, self.port, self.tls, self.delai = hote, port, tls, delai
        self.cnx: imaplib.IMAP4 | None = None

    def ouvrir(self, utilisateur: str, mot_de_passe: str):
        """utilisateur = « boite@domaine*masteruser » avec le compte master (chapitre 06)"""
        self.cnx = imaplib.IMAP4_SSL(self.hote, self.port, ssl_context=ssl.create_default_context(), timeout=self.delai) if self.tls \
                   else imaplib.IMAP4(self.hote, self.port, timeout=self.delai)
        self.cnx.login(utilisateur, mot_de_passe)
        log.info("connecté %s@%s:%d", utilisateur, self.hote, self.port)
        return self

    def fermer(self):
        try:
            if self.cnx: self.cnx.logout()
        finally: self.cnx = None

    def dossiers(self) -> list[str]:
        typ, lignes = self.cnx.list()
        out = []
        for l in lignes or []:
            m = re.match(rb'\((?P<flags>[^)]*)\) "(?P<sep>[^"]*)" (?P<nom>.+)$', l if isinstance(l, bytes) else l[0])
            if not m: continue
            if b"\\Noselect" in m.group("flags"): continue
            nom = m.group("nom").strip().strip(b'"').decode("utf-7" if b"&" in m.group("nom") else "ascii", "replace")
            out.append(nom)
        return out

    def selectionner(self, dossier: str) -> tuple[int, int]:
        """EXAMINE (lecture seule) ; rend (UIDVALIDITY, UIDNEXT)"""
        typ, _ = self.cnx.select(self._quoter(dossier), readonly=True)
        if typ != "OK":
            log.warning("EXAMINE %s refusé : %s", dossier, typ); raise RuntimeError("EXAMINE %s : %s" % (dossier, typ))
        def statut(nom):
            typ, v = self.cnx.response(nom); return int(v[0]) if v and v[0] else 0
        v, n = statut("UIDVALIDITY"), statut("UIDNEXT")
        log.debug("EXAMINE %s : uidvalidity %d, uidnext %d", dossier, v, n)
        return v, n

    def nouveaux(self, depuis_uid: int) -> list[int]:
        """les UID à partir de depuis_uid — la reprise (D043) ; « 1:* » au premier passage"""
        typ, data = self.cnx.uid("search", None, "UID", "%d:*" % max(1, depuis_uid))
        if typ != "OK" or not data or not data[0]: return []
        return [u for u in map(int, data[0].split()) if u >= depuis_uid]

    def lire(self, uid: int) -> tuple[bytes, datetime | None, list[str]]:
        """le message brut, sans poser \\Seen : BODY.PEEK[] ; avec sa date interne et ses drapeaux"""
        typ, data = self.cnx.uid("fetch", str(uid), "(BODY.PEEK[] INTERNALDATE FLAGS)")
        if typ != "OK" or not data or data[0] is None:
            log.warning("FETCH uid %d : %s", uid, typ); raise RuntimeError("FETCH %d : %s" % (uid, typ))
        meta, octets = data[0][0], data[0][1]
        m = re.search(rb'INTERNALDATE "([^"]+)"', meta)
        date = None
        if m:
            try: date = email.utils.parsedate_to_datetime(m.group(1).decode())
            except Exception: date = None
        f = re.search(rb'FLAGS \(([^)]*)\)', meta)
        drapeaux = f.group(1).decode().split() if f else []
        log.debug("FETCH uid %d : %d octets, %s", uid, len(octets), " ".join(drapeaux) or "-")
        return octets, date, drapeaux

    def idle(self, secondes: int = 25 * 60) -> bool:
        """attend un changement du dossier sélectionné (RFC 2177) ; rend True si quelque chose est arrivé.
        Les serveurs coupent un IDLE après ~30 min : on renouvelle avant."""
        c = self.cnx
        tag = c._new_tag()
        c.send(tag + b" IDLE\r\n")
        rep = c.readline()
        if not rep.startswith(b"+"):
            log.warning("IDLE refusé : %r", rep); raise RuntimeError("IDLE refusé : %r" % rep)
        log.debug("IDLE (%d s)", secondes)
        arrive = False
        c.sock.settimeout(secondes)
        try:
            ligne = c.readline()
            arrive = bool(ligne) and (b"EXISTS" in ligne or b"EXPUNGE" in ligne or b"FETCH" in ligne)
        except (socket.timeout, TimeoutError):
            arrive = False
        finally:
            c.sock.settimeout(self.delai)
            c.send(b"DONE\r\n")
            while True:
                l = c.readline()
                if not l or l.startswith(tag): break
        log.debug("IDLE terminé : %s", "du nouveau" if arrive else "rien")
        return arrive

    @staticmethod
    def _quoter(nom: str) -> str:
        return '"%s"' % nom.replace('"', '\\"')
