"""UNE SESSION IMAP (D180, D183) — sans socket : elle prend une commande, rend des lignes.

Séparer la session du réseau n'est pas une coquetterie : c'est ce qui permet d'éprouver tout le
dialogue — connexion, sélection, relevé — dans un test, sans écouter sur un port ni attendre.

CE QU'ON N'ANNONCE PAS, ON NE LE SERT PAS. La CAPABILITY est le contrat : un client à qui l'on ne
promet ni CONDSTORE ni QRESYNC se rabat proprement sur une synchronisation simple ; un client à qui
on les promet sans les tenir CORROMPT SON CACHE, et le symptôme apparaît des jours plus tard, chez
lui. D'où `CAPACITES`, et un test qui vérifie qu'on ne sert rien d'autre.
"""
from __future__ import annotations
import base64
import re
from .protocol import LiteralNeeded, quote, parse_line, sequence
from ..journal import journal

log = journal("imap")

# CE QU'ON ANNONCE, ON LE TIENT. `MOVE` (RFC 6851) parce qu'un déplacement est UNE écriture chez
# nous et qu'un client qui l'a préfère toujours à COPY+STORE+EXPUNGE ; `SPECIAL-USE` (RFC 6154)
# parce que sans lui le client ne sait pas laquelle de nos boîtes est la corbeille, et s'en crée une.
# Toujours ni CONDSTORE ni QRESYNC : on ne les annonce pas, donc on ne les sert pas.
#
# NI `STARTTLS`, NI `LOGINDISABLED`. Le chiffrement est IMPLICITE (RFC 8314, qui le préfère à
# STARTTLS) : l'écouteur parle TLS dès le premier octet quand il a un certificat, et il REFUSE DE
# DÉMARRER en clair ailleurs que sur la boucle locale (voir `server.check_transport`). Une session
# n'a donc jamais à négocier quoi que ce soit. Elle annonçait `STARTTLS` hors TLS — sans qu'aucune
# commande le serve : la règle d'au-dessus, contredite trois lignes plus bas.
CAPABILITIES = ["IMAP4rev1", "AUTH=PLAIN", "UIDPLUS", "MOVE", "SPECIAL-USE", "NAMESPACE", "IDLE", "ID"]

# Les drapeaux qu'un message peut porter chez nous. `\\Seen` et `\\Flagged` sont PERSONNELS depuis
# D175 ; `\\Deleted` n'est pas un drapeau posé à côté mais une TRANSITION vers la corbeille (D183) —
# la traduction est volontaire : un message supprimé doit se retrouver dans la corbeille.
FLAGS = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]
# Ceux que le client peut MODIFIER — c'est ce que `PERMANENTFLAGS` annonce. `\\Answered` en fait
# partie parce que répondre est un acte collectif que nous savons enregistrer.
WRITABLE_FLAGS = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]


# Le plus gros littéral accepté — un message de 50 Mo, pièces jointes comprises. Au-delà, on répond
# NO AVANT le « + » : le client n'envoie rien, et l'on n'a pas lu cinquante mégaoctets pour les jeter.
MAX_LITERAL = 50 * 1024 * 1024


class Literal(str):
    """un littéral IMAP : la chaîne que les commandes ordinaires lisent, ET les octets exacts.

    LOGIN veut du texte ; APPEND veut les OCTETS, à l'octet près — c'est le message qu'on stocke
    (D025). Le littéral était autrefois décodé en UTF-8 avec remplacement puis réinjecté dans la
    ligne : tout message 8 bits qui n'était pas de l'UTF-8 aurait été corrompu en silence, et un
    message de 25 Mo repassé caractère par caractère dans l'analyseur."""
    def __new__(cls, raw: bytes):
        v = super().__new__(cls, raw.decode("utf-8", "replace"))
        v.raw = raw
        return v


def authenticated(fn): fn._authenticated = True; return fn
def selected(fn): fn._authenticated = fn._selected = True; return fn


class Session:
    """L'état d'un client connecté. `magasin` rend les octets, `vue` répond aux questions de la base.

    Les deux sont injectés : le harnais en pose des doubles, et la session ne sait pas qu'ils sont
    doubles — c'est la seule façon d'éprouver le protocole sans base ni disque."""

    def __init__(self, view, store):
        self.view, self.store = view, store
        self.compte = None            # None = pas encore authentifié
        self.mailbox = None             # la boîte aux lettres sélectionnée
        self.uids: list[int] = []     # ses UID, dans l'ordre — l'index+1 est le numéro de séquence
        self.done = False
        self.read_only = True     # SELECT ouvre en écriture, EXAMINE non (RFC 3501 § 6.3.2)
        self.awaiting_literal = None  # (ligne_partielle, octets_attendus) quand un littéral est en cours
        self.qui = ""                 # « ip:port client » — qui fait quoi, dans le journal (04/11)
        self._flags: dict = {}        # l'instantané des drapeaux du dossier sélectionné, pour NOOP/IDLE
        self._literals: list[bytes] = []   # les littéraux de la commande en cours, octets intacts
        self.idling = None            # l'étiquette de l'IDLE en cours, ou None (RFC 2177)

    # ── entrée ──────────────────────────────────────────────────────────────────────────────────
    def greeting(self) -> list[str]:
        return ["* OK [CAPABILITY %s] AtomBox prêt" % " ".join(self._capabilities())]

    def _capabilities(self) -> list[str]:
        return list(CAPABILITIES)

    def line(self, text: str) -> list[str]:
        """traite une ligne du client et rend les lignes à lui renvoyer"""
        if self.idling is not None:
            return self.idle_line(text)
        if self.awaiting_literal is not None:
            # l'ancienne interface : un littéral passé comme TEXTE. Gardée pour les doubles de test ;
            # l'écouteur, lui, passe les octets par `literal()`.
            return self.literal(text.encode("utf-8"), "")
        self._literals = []
        return self._process(text)

    def literal(self, data: bytes, rest: str) -> list[str]:
        """les octets d'un littéral, puis la FIN de la ligne qui le suit.

        La fin de ligne n'est pas un CRLF à jeter : `LOGIN {6}\r\nmathieu {6}\r\nsecret` porte un
        second littéral après le premier. L'écouteur la jetait, et toute commande à deux littéraux
        perdait sa seconde moitié."""
        prefix, _ = self.awaiting_literal
        self.awaiting_literal = None
        self._literals.append(data)
        # un repère court à la place des octets : l'analyseur n'a pas à parcourir 25 Mo caractère par
        # caractère, et il ne peut pas les mal lire — il ne les voit pas
        return self._process(prefix + "\x00%d\x00" % (len(self._literals) - 1) + rest)

    def _resolve(self, v):
        if isinstance(v, list): return [self._resolve(x) for x in v]
        if isinstance(v, str) and len(v) > 2 and v[0] == "\x00" and v[-1] == "\x00" and v[1:-1].isdigit():
            return Literal(self._literals[int(v[1:-1])])
        return v

    def _process(self, text: str) -> list[str]:
        try:
            elements = parse_line(text)
        except LiteralNeeded as e:
            # ON NE DEMANDE PAS DE DONNÉES POUR UNE COMMANDE QU'ON VA REFUSER. Sans ce contrôle,
            # `APPEND INBOX {3}` obtenait un « + » : le client envoyait son message, le serveur le
            # jetait, et les deux se désynchronisaient — la commande suivante était lue comme le
            # contenu du littéral. Sur un serveur en LECTURE SEULE, c'est aussi accepter un
            # téléversement de taille arbitraire pour rien.
            tag0 = text.split(" ", 1)[0] or "*"
            if not self._is_served(text):
                return ["%s BAD commande inconnue ou non servie" % tag0]
            if self._needs_login(text) and self.compte is None:
                return ["%s NO connectez-vous d'abord" % tag0]
            if e.n > MAX_LITERAL:
                log.info("littéral de %d octets refusé (plafond %d)", e.n, MAX_LITERAL)
                return ["%s NO [TOOBIG] littéral trop gros (%d octets, plafond %d)" % (tag0, e.n, MAX_LITERAL)]
            self.awaiting_literal = (text[:text.rindex("{")], e.n)
            return ["+ envoyez %d octets" % e.n]
        except ValueError as e:
            return ["* BAD %s" % e]
        if not elements: return ["* BAD commande vide"]
        elements = self._resolve(elements)
        tag = elements[0]
        cmd = (elements[1] if len(elements) > 1 else "").upper()
        args = elements[2:]
        method = getattr(self, "_c_" + cmd.lower().replace(".", "_"), None)
        if method is None:
            log.info("commande refusée : %s", cmd)
            return ["%s BAD commande inconnue ou non servie : %s" % (tag, cmd)]
        if method.__dict__.get("_authenticated") and self.compte is None:
            return ["%s NO connectez-vous d'abord" % tag]
        if method.__dict__.get("_selected") and self.mailbox is None:
            return ["%s BAD sélectionnez une boîte aux lettres d'abord" % tag]
        try:
            return method(tag, args)
        except Exception:
            log.exception("commande %s en échec", cmd)
            # UNE ERREUR NE DOIT PAS EMPOISONNER LA CONNEXION. Une écriture qui échoue laisse la
            # session SQLAlchemy en transaction avortée : tout ce qui suit lève
            # `PendingRollbackError`, y compris un NOOP. C'est arrivé en produit — un seul
            # déplacement refusé, et le client n'obtenait plus que « erreur interne » jusqu'à ce
            # qu'il se reconnecte. Le client, lui, ne peut rien en déduire ni rien réparer.
            try:
                self.view.rollback()
            except Exception:
                log.exception("l'annulation de la transaction a échoué elle aussi")
            return ["%s NO erreur interne" % tag]




    # ── le relevé : FETCH ───────────────────────────────────────────────────────────────────────
    def _fetch(self, tag, args, by_uid):
        if len(args) < 2: return ["%s BAD FETCH demande un ensemble et des éléments" % tag]
        targeted = sequence(args[0], self.uids, by_uid)
        requested = args[1] if isinstance(args[1], list) else [args[1]]
        requested = [d.upper() for d in requested]
        if "FAST" in requested: requested = ["FLAGS", "INTERNALDATE", "RFC822.SIZE"]
        elif "ALL" in requested: requested = ["FLAGS", "INTERNALDATE", "RFC822.SIZE", "ENVELOPE"]
        elif "FULL" in requested: requested = ["FLAGS", "INTERNALDATE", "RFC822.SIZE", "ENVELOPE", "BODY"]
        # LIRE LE CORPS MARQUE LU (RFC 3501 § 6.4.5) : `BODY[…]` sans `.PEEK`, `RFC822`, `RFC822.TEXT`.
        # Le 04/11, l'application mail d'Android : un message lu sur le téléphone redevenait non lu à
        # la synchronisation suivante — elle compte sur ce marquage implicite, quand Thunderbird envoie
        # un STORE explicite. Jamais en lecture seule (EXAMINE), jamais sur un PEEK. Le changement se
        # dit dans la même réponse : FLAGS est ajouté pour les messages qui viennent d'être marqués.
        implicit = not self.read_only and any(
            d.startswith("BODY[") or d in ("RFC822", "RFC822.TEXT") for d in requested)
        marked = set()
        if implicit:
            unseen = [u for u in targeted if (lambda m: m is not None and "\\Seen" not in m.flags)(
                self.view.message(self.mailbox, u))]
            if unseen:
                self.view.store_flags(self.compte, self.mailbox, unseen, ["\\Seen"], [])
                marked = set(unseen)
                self._flags = self._flags_of(self.mailbox)
        lines = []
        for uid in targeted:
            m = self.view.message(self.mailbox, uid)
            if m is None: continue
            chunks = []
            if uid in marked and "FLAGS" not in requested:
                chunks += self._element(m, "FLAGS")
            # UID TOUJOURS RENDU sur un UID FETCH, même si le client ne l'a pas demandé : la
            # RFC l'impose, et un client qui ne le reçoit pas ne sait pas de quoi on lui parle.
            if by_uid and "UID" not in requested: requested = requested + ["UID"]
            for d in requested:
                chunks += self._element(m, d)
            lines.append("* %d FETCH (%s)" % (self.uids.index(uid) + 1, " ".join(chunks)))
        return lines + ["%s OK FETCH" % tag]

    def _element(self, m, d):
        """un élément demandé → ses deux morceaux (nom, valeur), ou rien si on ne sait pas le servir"""
        if d == "UID": return ["UID", str(m.uid)]
        if d == "FLAGS": return ["FLAGS", "(%s)" % " ".join(m.flags)]
        if d == "RFC822.SIZE": return ["RFC822.SIZE", str(m.size)]
        if d == "INTERNALDATE": return ["INTERNALDATE", quote(m.internal_date)]
        if d == "ENVELOPE": return ["ENVELOPE", _rendered(m.envelope())]
        # BODY sans crochets : la structure SANS les données d'extension ; BODYSTRUCTURE : avec.
        if d == "BODYSTRUCTURE": return [d, _rendered(m.structure(True))]
        if d == "BODY": return [d, _rendered(m.structure(False))]
        # les formes RFC822 sont des alias anciens, que des clients emploient encore
        alias = {"RFC822": ("", "RFC822"), "RFC822.HEADER": ("HEADER", "RFC822.HEADER"), "RFC822.TEXT": ("TEXT", "RFC822.TEXT")}
        if d in alias:
            section, name = alias[d]
            data = m.section_bytes(section)
            return [] if data is None else [name, _literal(data)]
        if d.startswith("BODY.PEEK[") or d.startswith("BODY["):
            section = d[d.index("[") + 1:d.rindex("]")]
            data = m.section_bytes(section)
            if data is None: return []
            name = "BODY[%s]" % section
            # UNE TRANCHE : `BODY[2]<0.4096>`. Thunderbird télécharge les grosses pièces par morceaux ;
            # rendre le tout sous le nom `BODY[2]` quand il attend `BODY[2]<0>`, c'est une réponse
            # qu'il ne sait pas rattacher à sa demande (RFC 3501 § 6.4.5 et § 7.4.2).
            tail = d[d.rindex("]") + 1:]
            pm = re.match(r"^<(\d+)(?:\.(\d+))?>$", tail)
            if pm:
                start = int(pm.group(1)); length = int(pm.group(2)) if pm.group(2) else None
                data = data[start:start + length] if length is not None else data[start:]
                name += "<%d>" % start
            # LE LITTÉRAL COMPTE DES OCTETS, PAS DES CARACTÈRES. Un accent dans un en-tête et un
            # compte fait sur la chaîne décalent tout ce qui suit : le client lit le début du
            # message suivant comme la fin de celui-ci.
            return [name, _literal(data)]
        log.info("élément de FETCH non servi : %s", d)
        return []

    # ── la recherche : un sous-ensemble assumé ──────────────────────────────────────────────────
    def _search(self, tag, args, by_uid):
        """SEARCH — TOUS les critères de la RFC 3501 § 6.4.4 (`imap/search.py`), avec NOT, OR et les
        parenthèses. IMAP4rev1 les promet tous : on en refusait la plupart.

        Ce qu'on ne comprend pas reste une ERREUR (BAD), jamais une liste vide : « rien trouvé » ferait
        conclure à l'utilisateur que son message a disparu, et il n'insisterait pas."""
        from . import search as S
        args = list(args)
        if args and str(args[0]).upper() == "CHARSET":
            if len(args) < 2: return ["%s BAD CHARSET sans jeu de caractères" % tag]
            if str(args[1]).upper() not in ("UTF-8", "US-ASCII"):
                return ["%s NO [BADCHARSET (UTF-8 US-ASCII)] jeu de caractères non servi" % tag]
            args = args[2:]
        try:
            tree = S.parse(args, self.uids)
            found = [u for u in self.uids if S.matches(tree, self._search_facade(u))]
        except S.SearchError as e:
            log.info("SEARCH refusé : %s", e)
            return ["%s BAD %s" % (tag, e)]
        returned = found if by_uid else [self.uids.index(u) + 1 for u in found]
        return ["* SEARCH" + ("".join(" %d" % n for n in returned)), "%s OK SEARCH" % tag]

    def _search_facade(self, uid):
        from . import search as S
        fn = getattr(self.view, "search_message", None)
        if fn is not None: return fn(self.mailbox, uid, self.uids)
        m = self.view.message(self.mailbox, uid)            # un double de test : ses octets suffisent
        return S.Message(uid, self.uids, getattr(m, "raw", b""), m.flags, None, getattr(m, "size", None))

    def _needs_login(self, text: str) -> bool:
        """la commande exige-t-elle d'être connecté ? — pour ne pas lire un littéral qu'on refusera"""
        chunks = text.split(" ", 2)
        if len(chunks) < 2: return False
        m = getattr(self, "_c_" + chunks[1].lower().replace(".", "_"), None)
        return bool(m is not None and m.__dict__.get("_authenticated"))

    def _is_served(self, text: str) -> bool:
        """la commande est-elle connue ? — lu sur la ligne BRUTE, avant tout littéral"""
        chunks = text.split(" ", 2)
        if len(chunks) < 2: return False
        cmd = chunks[1].upper()
        if cmd == "UID" and len(chunks) > 2: cmd = "UID"
        return hasattr(self, "_c_" + cmd.lower().replace(".", "_"))

    # ── sans authentification ───────────────────────────────────────────────────────────────────
    def _c_capability(self, tag, args):
        return ["* CAPABILITY " + " ".join(self._capabilities()), "%s OK CAPABILITY" % tag]

    def _c_noop(self, tag, args): return self._refresh() + ["%s OK NOOP" % tag]

    def _flags_of(self, mailbox) -> dict:
        """l'instantané des drapeaux ; une vue qui ne sait pas le dire (une doublure) n'annonce rien"""
        f = getattr(self.view, "flags_of", None)
        return f(mailbox) if f is not None and mailbox is not None else {}

    def _c_id(self, tag, args):
        """ID (RFC 2971) : le client dit qui il est (« Thunderbird », « K-9 Mail »…), nous aussi.

        Le 04/11, impossible de dire depuis le journal QUELLE session avait été prévenue d'un
        déplacement : le téléphone et Thunderbird venaient de la même adresse. Le nom annoncé suit
        désormais l'adresse dans chaque ligne qui compte."""
        champs = args[0] if args and isinstance(args[0], list) else []
        info = {str(champs[i]).lower(): str(champs[i + 1]) for i in range(0, len(champs) - 1, 2)}
        nom = " ".join(x for x in (info.get("name"), info.get("version")) if x and x != "NIL")
        if nom:
            self.qui = ("%s %s" % (self.qui, nom.replace(" ", "_"))).strip()
            self.view.qui = self.qui
            log.info("%s se présente : %s", self.qui, nom)
        return ['* ID ("name" "AtomBox")', "%s OK ID" % tag]

    def _c_check(self, tag, args): return self._refresh() + ["%s OK CHECK" % tag]

    def _refresh(self) -> list[str]:
        """dit au client ce qui a DISPARU depuis sa dernière nouvelle, et ce qui est arrivé.

        Sans ça, un message retiré chez nous reste affiché chez lui pour toujours : rien ne le lui
        apprend. IMAP a un mot pour ça — `* n EXPUNGE` —, et un client qui ne le reçoit jamais ne
        peut que garder sa liste d'hier.

        DEUX RÈGLES QUI NE SE DEVINENT PAS :

        - on n'envoie JAMAIS d'EXPUNGE pendant un FETCH, un STORE ou un SEARCH (RFC 3501 § 5.2) :
          le client y compte les messages par leur NUMÉRO DE SÉQUENCE, et retirer une ligne au
          milieu décale tout ce qu'il est en train de lire. D'où l'envoi sur NOOP et CHECK, qui
          existent exactement pour ça ;
        - les numéros s'entendent sur la liste qui RÉTRÉCIT au fur et à mesure. Retirer les
          messages 2 et 5 d'une liste de six, c'est annoncer « 2 » puis « 4 » — pas « 2 » puis
          « 5 ». Les annoncer sur la liste d'origine décale le client d'un cran par suppression,
          en silence."""
        if self.mailbox is None: return []
        fresh = self.view.open_mailbox(self.compte, self.mailbox.name)
        if fresh is None: return []
        previous, resulting = list(self.uids), list(fresh.uids)
        present, lines = set(resulting), []
        current = list(previous)
        for uid in previous:
            if uid not in present:
                rank = current.index(uid) + 1
                lines.append("* %d EXPUNGE" % rank)
                current.pop(rank - 1)
        if len(resulting) != len(current):
            lines.append("* %d EXISTS" % len(resulting))
        # LES CHANGEMENTS D'ÉTAT FAITS AILLEURS (04/11) : lu sur le téléphone, le message restait non lu
        # dans Thunderbird jusqu'à ce qu'il rouvre le dossier. RFC 3501 § 7.4.2 : une réponse FETCH
        # non sollicitée dit au client que les drapeaux ont changé. UID inclus : le client sait de quel
        # message on parle sans recompter.
        new_flags = self._flags_of(fresh)
        old_flags = getattr(self, "_flags", {}) or {}
        changed = 0
        for i, uid in enumerate(resulting, 1):
            if uid in old_flags and new_flags.get(uid, ()) != old_flags[uid]:
                lines.append("* %d FETCH (UID %d FLAGS (%s))" % (i, uid, " ".join(new_flags.get(uid, ()))))
                changed += 1
        self._flags = new_flags
        if lines: log.info("%s boîte « %s » : %d disparu(s), %d changé(s), %d au total", self.qui, self.mailbox.name,
                            len(previous) - len(current), changed, len(resulting))
        self.mailbox, self.uids = fresh, resulting
        return lines

    def _c_logout(self, tag, args):
        self.done = True
        return ["* BYE au revoir", "%s OK LOGOUT" % tag]

    def _c_login(self, tag, args):
        if len(args) < 2: return ["%s BAD LOGIN demande un identifiant et un mot de passe" % tag]
        return self._login(tag, args[0], args[1])

    def _c_authenticate(self, tag, args):
        """AUTHENTICATE PLAIN, forme abrégée : le jeton peut venir collé à la commande (SASL-IR)."""
        if not args or args[0].upper() != "PLAIN":
            return ["%s NO seul PLAIN est servi" % tag]
        if len(args) < 2: return ["%s NO envoyez PLAIN avec son jeton (SASL-IR)" % tag]
        try:
            _, ident, password = base64.b64decode(args[1]).decode("utf-8").split("\x00", 2)
        except Exception:
            return ["%s NO jeton illisible" % tag]
        return self._login(tag, ident, password)

    def _login(self, tag, login, password):
        compte = self.view.authenticate(login, password)
        if compte is None:
            # Un délai serait à sa place ici ; il appartient à l'écouteur, qui sait dormir sans
            # bloquer les autres sessions.
            log.warning("échec d'authentification IMAP pour %r", login)
            return ["%s NO identifiants refusés" % tag]
        self.compte = compte
        log.info("%s session IMAP ouverte par %s", self.qui, login)
        return ["%s OK [CAPABILITY %s] bonjour" % (tag, " ".join(self._capabilities()))]

    # ── avec authentification ───────────────────────────────────────────────────────────────────
    @authenticated
    def _c_namespace(self, tag, args):
        return ['* NAMESPACE (("" "/")) NIL NIL', "%s OK NAMESPACE" % tag]

    @authenticated
    def _c_list(self, tag, args):
        pattern = args[1] if len(args) > 1 else "*"
        lines = ['* LIST (%s) "/" %s' % (" ".join(b.attributes), quote(b.name))
                  for b in self.view.mailboxes(self.compte) if _matches(b.name, pattern)]
        return lines + ["%s OK LIST" % tag]

    @authenticated
    def _c_lsub(self, tag, args):
        lines = [l.replace("* LIST", "* LSUB", 1) for l in self._c_list(tag, args)[:-1]]
        return lines + ["%s OK LSUB" % tag]

    @authenticated
    def _c_status(self, tag, args):
        if len(args) < 2: return ["%s BAD STATUS demande une boîte et des éléments" % tag]
        state = self.view.status(self.compte, args[0])
        if state is None: return ["%s NO boîte aux lettres inconnue" % tag]
        requested = args[1] if isinstance(args[1], list) else [args[1]]
        returned = " ".join("%s %d" % (d.upper(), state.get(d.upper(), 0)) for d in requested)
        return ["* STATUS %s (%s)" % (quote(args[0]), returned), "%s OK STATUS" % tag]

    # ── IDLE (RFC 2177) : le serveur PARLE le premier ───────────────────────────────────────────
    @authenticated
    def _c_idle(self, tag, args):
        """le client se tait et écoute ; c'est l'écouteur qui interroge la base pendant ce temps et
        lui pousse ce qui a changé (`idle_poll`), jusqu'à ce qu'il dise DONE (`idle_line`).

        Sans IDLE, un client interroge à intervalle fixe — Thunderbird toutes les dix minutes par
        défaut : un message arrivé attendait jusqu'à dix minutes pour s'afficher."""
        self.idling = tag
        return ["+ en attente — DONE pour reprendre"]

    def idle_poll(self) -> list[str]:
        """ce qui a changé depuis la dernière fois — appelé par l'écouteur pendant l'attente.

        Les mêmes lignes que NOOP, et le même calcul : un EXPUNGE ou un EXISTS annoncé pendant IDLE
        doit dire exactement ce qu'aurait dit NOOP, sinon le client se désynchronise selon la
        façon dont il a appris la nouvelle."""
        return self._refresh() if self.idling is not None else []

    def idle_line(self, text: str) -> list[str]:
        tag, self.idling = self.idling, None
        if text.strip().upper() == "DONE":
            return self._refresh() + ["%s OK IDLE terminé" % tag]
        # La RFC n'admet que DONE. Tout autre chose est une faute du client : on sort de l'attente
        # en le lui disant, plutôt que de lire sa ligne comme une commande dont on ignorerait l'étiquette.
        log.info("IDLE interrompu par autre chose que DONE : %.40r", text)
        return ["%s BAD IDLE attendait DONE" % tag]

    @authenticated
    def _c_append(self, tag, args):
        """APPEND boîte [(drapeaux)] [date] {littéral} — RFC 3501 § 6.3.11, avec APPENDUID (RFC 4315).

        C'est par là que Thunderbird enregistre un BROUILLON et range un ENVOYÉ. Le message passe
        par l'ingestion, comme un message relevé : stocké à l'octet (D025), dédoublonné (D064),
        rangé avec un UID neuf de la boîte d'arrivée (D183) — un seul chemin, pas un second."""
        if len(args) < 2: return ["%s BAD APPEND demande une boîte et un message" % tag]
        name, rest = args[0], list(args[1:])
        message = rest.pop() if rest else None
        if not isinstance(message, Literal):
            return ["%s BAD APPEND : le message doit être un littéral" % tag]
        flags = [_normalize_flag(f) for f in (rest.pop(0) if rest and isinstance(rest[0], list) else [])]
        when = None
        if rest:
            when = _internal_date(rest.pop(0))
            if when is None: return ["%s BAD APPEND : date interne illisible" % tag]
        res = self.view.append(self.compte, str(name), message.raw, flags, when)
        if res is None:
            # TRYCREATE : « crée-la puis recommence » (RFC 3501 § 6.3.11) — sans lui, le client
            # abandonne en silence et l'utilisateur croit son brouillon enregistré
            return ["%s NO [TRYCREATE] boîte aux lettres inconnue : %s" % (tag, name)]
        validity, uid = res
        lines = []
        if self.mailbox is not None and str(name).lower() == self.mailbox.name.lower():
            lines = self._refresh()          # le client doit apprendre le EXISTS de la boîte ouverte
        if uid is None:
            # le message était déjà rangé AILLEURS dans cette boîte (un rattachement = une boîte aux
            # lettres, D175 § 4) : on ne le déplace pas en douce, et l'on ne promet pas d'UID
            return lines + ["%s OK APPEND (déjà présent dans une autre boîte de cette adresse)" % tag]
        return lines + ["%s OK [APPENDUID %d %d] APPEND" % (tag, validity, uid)]

    # ── les dossiers (RM3499) ───────────────────────────────────────────────────────────────────
    def _folder_cmd(self, tag, what, fn, *names):
        from ..services.folders_util import FolderRefused
        try:
            fn(self.compte, *[str(n) for n in names])
        except FolderRefused as e:
            self.view.rollback()
            return ["%s NO [%s] %s" % (tag, e.code, e)]
        return ["%s OK %s" % (tag, what)]

    @authenticated
    def _c_create(self, tag, args):
        # UN SEUL nom : `CREATE Pi&AOg-ces jointes` sans guillemets créait « Pi&AOg-ces » et jetait
        # « jointes » en silence — un dossier au nom tronqué, sans un mot (RFC 3501 : erreur de syntaxe)
        if len(args) != 1: return ["%s BAD CREATE demande UN nom (entre guillemets s'il contient une espace)" % tag]
        if str(args[0]).strip("/").upper() == "INBOX": return ["%s NO [ALREADYEXISTS] INBOX existe toujours" % tag]
        return self._folder_cmd(tag, "CREATE", self.view.create, args[0])

    @authenticated
    def _c_rename(self, tag, args):
        if len(args) != 2: return ["%s BAD RENAME demande un ancien et un nouveau nom (entre guillemets s'ils contiennent une espace)" % tag]
        r = self._folder_cmd(tag, "RENAME", self.view.rename, args[0], args[1])
        # la boîte ouverte a changé de nom : la session doit la suivre, sinon le prochain NOOP la
        # croirait disparue et annoncerait l'EXPUNGE de chacun de ses messages
        if r[-1].startswith(tag + " OK") and self.mailbox is not None and self.mailbox.name.lower() == str(args[0]).lower():
            self.mailbox = self.view.open_mailbox(self.compte, str(args[1])) or self.mailbox
        return r

    @authenticated
    def _c_delete(self, tag, args):
        if len(args) != 1: return ["%s BAD DELETE demande UN nom (entre guillemets s'il contient une espace)" % tag]
        if self.mailbox is not None and self.mailbox.name.lower() == str(args[0]).lower():
            return ["%s NO [INUSE] la boîte est ouverte — la fermer d'abord" % tag]
        return self._folder_cmd(tag, "DELETE", self.view.delete, args[0])

    @authenticated
    def _c_subscribe(self, tag, args):
        """Tout dossier est ABONNÉ chez nous : LSUB rend ce que rend LIST. S'abonner est donc
        toujours vrai — si le dossier existe."""
        if not args: return ["%s BAD SUBSCRIBE demande un nom" % tag]
        if self.view.folder_named(self.compte, str(args[0])) is None:
            return ["%s NO [NONEXISTENT] boîte aux lettres inconnue" % tag]
        return ["%s OK SUBSCRIBE" % tag]

    @authenticated
    def _c_unsubscribe(self, tag, args):
        """Se désabonner d'un dossier qui EXISTE serait un mensonge : LSUB continuerait de le rendre,
        puisque l'abonnement n'est pas conservé (il demanderait une colonne — à l'étage 3 de RM3351,
        s'il le faut). On le dit. Se désabonner d'un dossier SUPPRIMÉ est le geste que fait
        Thunderbird après un DELETE : là, c'est vrai, et on répond OK."""
        if not args: return ["%s BAD UNSUBSCRIBE demande un nom" % tag]
        if self.view.folder_named(self.compte, str(args[0])) is None:
            return ["%s OK UNSUBSCRIBE" % tag]
        return ["%s NO [CANNOT] les abonnements ne sont pas conservés : tous les dossiers restent affichés" % tag]

    @authenticated
    def _c_select(self, tag, args): return self._select(tag, args, "SELECT")

    @authenticated
    def _c_examine(self, tag, args): return self._select(tag, args, "EXAMINE")

    def _select(self, tag, args, what):
        if not args: return ["%s BAD %s demande une boîte aux lettres" % (tag, what)]
        mailbox = self.view.open_mailbox(self.compte, args[0])
        if mailbox is None:
            self.mailbox = None
            return ["%s NO boîte aux lettres inconnue" % tag]
        self.mailbox, self.uids = mailbox, mailbox.uids
        self._flags = self._flags_of(mailbox)
        self.read_only = (what == "EXAMINE")
        # LE CLIENT DOIT SAVOIR CE QU'IL PEUT ÉCRIRE, exactement. Annoncer PERMANENTFLAGS () quand
        # on accepte les STORE ferait que Thunderbird n'essaierait même pas ; annoncer des drapeaux
        # qu'on ignore lui ferait croire que ses écritures ont porté. La liste est donc celle qu'on
        # tient, ni plus ni moins — et EXAMINE, lui, reste en lecture seule par définition.
        permanent = "" if self.read_only else " ".join(WRITABLE_FLAGS)
        return [
            "* %d EXISTS" % len(self.uids),
            "* 0 RECENT",                                   # on ne suit pas \\Recent : personne n'en dépend
            "* FLAGS (%s)" % " ".join(FLAGS),
            "* OK [PERMANENTFLAGS (%s)] " % permanent,
            "* OK [UIDVALIDITY %d] " % mailbox.uid_validity,
            "* OK [UIDNEXT %d] " % mailbox.uid_next,
            "%s OK [%s] %s" % (tag, "READ-ONLY" if self.read_only else "READ-WRITE", what),
        ]

    @selected
    def _c_close(self, tag, args):
        self.mailbox, self.uids = None, []
        return ["%s OK CLOSE" % tag]

    @selected
    def _c_fetch(self, tag, args): return self._fetch(tag, args, by_uid=False)

    @selected
    def _c_search(self, tag, args): return self._search(tag, args, by_uid=False)

    @authenticated
    def _c_uid(self, tag, args):
        """UID FETCH / UID SEARCH : la même chose, mais les nombres sont des UID."""
        if not args: return ["%s BAD UID demande une sous-commande" % tag]
        sub = args[0].upper()
        if self.mailbox is None: return ["%s BAD sélectionnez une boîte aux lettres d'abord" % tag]
        if sub == "FETCH": return self._fetch(tag, args[1:], by_uid=True)
        if sub == "SEARCH": return self._search(tag, args[1:], by_uid=True)
        if sub in ("MOVE", "COPY"): return self._move(tag, args[1:], sub, by_uid=True)
        if sub == "STORE": return self._store(tag, args[1:], by_uid=True)
        return ["%s BAD UID %s n'est pas servi" % (tag, sub)]

    @selected
    def _c_move(self, tag, args): return self._move(tag, args, "MOVE", by_uid=False)

    @selected
    def _c_copy(self, tag, args): return self._move(tag, args, "COPY", by_uid=False)

    @selected
    def _c_store(self, tag, args): return self._store(tag, args, by_uid=False)

    @selected
    def _c_expunge(self, tag, args):
        """EXPUNGE — chez nous, il ne DÉTRUIT rien, et c'est voulu.

        Un message « supprimé » est dans la corbeille (D183), et un rattachement marqué supprimé
        n'est JAMAIS effacé (D118) : c'est ce qui rend la déchetterie lisible par domaine. EXPUNGE
        se contente donc d'annoncer ce qui a quitté la boîte sélectionnée — ce que le client attend
        de lui, et la seule partie de son contrat que nous puissions honnêtement tenir."""
        if self.read_only: return ["%s NO boîte ouverte en lecture seule" % tag]
        return self._refresh() + ["%s OK EXPUNGE" % tag]

    # ── les écritures ───────────────────────────────────────────────────────────────────────────
    def _move(self, tag, args, what, by_uid):
        """MOVE et COPY vers une autre boîte aux lettres.

        COPY FAIT LA MÊME CHOSE QUE MOVE, et il faut le dire : la clé d'un rattachement est
        (message, boîte), donc un message ne peut pas être dans deux boîtes aux lettres de la même
        adresse — un message reçu est dans une et une seule des cinq (D175 § 4). Refuser COPY
        laisserait sans recours les clients qui ne connaissent pas MOVE ; le traiter comme un
        déplacement leur donne le résultat attendu, et le `COPYUID` le leur dit sans ambiguïté."""
        if self.read_only: return ["%s NO boîte ouverte en lecture seule" % tag]
        if len(args) < 2: return ["%s BAD %s demande un ensemble et une destination" % (tag, what)]
        targeted = sequence(args[0], self.uids, by_uid)
        if not targeted: return ["%s OK %s (rien à déplacer)" % (tag, what)]
        pairs = self.view.move(self.compte, self.mailbox, targeted, args[1])
        if pairs is None:
            # TRYCREATE dit au client « crée-la puis recommence » ; sans lui, il abandonne
            # silencieusement et l'utilisateur voit son geste ne rien faire (RFC 3501 § 6.4.7).
            return ["%s NO [TRYCREATE] boîte aux lettres inconnue : %s" % (tag, args[1])]
        if not pairs: return ["%s OK %s (aucun message visé)" % (tag, what)]
        dest = self.view.open_mailbox(self.compte, args[1])
        lines = ["* OK [COPYUID %d %s %s] déplacé" % (
            dest.uid_validity if dest else 1,
            ",".join(str(a) for a, _ in pairs), ",".join(str(b) for _, b in pairs))]
        # L'EXPUNGE VIENT APRÈS le COPYUID (RFC 6851 § 3.3) : le client doit savoir où le message
        # est arrivé avant d'apprendre qu'il a quitté la boîte courante, sinon il le perd de vue.
        return lines + self._refresh() + ["%s OK %s" % (tag, what)]

    def _store(self, tag, args, by_uid):
        """STORE ±FLAGS — et le silence de `.SILENT`, que les clients utilisent presque toujours."""
        if self.read_only: return ["%s NO boîte ouverte en lecture seule" % tag]
        if len(args) < 3: return ["%s BAD STORE demande un ensemble, une opération et des drapeaux" % tag]
        targeted = sequence(args[0], self.uids, by_uid)
        op = str(args[1]).upper()
        silent = op.endswith(".SILENT")
        if silent: op = op[:-len(".SILENT")]
        flags = args[2] if isinstance(args[2], list) else [args[2]]
        flags = [_normalize_flag(d) for d in flags]
        unknown_flags = [d for d in flags if d not in FLAGS]
        if unknown_flags:
            # On ne se tait pas sur ce qu'on ignore : un mot-clé qu'on jette en silence fait croire
            # au client qu'il est posé, et il l'affichera jusqu'à la fin des temps.
            log.info("STORE : drapeaux non servis, ignorés : %s", " ".join(unknown_flags))
        known_flags = [d for d in flags if d in FLAGS]
        if op == "FLAGS":
            # remplacement : ce qui n'est pas dans la liste est retiré
            to_add, to_remove = known_flags, [d for d in WRITABLE_FLAGS if d not in known_flags]
        elif op == "+FLAGS": to_add, to_remove = known_flags, []
        elif op == "-FLAGS": to_add, to_remove = [], known_flags
        else: return ["%s BAD opération de STORE inconnue : %s" % (tag, op)]
        self.view.store_flags(self.compte, self.mailbox, targeted, to_add, to_remove)
        self._flags = self._flags_of(self.mailbox)   # son propre geste n'est pas une nouvelle
        lines = []
        if not silent:
            for uid in targeted:
                m = self.view.message(self.mailbox, uid)
                if m is None: continue
                rank = self.uids.index(uid) + 1 if uid in self.uids else None
                if rank: lines.append("* %d FETCH (FLAGS (%s)%s)" % (
                    rank, " ".join(m.flags), " UID %d" % uid if by_uid else ""))
        # PAS D'EXPUNGE ICI : la RFC 3501 § 5.2 l'interdit pendant un STORE — le client compte les
        # messages par numéro de séquence, et retirer une ligne au milieu décale ce qu'il lit. Un
        # `\\Deleted` posé fait bien quitter la boîte, mais il l'apprendra au NOOP suivant.
        return lines + ["%s OK STORE" % tag]


def _matches(name: str, pattern: str) -> bool:
    """le joker IMAP : `*` traverse la hiérarchie, `%` s'arrête au séparateur"""
    if pattern in ("*", ""): return True
    import re
    # Construit l'expression caractère par caractère. Passer par `re.escape` puis remplacer les
    # jokers ne marche pas : depuis Python 3.7, `re.escape` n'échappe plus `%`, donc le
    # remplacement de `\%` ne trouvait rien et le motif « % » ne correspondait à RIEN.
    exp = "".join(".*" if c == "*" else "[^/]*" if c == "%" else re.escape(c) for c in pattern)
    return re.match("^" + exp + "$", name, re.I) is not None


def _literal(data: bytes) -> str:
    return "{%d}\r\n%s" % (len(data), data.decode("latin-1"))


def _rendered(v) -> str:
    """déjà mis en forme (la vue lit l'octet) — ou une liste à mettre en forme (les doubles de test)"""
    return v if isinstance(v, str) else quote(v)


_MOIS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def _internal_date(v):
    """« 17-Jul-1996 02:44:25 -0700 » (RFC 3501 § 9, date-time) → datetime, ou None.

    À la main et non par `strptime("%b")` : `%b` suit la LOCALE du processus, et un serveur lancé
    sous fr_FR attendrait « juil. »."""
    import re
    from datetime import datetime, timedelta, timezone
    m = re.match(r"^\s?(\d{1,2})-([A-Za-z]{3})-(\d{4}) (\d\d):(\d\d):(\d\d) ([+-])(\d\d)(\d\d)$", str(v))
    if not m or m.group(2).lower() not in _MOIS: return None
    d, mo, y, hh, mi, ss, sg, zh, zm = m.groups()
    tz = timezone((1 if sg == "+" else -1) * timedelta(hours=int(zh), minutes=int(zm)))
    try:
        return datetime(int(y), _MOIS[mo.lower()], int(d), int(hh), int(mi), int(ss), tzinfo=tz)
    except ValueError:
        return None


def _normalize_flag(d) -> str:
    """`\\seen` et `\\Seen` sont le même drapeau : la RFC les dit insensibles à la casse (§ 9).

    Sans ça, un client qui écrit en minuscules voyait ses STORE ignorés — et rien ne le lui disait."""
    s = str(d)
    for known in FLAGS:
        if s.lower() == known.lower(): return known
    return s
