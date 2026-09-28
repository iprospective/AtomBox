"""UNE SESSION IMAP, en LECTURE SEULE (D180) — sans socket : elle prend une commande, rend des lignes.

Séparer la session du réseau n'est pas une coquetterie : c'est ce qui permet d'éprouver tout le
dialogue — connexion, sélection, relevé — dans un test, sans écouter sur un port ni attendre.

CE QU'ON N'ANNONCE PAS, ON NE LE SERT PAS. La CAPABILITY est le contrat : un client à qui l'on ne
promet ni CONDSTORE ni QRESYNC se rabat proprement sur une synchronisation simple ; un client à qui
on les promet sans les tenir CORROMPT SON CACHE, et le symptôme apparaît des jours plus tard, chez
lui. D'où `CAPACITES`, et un test qui vérifie qu'on ne sert rien d'autre.
"""
from __future__ import annotations
import base64
from .protocole import BesoinDeLitteral, citer, decouper, sequence
from ..journal import journal

log = journal("imap")

# Lecture seule : ni STORE, ni APPEND, ni EXPUNGE, ni MOVE. `LOGINDISABLED` n'y est pas car le
# transport est chiffré par le serveur qui nous précède ; hors TLS, l'écouteur l'ajoute.
CAPACITES = ["IMAP4rev1", "AUTH=PLAIN", "UIDPLUS", "NAMESPACE"]

# Ce qu'un message peut porter comme drapeau chez nous aujourd'hui. `\\Seen` et `\\Flagged` sont
# collectifs tant que l'état personnel n'existe pas (D175, RM3320) : on les sert, on ne les écrit pas.
DRAPEAUX = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]


def authentifie(fn): fn._authentifie = True; return fn
def selectionne(fn): fn._authentifie = fn._selectionne = True; return fn


class Session:
    """L'état d'un client connecté. `magasin` rend les octets, `vue` répond aux questions de la base.

    Les deux sont injectés : le harnais en pose des doubles, et la session ne sait pas qu'ils sont
    doubles — c'est la seule façon d'éprouver le protocole sans base ni disque."""

    def __init__(self, vue, magasin, tls: bool = True):
        self.vue, self.magasin, self.tls = vue, magasin, tls
        self.compte = None            # None = pas encore authentifié
        self.boite = None             # la boîte aux lettres sélectionnée
        self.uids: list[int] = []     # ses UID, dans l'ordre — l'index+1 est le numéro de séquence
        self.fini = False
        self.attente_litteral = None  # (ligne_partielle, octets_attendus) quand un littéral est en cours

    # ── entrée ──────────────────────────────────────────────────────────────────────────────────
    def accueil(self) -> list[str]:
        return ["* OK [CAPABILITY %s] AtomBox prêt" % " ".join(self._capacites())]

    def _capacites(self) -> list[str]:
        caps = list(CAPACITES)
        if not self.tls: caps.insert(1, "STARTTLS")
        return caps

    def ligne(self, texte: str) -> list[str]:
        """traite une ligne du client et rend les lignes à lui renvoyer"""
        if self.attente_litteral is not None:
            debut, _ = self.attente_litteral
            self.attente_litteral = None
            texte = debut + '"' + texte.replace("\\", "\\\\").replace('"', '\\"') + '"'
        try:
            elements = decouper(texte)
        except BesoinDeLitteral as e:
            self.attente_litteral = (texte[:texte.rindex("{")], e.n)
            return ["+ envoyez %d octets" % e.n]
        except ValueError as e:
            return ["* BAD %s" % e]
        if not elements: return ["* BAD commande vide"]
        tag = elements[0]
        cmd = (elements[1] if len(elements) > 1 else "").upper()
        args = elements[2:]
        methode = getattr(self, "_c_" + cmd.lower().replace(".", "_"), None)
        if methode is None:
            log.info("commande refusée : %s", cmd)
            return ["%s BAD commande inconnue ou non servie : %s" % (tag, cmd)]
        if methode.__dict__.get("_authentifie") and self.compte is None:
            return ["%s NO connectez-vous d'abord" % tag]
        if methode.__dict__.get("_selectionne") and self.boite is None:
            return ["%s BAD sélectionnez une boîte aux lettres d'abord" % tag]
        try:
            return methode(tag, args)
        except Exception:
            log.exception("commande %s en échec", cmd)
            return ["%s NO erreur interne" % tag]




    # ── le relevé : FETCH ───────────────────────────────────────────────────────────────────────
    def _relever(self, tag, args, par_uid):
        if len(args) < 2: return ["%s BAD FETCH demande un ensemble et des éléments" % tag]
        vises = sequence(args[0], self.uids, par_uid)
        demandes = args[1] if isinstance(args[1], list) else [args[1]]
        demandes = [d.upper() for d in demandes]
        if "FAST" in demandes: demandes = ["FLAGS", "INTERNALDATE", "RFC822.SIZE"]
        elif "ALL" in demandes: demandes = ["FLAGS", "INTERNALDATE", "RFC822.SIZE", "ENVELOPE"]
        elif "FULL" in demandes: demandes = ["FLAGS", "INTERNALDATE", "RFC822.SIZE", "ENVELOPE", "BODY"]
        lignes = []
        for uid in vises:
            m = self.vue.message(self.boite, uid)
            if m is None: continue
            morceaux = []
            # UID TOUJOURS RENDU sur un UID FETCH, même si le client ne l'a pas demandé : la
            # RFC l'impose, et un client qui ne le reçoit pas ne sait pas de quoi on lui parle.
            if par_uid and "UID" not in demandes: demandes = demandes + ["UID"]
            for d in demandes:
                morceaux += self._element(m, d)
            lignes.append("* %d FETCH (%s)" % (self.uids.index(uid) + 1, " ".join(morceaux)))
        return lignes + ["%s OK FETCH" % tag]

    def _element(self, m, d):
        """un élément demandé → ses deux morceaux (nom, valeur), ou rien si on ne sait pas le servir"""
        if d == "UID": return ["UID", str(m.uid)]
        if d == "FLAGS": return ["FLAGS", "(%s)" % " ".join(m.drapeaux)]
        if d == "RFC822.SIZE": return ["RFC822.SIZE", str(m.taille)]
        if d == "INTERNALDATE": return ["INTERNALDATE", citer(m.date_interne)]
        if d == "ENVELOPE": return ["ENVELOPE", citer(m.enveloppe())]
        if d in ("BODY", "BODYSTRUCTURE"): return [d, citer(m.structure())]
        if d.startswith("BODY.PEEK[") or d.startswith("BODY["):
            section = d[d.index("[") + 1:d.rindex("]")]
            octets = m.octets(section)
            if octets is None: return []
            # LE LITTÉRAL COMPTE DES OCTETS, PAS DES CARACTÈRES. Un accent dans un en-tête et un
            # compte fait sur la chaîne décalent tout ce qui suit : le client lit le début du
            # message suivant comme la fin de celui-ci.
            return ["BODY[%s]" % section, "{%d}\r\n%s" % (len(octets), octets.decode("latin-1"))]
        log.info("élément de FETCH non servi : %s", d)
        return []

    # ── la recherche : un sous-ensemble assumé ──────────────────────────────────────────────────
    def _chercher(self, tag, args, par_uid):
        """ALL, UID <ensemble>, et les critères d'en-tête les plus courants.

        Ce qu'on ne sait pas faire, on le dit : rendre une liste vide sur un critère qu'on n'a pas
        compris ferait croire au client qu'il n'y a rien, ce qui est pire qu'une erreur — il
        n'insiste pas, et l'utilisateur conclut que le message a disparu."""
        criteres = [a.upper() if isinstance(a, str) else a for a in args]
        if criteres and criteres[0] in ("CHARSET", "UTF-8"): criteres = criteres[2:] if criteres[0] == "CHARSET" else criteres[1:]
        trouves = list(self.uids)
        i = 0
        while i < len(criteres):
            c = criteres[i]
            if c == "ALL": i += 1; continue
            if c == "UID" and i + 1 < len(criteres):
                trouves = [u for u in trouves if u in set(sequence(args[i + 1], self.uids, True))]; i += 2; continue
            if c in ("FROM", "TO", "CC", "SUBJECT", "BODY", "TEXT") and i + 1 < len(criteres):
                aiguille = str(args[i + 1]).lower()
                trouves = [u for u in trouves if self.vue.contient(self.boite, u, c, aiguille)]; i += 2; continue
            if c in ("SEEN", "UNSEEN", "FLAGGED", "UNFLAGGED"):
                veut = not c.startswith("UN")
                drapeau = "\\Seen" if c.endswith("SEEN") else "\\Flagged"
                trouves = [u for u in trouves if (drapeau in self.vue.message(self.boite, u).drapeaux) == veut]; i += 1; continue
            return ["%s NO critère de recherche non servi : %s" % (tag, c)]
        if par_uid: rendus = trouves
        else: rendus = [self.uids.index(u) + 1 for u in trouves]
        return ["* SEARCH" + ("".join(" %d" % n for n in rendus)), "%s OK SEARCH" % tag]

    # ── sans authentification ───────────────────────────────────────────────────────────────────
    def _c_capability(self, tag, args):
        return ["* CAPABILITY " + " ".join(self._capacites()), "%s OK CAPABILITY" % tag]

    def _c_noop(self, tag, args): return ["%s OK NOOP" % tag]

    def _c_logout(self, tag, args):
        self.fini = True
        return ["* BYE au revoir", "%s OK LOGOUT" % tag]

    def _c_login(self, tag, args):
        if len(args) < 2: return ["%s BAD LOGIN demande un identifiant et un mot de passe" % tag]
        return self._ouvrir(tag, args[0], args[1])

    def _c_authenticate(self, tag, args):
        """AUTHENTICATE PLAIN, forme abrégée : le jeton peut venir collé à la commande (SASL-IR)."""
        if not args or args[0].upper() != "PLAIN":
            return ["%s NO seul PLAIN est servi" % tag]
        if len(args) < 2: return ["%s NO envoyez PLAIN avec son jeton (SASL-IR)" % tag]
        try:
            _, ident, mdp = base64.b64decode(args[1]).decode("utf-8").split("\x00", 2)
        except Exception:
            return ["%s NO jeton illisible" % tag]
        return self._ouvrir(tag, ident, mdp)

    def _ouvrir(self, tag, identifiant, mdp):
        compte = self.vue.authentifier(identifiant, mdp)
        if compte is None:
            # Un délai serait à sa place ici ; il appartient à l'écouteur, qui sait dormir sans
            # bloquer les autres sessions.
            log.warning("échec d'authentification IMAP pour %r", identifiant)
            return ["%s NO identifiants refusés" % tag]
        self.compte = compte
        log.info("session IMAP ouverte par %s", identifiant)
        return ["%s OK [CAPABILITY %s] bonjour" % (tag, " ".join(self._capacites()))]

    # ── avec authentification ───────────────────────────────────────────────────────────────────
    @authentifie
    def _c_namespace(self, tag, args):
        return ['* NAMESPACE (("" "/")) NIL NIL', "%s OK NAMESPACE" % tag]

    @authentifie
    def _c_list(self, tag, args):
        motif = args[1] if len(args) > 1 else "*"
        lignes = ['* LIST (%s) "/" %s' % (" ".join(b.attributs), citer(b.nom))
                  for b in self.vue.boites(self.compte) if _correspond(b.nom, motif)]
        return lignes + ["%s OK LIST" % tag]

    @authentifie
    def _c_lsub(self, tag, args):
        lignes = [l.replace("* LIST", "* LSUB", 1) for l in self._c_list(tag, args)[:-1]]
        return lignes + ["%s OK LSUB" % tag]

    @authentifie
    def _c_status(self, tag, args):
        if len(args) < 2: return ["%s BAD STATUS demande une boîte et des éléments" % tag]
        etat = self.vue.etat(self.compte, args[0])
        if etat is None: return ["%s NO boîte aux lettres inconnue" % tag]
        demandes = args[1] if isinstance(args[1], list) else [args[1]]
        rendus = " ".join("%s %d" % (d.upper(), etat.get(d.upper(), 0)) for d in demandes)
        return ["* STATUS %s (%s)" % (citer(args[0]), rendus), "%s OK STATUS" % tag]

    @authentifie
    def _c_select(self, tag, args): return self._selectionner(tag, args, "SELECT")

    @authentifie
    def _c_examine(self, tag, args): return self._selectionner(tag, args, "EXAMINE")

    def _selectionner(self, tag, args, quoi):
        if not args: return ["%s BAD %s demande une boîte aux lettres" % (tag, quoi)]
        boite = self.vue.ouvrir(self.compte, args[0])
        if boite is None:
            self.boite = None
            return ["%s NO boîte aux lettres inconnue" % tag]
        self.boite, self.uids = boite, boite.uids
        return [
            "* %d EXISTS" % len(self.uids),
            "* 0 RECENT",                                   # on ne suit pas \\Recent : personne n'en dépend
            "* FLAGS (%s)" % " ".join(DRAPEAUX),
            "* OK [PERMANENTFLAGS ()] lecture seule",       # () = le client ne peut RIEN modifier
            "* OK [UIDVALIDITY %d] " % boite.uid_validity,
            "* OK [UIDNEXT %d] " % boite.uid_next,
            # LE CLIENT DOIT SAVOIR QU'IL NE PEUT PAS ÉCRIRE. Sans [READ-ONLY], Thunderbird croit
            # que ses STORE ont porté, et son affichage diverge de la réalité sans rien dire.
            "%s OK [READ-ONLY] %s" % (tag, quoi),
        ]

    @selectionne
    def _c_close(self, tag, args):
        self.boite, self.uids = None, []
        return ["%s OK CLOSE" % tag]

    @selectionne
    def _c_fetch(self, tag, args): return self._relever(tag, args, par_uid=False)

    @selectionne
    def _c_search(self, tag, args): return self._chercher(tag, args, par_uid=False)

    @authentifie
    def _c_uid(self, tag, args):
        """UID FETCH / UID SEARCH : la même chose, mais les nombres sont des UID."""
        if not args: return ["%s BAD UID demande une sous-commande" % tag]
        sous = args[0].upper()
        if self.boite is None: return ["%s BAD sélectionnez une boîte aux lettres d'abord" % tag]
        if sous == "FETCH": return self._relever(tag, args[1:], par_uid=True)
        if sous == "SEARCH": return self._chercher(tag, args[1:], par_uid=True)
        return ["%s BAD UID %s n'est pas servi (lecture seule)" % (tag, sous)]


def _correspond(nom: str, motif: str) -> bool:
    """le joker IMAP : `*` traverse la hiérarchie, `%` s'arrête au séparateur"""
    if motif in ("*", ""): return True
    import re
    # Construit l'expression caractère par caractère. Passer par `re.escape` puis remplacer les
    # jokers ne marche pas : depuis Python 3.7, `re.escape` n'échappe plus `%`, donc le
    # remplacement de `\%` ne trouvait rien et le motif « % » ne correspondait à RIEN.
    exp = "".join(".*" if c == "*" else "[^/]*" if c == "%" else re.escape(c) for c in motif)
    return re.match("^" + exp + "$", nom, re.I) is not None
