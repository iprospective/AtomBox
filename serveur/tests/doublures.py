"""LES DOUBLURES RÉSEAU des tests de bout en bout (RM3188) : un serveur IMAP et un relais SMTP, sur
127.0.0.1, dans le processus du test — pour que les VRAIS démons (ingestion, tâches) tournent contre
eux, en sous-processus.

Pourquoi un IMAP simulé, alors que `test_sync.py` s'y refusait (« un serveur simulé mentirait sur
le seul point qui compte, le protocole ») : ce que les tests de bout en bout cherchent n'est pas le
dialogue IMAP, c'est la CHAÎNE — un message qui arrive, un démon qui se réveille, un ordre qui
remonte. Le NOTIFY muet a survécu des semaines parce que personne ne faisait tourner la boucle. Le
protocole, lui, reste validé sur le pilote, contre un vrai Dovecot.

Ce que le faux IMAP reproduit FIDÈLEMENT, parce que le client en dépend :
  - `UID SEARCH UID n:*` rend le DERNIER message même quand n le dépasse (RFC 3501 § 6.4.8 : « * »
    est le plus grand UID) — un client qui l'ignore réingère le dernier message à chaque relève ;
  - IDLE ne rend la main que sur un événement ou un DONE ;
  - STORE .SILENT ne renvoie pas de FETCH.
Ce qu'il ne fait PAS : TLS, littéraux dans les commandes, recherche autre que par UID, sous-dossiers.
"""
from __future__ import annotations
import re, select, socket, threading, time


class FauxImap(threading.Thread):
    SEP = "/"

    def __init__(self, dossiers=("INBOX", "Sent", "Drafts", "Trash", "Junk")):
        super().__init__(daemon=True)
        self.sock = socket.socket(); self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0)); self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.verrou = threading.Condition()
        self.boites = {d: {"validity": 1000 + i, "suivant": 1, "messages": []} for i, d in enumerate(dossiers)}
        self.journal: list[str] = []              # les commandes reçues, pour les assertions
        self.changes: list[tuple[str, int]] = []  # (dossier, uid) dont les drapeaux ont bougé — pour IDLE
        self.arret = False

    # ---- ce que le TEST fait sur la boîte -------------------------------------------------------
    def deposer(self, octets: bytes, dossier: str = "INBOX", drapeaux=(), date: str = "18-Sep-2026 10:00:00 +0200") -> int:
        """un message arrive, comme si le MTA venait de le livrer ; réveille les IDLE"""
        with self.verrou:
            b = self.boites[dossier]
            uid = b["suivant"]; b["suivant"] += 1
            b["messages"].append({"uid": uid, "octets": octets, "flags": set(drapeaux), "date": date})
            self.verrou.notify_all()
            return uid

    def drapeaux(self, dossier: str, uid: int) -> set:
        with self.verrou:
            return set(next(m["flags"] for m in self.boites[dossier]["messages"] if m["uid"] == uid))

    def poser(self, dossier: str, uid: int, *flags):
        """un AUTRE client (Thunderbird, le téléphone) change un état — pour la synchro descendante"""
        with self.verrou:
            next(m for m in self.boites[dossier]["messages"] if m["uid"] == uid)["flags"].update(flags)
            self.changes.append((dossier, uid))
            self.verrou.notify_all()

    def retirer(self, dossier: str, uid: int, *flags):
        with self.verrou:
            next(m for m in self.boites[dossier]["messages"] if m["uid"] == uid)["flags"].difference_update(flags)
            self.changes.append((dossier, uid))
            self.verrou.notify_all()

    def arreter(self):
        self.arret = True
        try: self.sock.close()
        except Exception: pass

    # ---- le serveur ------------------------------------------------------------------------------
    def run(self):
        while not self.arret:
            try: c, _ = self.sock.accept()
            except OSError: return
            threading.Thread(target=self._session, args=(c,), daemon=True).start()

    def _session(self, c: socket.socket):
        f = c.makefile("rwb", buffering=0)
        ecrire = lambda s: f.write((s + "\r\n").encode() if isinstance(s, str) else s)
        ecrire("* OK [CAPABILITY IMAP4rev1 IDLE MOVE UIDPLUS] faux IMAP prêt")
        courant = None
        # ce que la SESSION a déjà appris : un serveur réel signale tout changement survenu depuis,
        # dès la commande suivante — IDLE comprise (RFC 3501 § 5.2). Partir de l'état à l'entrée en
        # IDLE, c'était taire un message arrivé entre le SELECT et l'IDLE.
        annonce = {"n": 0, "ch": 0}
        try:
            for brut in f:
                ligne = brut.decode("utf-8", "replace").rstrip("\r\n")
                if not ligne: continue
                tag, _, reste = ligne.partition(" ")
                cmd, _, args = reste.partition(" ")
                cmd = cmd.upper()
                with self.verrou: self.journal.append(reste)
                if cmd == "UID":
                    sous, _, args = args.partition(" ")
                    courant = self._uid(ecrire, tag, sous.upper(), args, courant); continue
                if cmd == "CAPABILITY": ecrire("* CAPABILITY IMAP4rev1 IDLE MOVE UIDPLUS"); ecrire(tag + " OK fait")
                elif cmd == "LOGIN": ecrire(tag + " OK connecté")
                elif cmd == "LIST":
                    for d in self.boites: ecrire('* LIST (\\HasNoChildren) "%s" "%s"' % (self.SEP, d))
                    ecrire(tag + " OK fait")
                elif cmd in ("SELECT", "EXAMINE"):
                    nom = self._nom(args)
                    if nom not in self.boites: ecrire(tag + " NO dossier inconnu"); continue
                    courant = nom
                    with self.verrou:
                        b = self.boites[nom]
                        annonce.update(n=len(b["messages"]), ch=len(self.changes))
                        ecrire("* %d EXISTS" % len(b["messages"]))
                        ecrire("* OK [UIDVALIDITY %d] ok" % b["validity"])
                        ecrire("* OK [UIDNEXT %d] ok" % b["suivant"])
                    ecrire(tag + " OK [%s] ok" % ("READ-WRITE" if cmd == "SELECT" else "READ-ONLY"))
                elif cmd == "IDLE": self._idle(c, f, ecrire, tag, courant, annonce)
                elif cmd == "LOGOUT": ecrire("* BYE"); ecrire(tag + " OK fait"); break
                elif cmd in ("NOOP", "CHECK", "CLOSE", "EXPUNGE", "SUBSCRIBE", "UNSUBSCRIBE", "CREATE"): ecrire(tag + " OK fait")
                else: ecrire(tag + " BAD commande inconnue du faux IMAP : " + cmd)
        except (OSError, ValueError):
            pass
        finally:
            try: c.close()
            except Exception: pass

    @staticmethod
    def _nom(args: str) -> str:
        return args.strip().strip('"')

    def _uids(self, ensemble: str, messages) -> list[int]:
        """« 3 », « 1,4 », « 2:* » — avec la sémantique réelle de « * » (le plus grand UID)"""
        tous = [m["uid"] for m in messages]
        if not tous: return []
        plus_grand, out = max(tous), set()
        for morceau in ensemble.split(","):
            if ":" in morceau:
                a, b = morceau.split(":")
                a = plus_grand if a == "*" else int(a); b = plus_grand if b == "*" else int(b)
                lo, hi = min(a, b), max(a, b)
                out.update(u for u in tous if lo <= u <= hi)
            else:
                out.update(u for u in tous if u == (plus_grand if morceau == "*" else int(morceau)))
        return sorted(out)

    def _uid(self, ecrire, tag, sous, args, courant):
        if courant is None: ecrire(tag + " NO aucun dossier sélectionné"); return courant
        with self.verrou:
            msgs = self.boites[courant]["messages"]
            seq = {m["uid"]: i + 1 for i, m in enumerate(msgs)}
            if sous == "SEARCH":
                m = re.search(r"UID\s+(\S+)", args)
                ecrire("* SEARCH" + "".join(" %d" % u for u in self._uids(m.group(1) if m else "1:*", msgs)))
                ecrire(tag + " OK fait")
            elif sous == "FETCH":
                ensemble, _, quoi = args.partition(" ")
                for u in self._uids(ensemble, msgs):
                    m = next(x for x in msgs if x["uid"] == u)
                    flags = " ".join(sorted(m["flags"]))
                    if "BODY" in quoi.upper():
                        tete = '* %d FETCH (UID %d INTERNALDATE "%s" FLAGS (%s) BODY[] {%d}\r\n' % (
                            seq[u], u, m["date"], flags, len(m["octets"]))
                        ecrire(tete.encode() + m["octets"] + b")\r\n")
                    else:
                        ecrire("* %d FETCH (UID %d FLAGS (%s))" % (seq[u], u, flags))
                ecrire(tag + " OK fait")
            elif sous == "STORE":
                ensemble, mode, liste = args.split(" ", 2)
                flags = set(liste.strip("()").split())
                for u in self._uids(ensemble, msgs):
                    m = next(x for x in msgs if x["uid"] == u)
                    if mode.upper().startswith("+"): m["flags"] |= flags
                    elif mode.upper().startswith("-"): m["flags"] -= flags
                    else: m["flags"] = set(flags)
                    self.changes.append((courant, u))
                    if not mode.upper().endswith(".SILENT"):
                        ecrire("* %d FETCH (UID %d FLAGS (%s))" % (seq[u], u, " ".join(sorted(m["flags"]))))
                self.verrou.notify_all()
                ecrire(tag + " OK fait")
            elif sous == "MOVE":
                ensemble, _, vers = args.partition(" ")
                vers = self._nom(vers); cible = self.boites.get(vers)
                if cible is None: ecrire(tag + " NO dossier inconnu"); return courant
                for u in self._uids(ensemble, msgs):
                    m = next(x for x in msgs if x["uid"] == u)
                    neuf = cible["suivant"]; cible["suivant"] += 1
                    cible["messages"].append(dict(m, uid=neuf, flags=set(m["flags"])))
                    msgs.remove(m)
                    ecrire("* OK [COPYUID %d %d %d] déplacé" % (cible["validity"], u, neuf))
                self.verrou.notify_all()
                ecrire(tag + " OK fait")
            else:
                ecrire(tag + " BAD UID " + sous + " inconnu du faux IMAP")
        return courant

    def _idle(self, c, f, ecrire, tag, courant, annonce):
        """RFC 2177 : on signale tout changement depuis ce que la session sait déjà, puis on attend
        un changement du dossier sélectionné, ou DONE"""
        ecrire("+ idling")
        vu, vu_ch = annonce["n"], annonce["ch"]
        while not self.arret:
            with self.verrou:
                self.verrou.wait(timeout=0.05)
                msgs = self.boites[courant]["messages"] if courant else []
                n, neufs = len(msgs), self.changes[vu_ch:]
                vu_ch = len(self.changes)
                fetch = [(i + 1, m) for d, u in neufs if d == courant
                         for i, m in enumerate(msgs) if m["uid"] == u]
            if n != vu:
                ecrire("* %d EXISTS" % n); vu = n; annonce["n"] = n
            annonce["ch"] = vu_ch
            for seq, m in fetch:        # un autre client a changé un drapeau : Dovecot le dit pendant IDLE
                ecrire("* %d FETCH (UID %d FLAGS (%s))" % (seq, m["uid"], " ".join(sorted(m["flags"]))))
            prets, _, _ = select.select([c], [], [], 0)
            if prets:
                ligne = f.readline()
                if not ligne or ligne.strip().upper() == b"DONE": break
        ecrire(tag + " OK IDLE terminé")


class FauxRelais(threading.Thread):
    """un relais SMTP qui accepte PLUSIEURS connexions (le RelaisFactice de test_emission n'en prend
    qu'une) et garde chaque remise : enveloppe et octets. Refuse toute adresse en @refuse.example."""

    def __init__(self):
        super().__init__(daemon=True)
        self.sock = socket.socket(); self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0)); self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.remises: list[dict] = []; self.verrou = threading.Lock(); self.arret = False

    def arreter(self):
        self.arret = True
        try: self.sock.close()
        except Exception: pass

    def attendre(self, n: int, delai: float) -> list[dict]:
        fin = time.monotonic() + delai
        while time.monotonic() < fin:
            with self.verrou:
                if len(self.remises) >= n: return list(self.remises)
            time.sleep(0.05)
        with self.verrou: return list(self.remises)

    def run(self):
        while not self.arret:
            try: c, _ = self.sock.accept()
            except OSError: return
            threading.Thread(target=self._session, args=(c,), daemon=True).start()

    def _session(self, c):
        f = c.makefile("rwb", buffering=0)
        rep = lambda x: f.write((x + "\r\n").encode())
        rep("220 faux relais"); de, pour, data, corps = None, [], False, []
        try:
            for brut in f:
                if data:
                    if brut in (b".\r\n", b".\n"):
                        with self.verrou:
                            self.remises.append({"de": de, "pour": list(pour), "octets": b"".join(corps)})
                        data, corps, pour = False, [], []; rep("250 OK remis")
                    else: corps.append(brut[1:] if brut.startswith(b"..") else brut)
                    continue
                l = brut.decode("utf-8", "replace").rstrip("\r\n"); cmd = l.split(" ")[0].upper()
                if cmd in ("EHLO", "HELO"): rep("250-faux relais"); rep("250 8BITMIME")
                elif cmd == "MAIL": de = re.search(r"<([^>]*)>", l).group(1); rep("250 OK")
                elif cmd == "RCPT":
                    a = re.search(r"<([^>]*)>", l).group(1)
                    if a.endswith("@refuse.example"): rep("550 5.1.1 inconnu")
                    else: pour.append(a); rep("250 OK")
                elif cmd == "DATA": data = True; rep("354 allez-y")
                elif cmd == "QUIT": rep("221 au revoir"); break
                else: rep("250 OK")
        except OSError:
            pass
        finally:
            try: c.close()
            except Exception: pass
