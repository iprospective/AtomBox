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
CAPABILITIES = ["IMAP4rev1", "AUTH=PLAIN", "UIDPLUS", "MOVE", "SPECIAL-USE", "NAMESPACE"]

# Les drapeaux qu'un message peut porter chez nous. `\\Seen` et `\\Flagged` sont PERSONNELS depuis
# D175 ; `\\Deleted` n'est pas un drapeau posé à côté mais une TRANSITION vers la corbeille (D183) —
# la traduction est volontaire : un message supprimé doit se retrouver dans la corbeille.
FLAGS = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]
# Ceux que le client peut MODIFIER — c'est ce que `PERMANENTFLAGS` annonce. `\\Answered` en fait
# partie parce que répondre est un acte collectif que nous savons enregistrer.
WRITABLE_FLAGS = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]


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

    # ── entrée ──────────────────────────────────────────────────────────────────────────────────
    def greeting(self) -> list[str]:
        return ["* OK [CAPABILITY %s] AtomBox prêt" % " ".join(self._capabilities())]

    def _capabilities(self) -> list[str]:
        return list(CAPABILITIES)

    def line(self, text: str) -> list[str]:
        """traite une ligne du client et rend les lignes à lui renvoyer"""
        if self.awaiting_literal is not None:
            prefix, _ = self.awaiting_literal
            self.awaiting_literal = None
            text = prefix + '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
        try:
            elements = parse_line(text)
        except LiteralNeeded as e:
            # ON NE DEMANDE PAS DE DONNÉES POUR UNE COMMANDE QU'ON VA REFUSER. Sans ce contrôle,
            # `APPEND INBOX {3}` obtenait un « + » : le client envoyait son message, le serveur le
            # jetait, et les deux se désynchronisaient — la commande suivante était lue comme le
            # contenu du littéral. Sur un serveur en LECTURE SEULE, c'est aussi accepter un
            # téléversement de taille arbitraire pour rien.
            if not self._is_served(text):
                return ["%s BAD commande inconnue ou non servie" % (text.split(" ", 1)[0] or "*")]
            self.awaiting_literal = (text[:text.rindex("{")], e.n)
            return ["+ envoyez %d octets" % e.n]
        except ValueError as e:
            return ["* BAD %s" % e]
        if not elements: return ["* BAD commande vide"]
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
        lines = []
        for uid in targeted:
            m = self.view.message(self.mailbox, uid)
            if m is None: continue
            chunks = []
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
        if d == "ENVELOPE": return ["ENVELOPE", quote(m.envelope())]
        if d in ("BODY", "BODYSTRUCTURE"): return [d, quote(m.structure())]
        if d.startswith("BODY.PEEK[") or d.startswith("BODY["):
            section = d[d.index("[") + 1:d.rindex("]")]
            section_bytes = m.section_bytes(section)
            if section_bytes is None: return []
            # LE LITTÉRAL COMPTE DES OCTETS, PAS DES CARACTÈRES. Un accent dans un en-tête et un
            # compte fait sur la chaîne décalent tout ce qui suit : le client lit le début du
            # message suivant comme la fin de celui-ci.
            return ["BODY[%s]" % section, "{%d}\r\n%s" % (len(section_bytes), section_bytes.decode("latin-1"))]
        log.info("élément de FETCH non servi : %s", d)
        return []

    # ── la recherche : un sous-ensemble assumé ──────────────────────────────────────────────────
    def _search(self, tag, args, by_uid):
        """ALL, UID <ensemble>, et les critères d'en-tête les plus courants.

        Ce qu'on ne sait pas faire, on le dit : rendre une liste vide sur un critère qu'on n'a pas
        compris ferait croire au client qu'il n'y a rien, ce qui est pire qu'une erreur — il
        n'insiste pas, et l'utilisateur conclut que le message a disparu."""
        criteria = [a.upper() if isinstance(a, str) else a for a in args]
        if criteria and criteria[0] in ("CHARSET", "UTF-8"): criteria = criteria[2:] if criteria[0] == "CHARSET" else criteria[1:]
        found = list(self.uids)
        i = 0
        while i < len(criteria):
            c = criteria[i]
            if c == "ALL": i += 1; continue
            if c == "UID" and i + 1 < len(criteria):
                found = [u for u in found if u in set(sequence(args[i + 1], self.uids, True))]; i += 2; continue
            if c in ("FROM", "TO", "CC", "SUBJECT", "BODY", "TEXT") and i + 1 < len(criteria):
                needle = str(args[i + 1]).lower()
                found = [u for u in found if self.view.contains(self.mailbox, u, c, needle)]; i += 2; continue
            if c in ("SEEN", "UNSEEN", "FLAGGED", "UNFLAGGED"):
                wants = not c.startswith("UN")
                flag = "\\Seen" if c.endswith("SEEN") else "\\Flagged"
                found = [u for u in found if (flag in self.view.message(self.mailbox, u).flags) == wants]; i += 1; continue
            return ["%s NO critère de recherche non servi : %s" % (tag, c)]
        if by_uid: returned = found
        else: returned = [self.uids.index(u) + 1 for u in found]
        return ["* SEARCH" + ("".join(" %d" % n for n in returned)), "%s OK SEARCH" % tag]

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
        if lines: log.info("boîte « %s » : %d disparu(s), %d au total", self.mailbox.name,
                            len(previous) - len(current), len(resulting))
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
        log.info("session IMAP ouverte par %s", login)
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


def _normalize_flag(d) -> str:
    """`\\seen` et `\\Seen` sont le même drapeau : la RFC les dit insensibles à la casse (§ 9).

    Sans ça, un client qui écrit en minuscules voyait ses STORE ignorés — et rien ne le lui disait."""
    s = str(d)
    for known in FLAGS:
        if s.lower() == known.lower(): return known
    return s
