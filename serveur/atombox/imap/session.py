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
from .protocole import BesoinDeLitteral, citer, decouper, sequence
from ..journal import journal

log = journal("imap")

# CE QU'ON ANNONCE, ON LE TIENT. `MOVE` (RFC 6851) parce qu'un déplacement est UNE écriture chez
# nous et qu'un client qui l'a préfère toujours à COPY+STORE+EXPUNGE ; `SPECIAL-USE` (RFC 6154)
# parce que sans lui le client ne sait pas laquelle de nos boîtes est la corbeille, et s'en crée une.
# Toujours ni APPEND ni CONDSTORE/QRESYNC : on ne les annonce pas, donc on ne les sert pas.
# `LOGINDISABLED` n'y est pas car le transport est chiffré par le serveur qui nous précède ; hors
# TLS, l'écouteur l'ajoute.
CAPACITES = ["IMAP4rev1", "AUTH=PLAIN", "UIDPLUS", "MOVE", "SPECIAL-USE", "NAMESPACE"]

# Les drapeaux qu'un message peut porter chez nous. `\\Seen` et `\\Flagged` sont PERSONNELS depuis
# D175 ; `\\Deleted` n'est pas un drapeau posé à côté mais une TRANSITION vers la corbeille (D183) —
# la traduction est volontaire : un message supprimé doit se retrouver dans la corbeille.
DRAPEAUX = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]
# Ceux que le client peut MODIFIER — c'est ce que `PERMANENTFLAGS` annonce. `\\Answered` en fait
# partie parce que répondre est un acte collectif que nous savons enregistrer.
MODIFIABLES = ["\\Seen", "\\Flagged", "\\Answered", "\\Deleted"]


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
        self.lecture_seule = True     # SELECT ouvre en écriture, EXAMINE non (RFC 3501 § 6.3.2)
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
            # ON NE DEMANDE PAS DE DONNÉES POUR UNE COMMANDE QU'ON VA REFUSER. Sans ce contrôle,
            # `APPEND INBOX {3}` obtenait un « + » : le client envoyait son message, le serveur le
            # jetait, et les deux se désynchronisaient — la commande suivante était lue comme le
            # contenu du littéral. Sur un serveur en LECTURE SEULE, c'est aussi accepter un
            # téléversement de taille arbitraire pour rien.
            if not self._servie(texte):
                return ["%s BAD commande inconnue ou non servie" % (texte.split(" ", 1)[0] or "*")]
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
            # UNE ERREUR NE DOIT PAS EMPOISONNER LA CONNEXION. Une écriture qui échoue laisse la
            # session SQLAlchemy en transaction avortée : tout ce qui suit lève
            # `PendingRollbackError`, y compris un NOOP. C'est arrivé en produit — un seul
            # déplacement refusé, et le client n'obtenait plus que « erreur interne » jusqu'à ce
            # qu'il se reconnecte. Le client, lui, ne peut rien en déduire ni rien réparer.
            try:
                self.vue.annuler()
            except Exception:
                log.exception("l'annulation de la transaction a échoué elle aussi")
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

    def _servie(self, texte: str) -> bool:
        """la commande est-elle connue ? — lu sur la ligne BRUTE, avant tout littéral"""
        morceaux = texte.split(" ", 2)
        if len(morceaux) < 2: return False
        cmd = morceaux[1].upper()
        if cmd == "UID" and len(morceaux) > 2: cmd = "UID"
        return hasattr(self, "_c_" + cmd.lower().replace(".", "_"))

    # ── sans authentification ───────────────────────────────────────────────────────────────────
    def _c_capability(self, tag, args):
        return ["* CAPABILITY " + " ".join(self._capacites()), "%s OK CAPABILITY" % tag]

    def _c_noop(self, tag, args): return self._rafraichir() + ["%s OK NOOP" % tag]

    def _c_check(self, tag, args): return self._rafraichir() + ["%s OK CHECK" % tag]

    def _rafraichir(self) -> list[str]:
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
        if self.boite is None: return []
        frais = self.vue.ouvrir(self.compte, self.boite.nom)
        if frais is None: return []
        anciens, nouveaux = list(self.uids), list(frais.uids)
        presents, lignes = set(nouveaux), []
        courant = list(anciens)
        for uid in anciens:
            if uid not in presents:
                rang = courant.index(uid) + 1
                lignes.append("* %d EXPUNGE" % rang)
                courant.pop(rang - 1)
        if len(nouveaux) != len(courant):
            lignes.append("* %d EXISTS" % len(nouveaux))
        if lignes: log.info("boîte « %s » : %d disparu(s), %d au total", self.boite.nom,
                            len(anciens) - len(courant), len(nouveaux))
        self.boite, self.uids = frais, nouveaux
        return lignes

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
        self.lecture_seule = (quoi == "EXAMINE")
        # LE CLIENT DOIT SAVOIR CE QU'IL PEUT ÉCRIRE, exactement. Annoncer PERMANENTFLAGS () quand
        # on accepte les STORE ferait que Thunderbird n'essaierait même pas ; annoncer des drapeaux
        # qu'on ignore lui ferait croire que ses écritures ont porté. La liste est donc celle qu'on
        # tient, ni plus ni moins — et EXAMINE, lui, reste en lecture seule par définition.
        permanents = "" if self.lecture_seule else " ".join(MODIFIABLES)
        return [
            "* %d EXISTS" % len(self.uids),
            "* 0 RECENT",                                   # on ne suit pas \\Recent : personne n'en dépend
            "* FLAGS (%s)" % " ".join(DRAPEAUX),
            "* OK [PERMANENTFLAGS (%s)] " % permanents,
            "* OK [UIDVALIDITY %d] " % boite.uid_validity,
            "* OK [UIDNEXT %d] " % boite.uid_next,
            "%s OK [%s] %s" % (tag, "READ-ONLY" if self.lecture_seule else "READ-WRITE", quoi),
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
        if sous in ("MOVE", "COPY"): return self._deplacer(tag, args[1:], sous, par_uid=True)
        if sous == "STORE": return self._stocker(tag, args[1:], par_uid=True)
        return ["%s BAD UID %s n'est pas servi" % (tag, sous)]

    @selectionne
    def _c_move(self, tag, args): return self._deplacer(tag, args, "MOVE", par_uid=False)

    @selectionne
    def _c_copy(self, tag, args): return self._deplacer(tag, args, "COPY", par_uid=False)

    @selectionne
    def _c_store(self, tag, args): return self._stocker(tag, args, par_uid=False)

    @selectionne
    def _c_expunge(self, tag, args):
        """EXPUNGE — chez nous, il ne DÉTRUIT rien, et c'est voulu.

        Un message « supprimé » est dans la corbeille (D183), et un rattachement marqué supprimé
        n'est JAMAIS effacé (D118) : c'est ce qui rend la déchetterie lisible par domaine. EXPUNGE
        se contente donc d'annoncer ce qui a quitté la boîte sélectionnée — ce que le client attend
        de lui, et la seule partie de son contrat que nous puissions honnêtement tenir."""
        if self.lecture_seule: return ["%s NO boîte ouverte en lecture seule" % tag]
        return self._rafraichir() + ["%s OK EXPUNGE" % tag]

    # ── les écritures ───────────────────────────────────────────────────────────────────────────
    def _deplacer(self, tag, args, quoi, par_uid):
        """MOVE et COPY vers une autre boîte aux lettres.

        COPY FAIT LA MÊME CHOSE QUE MOVE, et il faut le dire : la clé d'un rattachement est
        (message, boîte), donc un message ne peut pas être dans deux boîtes aux lettres de la même
        adresse — un message reçu est dans une et une seule des cinq (D175 § 4). Refuser COPY
        laisserait sans recours les clients qui ne connaissent pas MOVE ; le traiter comme un
        déplacement leur donne le résultat attendu, et le `COPYUID` le leur dit sans ambiguïté."""
        if self.lecture_seule: return ["%s NO boîte ouverte en lecture seule" % tag]
        if len(args) < 2: return ["%s BAD %s demande un ensemble et une destination" % (tag, quoi)]
        vises = sequence(args[0], self.uids, par_uid)
        if not vises: return ["%s OK %s (rien à déplacer)" % (tag, quoi)]
        couples = self.vue.deplacer(self.compte, self.boite, vises, args[1])
        if couples is None:
            # TRYCREATE dit au client « crée-la puis recommence » ; sans lui, il abandonne
            # silencieusement et l'utilisateur voit son geste ne rien faire (RFC 3501 § 6.4.7).
            return ["%s NO [TRYCREATE] boîte aux lettres inconnue : %s" % (tag, args[1])]
        if not couples: return ["%s OK %s (aucun message visé)" % (tag, quoi)]
        dest = self.vue.ouvrir(self.compte, args[1])
        lignes = ["* OK [COPYUID %d %s %s] déplacé" % (
            dest.uid_validity if dest else 1,
            ",".join(str(a) for a, _ in couples), ",".join(str(b) for _, b in couples))]
        # L'EXPUNGE VIENT APRÈS le COPYUID (RFC 6851 § 3.3) : le client doit savoir où le message
        # est arrivé avant d'apprendre qu'il a quitté la boîte courante, sinon il le perd de vue.
        return lignes + self._rafraichir() + ["%s OK %s" % (tag, quoi)]

    def _stocker(self, tag, args, par_uid):
        """STORE ±FLAGS — et le silence de `.SILENT`, que les clients utilisent presque toujours."""
        if self.lecture_seule: return ["%s NO boîte ouverte en lecture seule" % tag]
        if len(args) < 3: return ["%s BAD STORE demande un ensemble, une opération et des drapeaux" % tag]
        vises = sequence(args[0], self.uids, par_uid)
        op = str(args[1]).upper()
        silencieux = op.endswith(".SILENT")
        if silencieux: op = op[:-len(".SILENT")]
        drapeaux = args[2] if isinstance(args[2], list) else [args[2]]
        drapeaux = [_normaliser_drapeau(d) for d in drapeaux]
        inconnus = [d for d in drapeaux if d not in DRAPEAUX]
        if inconnus:
            # On ne se tait pas sur ce qu'on ignore : un mot-clé qu'on jette en silence fait croire
            # au client qu'il est posé, et il l'affichera jusqu'à la fin des temps.
            log.info("STORE : drapeaux non servis, ignorés : %s", " ".join(inconnus))
        connus = [d for d in drapeaux if d in DRAPEAUX]
        if op == "FLAGS":
            # remplacement : ce qui n'est pas dans la liste est retiré
            ajouter, retirer = connus, [d for d in MODIFIABLES if d not in connus]
        elif op == "+FLAGS": ajouter, retirer = connus, []
        elif op == "-FLAGS": ajouter, retirer = [], connus
        else: return ["%s BAD opération de STORE inconnue : %s" % (tag, op)]
        self.vue.drapeaux(self.compte, self.boite, vises, ajouter, retirer)
        lignes = []
        if not silencieux:
            for uid in vises:
                m = self.vue.message(self.boite, uid)
                if m is None: continue
                rang = self.uids.index(uid) + 1 if uid in self.uids else None
                if rang: lignes.append("* %d FETCH (FLAGS (%s)%s)" % (
                    rang, " ".join(m.drapeaux), " UID %d" % uid if par_uid else ""))
        # PAS D'EXPUNGE ICI : la RFC 3501 § 5.2 l'interdit pendant un STORE — le client compte les
        # messages par numéro de séquence, et retirer une ligne au milieu décale ce qu'il lit. Un
        # `\\Deleted` posé fait bien quitter la boîte, mais il l'apprendra au NOOP suivant.
        return lignes + ["%s OK STORE" % tag]


def _correspond(nom: str, motif: str) -> bool:
    """le joker IMAP : `*` traverse la hiérarchie, `%` s'arrête au séparateur"""
    if motif in ("*", ""): return True
    import re
    # Construit l'expression caractère par caractère. Passer par `re.escape` puis remplacer les
    # jokers ne marche pas : depuis Python 3.7, `re.escape` n'échappe plus `%`, donc le
    # remplacement de `\%` ne trouvait rien et le motif « % » ne correspondait à RIEN.
    exp = "".join(".*" if c == "*" else "[^/]*" if c == "%" else re.escape(c) for c in motif)
    return re.match("^" + exp + "$", nom, re.I) is not None


def _normaliser_drapeau(d) -> str:
    """`\\seen` et `\\Seen` sont le même drapeau : la RFC les dit insensibles à la casse (§ 9).

    Sans ça, un client qui écrit en minuscules voyait ses STORE ignorés — et rien ne le lui disait."""
    s = str(d)
    for connu in DRAPEAUX:
        if s.lower() == connu.lower(): return connu
    return s
