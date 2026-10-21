"""D180 — le serveur IMAP en lecture seule : le DIALOGUE, éprouvé sans socket ni base.

La session ne connaît ni le réseau ni la base : on lui pose une vue doublée et on lui parle. C'est
ce qui permet d'éprouver les cas tordus — littéraux, crochets, `*` dans une plage, CAPABILITY
honnête — sans monter un serveur ni attendre.
"""
from __future__ import annotations
import pytest
from atombox.imap.protocol import LiteralNeeded, quote, parse_line, sequence
from atombox.imap.session import CAPABILITIES, Session


class FauxMessage:
    def __init__(self, uid, raw, flags=()):
        self.uid, self.raw, self.flags = uid, raw, list(flags)
        self.size, self.internal_date = len(raw), "18-Sep-2026 10:00:00 +0200"

    def envelope(self): return ["Fri, 18 Sep 2026 10:00:00 +0200", "Sujet %d" % self.uid, None, None, None, None, None, None, None, "<m%d@x>" % self.uid]
    def structure(self): return ["TEXT", "PLAIN", ["CHARSET", "UTF-8"], None, None, "7BIT", self.size, 1]

    def section_bytes(self, section):
        if section == "": return self.raw
        if section.upper() == "HEADER": return self.raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
        if section.upper() == "TEXT": return self.raw.split(b"\r\n\r\n", 1)[1]
        return None


class FausseBoite:
    def __init__(self, name, messages):
        self.name, self.attributes = name, ["\\HasNoChildren"]
        self.messages = {m.uid: m for m in messages}
        self.uids = sorted(self.messages)
        self.uid_validity, self.uid_next = 1234, (max(self.uids) + 1 if self.uids else 1)


class FausseVue:
    def __init__(self):
        raw = b"From: a@x.fr\r\nTo: contact@exemple.fr\r\nSubject: Devis\r\n\r\nBonjour.\r\n"
        self.b = {"INBOX": FausseBoite("INBOX", [FauxMessage(1, raw, ["\\Seen"]), FauxMessage(4, raw), FauxMessage(9, raw)]),
                  "Projets/Dupont": FausseBoite("Projets/Dupont", [])}

    def authenticate(self, ident, password): return "compte" if (ident, password) == ("mathieu", "secret") else None

    def rollback(self): self.rolled_back = getattr(self, "rolled_back", 0) + 1
    def mailboxes(self, compte): return list(self.b.values())
    def open_mailbox(self, compte, name): return self.b.get(name)
    def status(self, compte, name):
        b = self.b.get(name)
        return None if b is None else {"MESSAGES": len(b.uids), "UIDNEXT": b.uid_next, "UIDVALIDITY": b.uid_validity, "UNSEEN": 2}
    def message(self, mailbox, uid): return mailbox.messages.get(uid)
    def contains(self, mailbox, uid, field, needle): return needle in mailbox.messages[uid].raw.decode().lower()


def dialogue(*lines, connecte=True):
    s = Session(FausseVue(), store=None)
    out = [s.greeting()]
    if connecte: s.line("a0 LOGIN mathieu secret")
    for l in lines: out.append(s.line(l))
    return s, out[1:] if connecte else out


def test_la_capability_n_annonce_que_ce_qu_on_sert():
    """Le garde-fou de D180, dans les deux sens. Un client à qui l'on promet CONDSTORE sans le tenir
    CORROMPT SON CACHE, et le symptôme apparaît des jours plus tard, chez lui. Mais l'inverse coûte
    aussi : ne pas annoncer MOVE alors qu'on le sert, c'est laisser tous les clients faire
    COPY+STORE+EXPUNGE pour rien.

    Ce test tient donc les deux bouts, et il se maintient seul : il lit la liste annoncée."""
    s = Session(FausseVue(), store=None)
    annonce = " ".join(s.greeting())
    for jamais in ("CONDSTORE", "QRESYNC", "NOTIFY", "APPENDLIMIT"):     # IDLE : servi depuis RM3499
        assert jamais not in annonce, "%s est annoncé alors qu'on ne le sert pas" % jamais
    assert "IMAP4rev1" in annonce
    servies = {n[3:].upper().replace("_", ".") for n in dir(Session) if n.startswith("_c_")}
    assert "FETCH" in servies and "SELECT" in servies
    # ce qu'on annonce et qui est une COMMANDE doit exister
    for cap in ("MOVE",):
        assert cap in annonce and cap in servies, "%s est annoncé mais pas servi" % cap
    # APPEND est une commande de BASE d'IMAP4rev1 (RFC 3501 § 6.3.11) : il n'a pas de capacité à
    # lui, l'annoncer c'est annoncer rev1. Il est servi depuis RM3499 — c'est par lui que Thunderbird
    # enregistre un brouillon et range un envoyé.
    assert "APPEND" in servies


def test_rien_avant_de_s_etre_connecte():
    s, (r,) = dialogue("a1 SELECT INBOX", connecte=False)[0], dialogue("a1 SELECT INBOX", connecte=False)[1][1:]
    assert r[0].startswith("a1 NO"), r
    assert dialogue("a2 LOGIN mathieu FAUX")[1][0][0].startswith("a2 NO")


def test_select_ouvre_en_ecriture_et_examine_non():
    """SELECT ouvre en écriture, EXAMINE en lecture — et chacun l'ANNONCE.

    Les deux erreurs symétriques coûtent cher et sont silencieuses : annoncer `[READ-ONLY]` quand on
    accepte les STORE fait que le client n'essaie même pas ; annoncer `[READ-WRITE]` sans tenir fait
    qu'il croit ses écritures passées et diverge sans rien dire. Et `PERMANENTFLAGS` doit lister
    exactement ce qu'on sait écrire."""
    _, (r,) = dialogue("a1 SELECT INBOX")
    assert "* 3 EXISTS" in r
    assert "* OK [UIDVALIDITY 1234] " in r
    assert "* OK [UIDNEXT 10] " in r
    permanent = next(l for l in r if "PERMANENTFLAGS" in l)
    for d in ("\\Seen", "\\Flagged", "\\Deleted"):
        assert d in permanent, "%s est modifiable : le client doit le savoir" % d
    assert r[-1].startswith("a1 OK [READ-WRITE]")

    _, (r2,) = dialogue("a1 EXAMINE INBOX")
    assert any("[PERMANENTFLAGS ()]" in l for l in r2), "EXAMINE n'autorise RIEN, et le dit"
    assert r2[-1].startswith("a1 OK [READ-ONLY]")


def test_une_boite_ouverte_en_lecture_refuse_les_ecritures():
    """Un refus explicite, jamais un succès muet : le client doit pouvoir se replier."""
    for commande in ("a2 STORE 1 +FLAGS (\\Seen)", "a2 EXPUNGE", "a2 UID MOVE 1 Trash"):
        _, (_, r) = dialogue("a1 EXAMINE INBOX", commande)
        assert r[-1].startswith("a2 NO"), "%s accepté sur une boîte en lecture seule : %r" % (commande, r)


def test_uid_fetch_rend_l_octet_exact_et_toujours_l_uid():
    _, (_, r) = dialogue("a1 SELECT INBOX", "a2 UID FETCH 4 (BODY.PEEK[])")
    line = next(l for l in r if l.startswith("* "))
    assert "UID 4" in line, "un UID FETCH rend TOUJOURS l'UID, même non demandé — la RFC l'impose"
    assert "* 2 FETCH" in line, "le numéro de séquence, lui, est le rang : l'UID 4 est le 2e"
    body = line.split("{", 1)[1]
    size = int(body.split("}", 1)[0])
    assert body.split("\r\n", 1)[1].encode("latin-1")[:size].endswith(b"Bonjour.\r\n")


def test_l_etoile_est_le_plus_grand_uid_pas_l_infini():
    _, (_, r) = dialogue("a1 SELECT INBOX", "a2 UID FETCH 5:* (UID)")
    assert [l for l in r if l.startswith("* ")] and "UID 9" in " ".join(r)
    assert "UID 1" not in " ".join(l for l in r if l.startswith("* ")), "5:* ne remonte pas avant 5"
    # Piège de la RFC 3501 § 9 : une plage aux bornes INVERSÉES se lit à l'endroit. Comme `*` vaut
    # le plus grand UID, `12:*` sur une boîte dont le plus grand est 7 signifie `7:12` — et contient
    # donc 7. Ce n'est pas « rien », et un client qui demande `<dernier connu>:*` compte dessus pour
    # se resynchroniser : c'est ainsi qu'il redemande le dernier message qu'il a déjà.
    assert sequence("12:*", [3, 7], True) == [7], "12:* vaut 7:12 quand le plus grand UID est 7"
    assert sequence("5:1", [1, 3, 7], True) == [1, 3], "les bornes peuvent être données à l'envers"


def test_le_client_apprend_ce_qui_a_disparu():
    """Sans EXPUNGE, un message retiré chez nous reste affiché chez le client POUR TOUJOURS :
    rien ne le lui apprend. C'est ce qui s'est vu en produit — un message supprimé au webmail
    restait dans l'INBOX de Thunderbird."""
    v = FausseVue(); s = Session(v, store=None)
    s.line("a0 LOGIN mathieu secret")
    assert "* 3 EXISTS" in s.line("a1 SELECT INBOX")
    del v.b["INBOX"].messages[4]; v.b["INBOX"].uids = sorted(v.b["INBOX"].messages)
    r = s.line("a2 NOOP")
    assert r[0] == "* 2 EXPUNGE", "l'UID 4 était le 2e de la liste : c'est son RANG qu'on annonce, pas son UID"
    assert s.line("a3 NOOP") == ["a3 OK NOOP"], "et on ne le répète pas au tour suivant"


def test_les_rangs_d_expunge_s_entendent_sur_la_liste_qui_retrecit():
    """Retirer les 2e et 5e d'une liste de six, c'est annoncer « 2 » puis « 4 » — pas « 2 » puis
    « 5 ». Les annoncer sur la liste d'origine décale le client d'un cran par suppression, en
    silence : il croit avoir retiré le bon, et se trompe de message à chaque fois."""
    v = FausseVue()
    raw = b"From: a@x.fr\r\n\r\nx\r\n"
    v.b["INBOX"] = FausseBoite("INBOX", [FauxMessage(u, raw) for u in (1, 2, 3, 4, 5, 6)])
    s = Session(v, store=None); s.line("a0 LOGIN mathieu secret"); s.line("a1 SELECT INBOX")
    for u in (2, 5): del v.b["INBOX"].messages[u]
    v.b["INBOX"].uids = sorted(v.b["INBOX"].messages)
    assert [l for l in s.line("a2 NOOP") if "EXPUNGE" in l] == ["* 2 EXPUNGE", "* 4 EXPUNGE"]


def test_un_message_qui_ARRIVE_est_annonce_aussi():
    v = FausseVue(); s = Session(v, store=None)
    s.line("a0 LOGIN mathieu secret"); s.line("a1 SELECT INBOX")
    b = v.b["INBOX"]
    b.messages[12] = FauxMessage(12, b"From: a@x.fr\r\n\r\nneuf\r\n"); b.uids = sorted(b.messages)
    assert "* 4 EXISTS" in s.line("a2 NOOP")


def test_aucun_expunge_pendant_un_fetch_ou_un_search():
    """RFC 3501 § 5.2 : le client y compte par NUMÉRO DE SÉQUENCE, et retirer une ligne au milieu
    décale tout ce qu'il est en train de lire."""
    v = FausseVue(); s = Session(v, store=None)
    s.line("a0 LOGIN mathieu secret"); s.line("a1 SELECT INBOX")
    del v.b["INBOX"].messages[4]; v.b["INBOX"].uids = sorted(v.b["INBOX"].messages)
    for commande in ("a2 UID FETCH 1:* (UID)", "a3 UID SEARCH ALL"):
        assert not any("EXPUNGE" in l for l in s.line(commande)), commande


def test_un_critere_de_recherche_inconnu_est_une_ERREUR_pas_une_liste_vide():
    """Rendre « rien trouvé » ferait conclure à l'utilisateur que son message a disparu."""
    _, (_, r) = dialogue("a1 SELECT INBOX", "a2 UID SEARCH YOUNGER 3600")
    assert r[0].startswith("a2 NO"), r
    _, (_, ok) = dialogue("a1 SELECT INBOX", "a2 UID SEARCH FROM a@x.fr")
    assert ok[0].startswith("* SEARCH 1 4 9"), ok


def test_les_crochets_ne_sont_pas_des_listes():
    """`BODY.PEEK[HEADER.FIELDS (FROM TO)]` est UN élément — Thunderbird envoie exactement ça."""
    e = parse_line("a5 UID FETCH 1:* (UID BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT)])")
    assert e[4] == ["UID", "BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT)]"], e


def test_un_litteral_suspend_l_analyse():
    with pytest.raises(LiteralNeeded) as e:
        parse_line('a3 LOGIN "jean" {12}')
    assert e.value.n == 12
    s = Session(FausseVue(), store=None)
    assert s.line('a3 LOGIN mathieu {6}')[0].startswith("+ "), "le serveur demande la suite"
    assert s.line("secret")[0].startswith("a3 OK"), "et la recolle à la commande"


def test_on_ne_demande_pas_de_donnees_pour_une_commande_refusee():
    """Une commande refusée qui obtient un « + » fait envoyer le littéral au client, le serveur le
    jette, et les deux se désynchronisent : la commande suivante est lue comme le contenu du
    littéral. C'était `APPEND INBOX {3}` quand APPEND n'était pas servi ; c'est aujourd'hui toute
    commande inconnue — et APPEND AVANT connexion, qui ferait téléverser 25 Mo pour un NO."""
    s = Session(FausseVue(), store=None)
    r = s.line("a6 APPEND INBOX {3}")
    assert r[0].startswith("a6 NO") and s.awaiting_literal is None, ("APPEND avant connexion : refus "
                                                                     "SANS demande de données", r)
    s.line("a0 LOGIN mathieu secret")
    r = s.line("a7 SETMETADATA INBOX {3}")
    assert r[0].startswith("a7 BAD"), r
    assert s.awaiting_literal is None, "le serveur n'attend RIEN : la commande est refusée séance tenante"
    r = s.line("a9 APPEND INBOX {%d}" % (60 * 1024 * 1024))
    assert r[0].startswith("a9 NO") and "TOOBIG" in r[0] and s.awaiting_literal is None, \
        ("un littéral au-delà du plafond est refusé AVANT d'être lu", r)
    assert s.line("a8 NOOP")[0].startswith("a8 OK"), "et le dialogue continue, non désynchronisé"


def test_citer_bascule_en_litteral_quand_il_le_faut():
    assert quote(None) == "NIL" and quote(12) == "12"
    assert quote('il a dit "non"') == '"il a dit \\"non\\""'
    assert quote("deux\r\nlignes").startswith("{12}"), "une chaîne IMAP ne porte pas de CRLF"
    assert quote(["a", None]) == '("a" NIL)'


def test_list_et_le_joker():
    _, (r,) = dialogue('a1 LIST "" "*"')
    assert any('"INBOX"' in l for l in r) and any('"Projets/Dupont"' in l for l in r)
    _, (r2,) = dialogue('a1 LIST "" "%"')
    assert any('"INBOX"' in l for l in r2)
    assert not any("Projets/Dupont" in l for l in r2), "%% s'arrête au séparateur, * le traverse"


def test_une_erreur_n_empoisonne_pas_la_connexion():
    """LE DÉFAUT VU EN PRODUIT, et il est pire que celui qui l'a déclenché. Une écriture refusée
    laissait la session SQLAlchemy en transaction avortée : tout ce qui suivait levait
    `PendingRollbackError`, y compris un NOOP. Le client n'obtenait plus que « erreur interne »
    jusqu'à reconnexion, et il n'avait aucun moyen de le deviner ni de le réparer.

    On annule donc la transaction en même temps qu'on refuse la commande. Le client reçoit un NO
    sur ce qu'il a demandé, et la commande d'après fonctionne."""
    class VueQuiCasse(FausseVue):
        def message(self, mailbox, uid): raise RuntimeError("écriture refusée par la base")

    v = VueQuiCasse()
    s = Session(v, store=None)
    s.line("a0 LOGIN mathieu secret")
    s.line("a1 SELECT INBOX")
    r = s.line("a2 UID FETCH 1 (FLAGS)")
    assert r[-1].startswith("a2 NO"), r
    assert getattr(v, "rolled_back", 0) == 1, "la transaction doit être annulée, sinon la suite est perdue"
    assert s.line("a3 NOOP")[-1].startswith("a3 OK"), "et la commande suivante doit passer"


def test_un_message_de_la_corbeille_n_est_pas_masque():
    """LE DÉFAUT QUE SEUL UN VRAI CLIENT RÉVÈLE — et il rendait la corbeille VIDE à l'écran.

    `\\Deleted` veut dire en IMAP « marqué pour suppression, en attente d'EXPUNGE ». Thunderbird
    masque par défaut les messages qui le portent. On le servait sur tout message dont
    `exit_reason` valait `deleted` : le client recevait bien les trois messages de la corbeille, et
    les cachait tous les trois. Côté serveur tout était juste — la base, l'API, le FETCH. Il a fallu
    lire ce que le serveur met SUR LE FIL pour le voir.

    Chez nous un message de la corbeille n'attend rien : il y est, et il n'en sortira pas seul
    (D118). L'état est porté par la boîte aux lettres, pas par un drapeau (D183)."""
    from atombox.imap.view import ServedMessage

    class FauxComm:
        taille, date_recue, sujet, from_adresse, from_nom, corps_texte = 10, None, "x", "a@b.c", None, ""

    class FauxRatt:
        repondu_le, exit_reason, comm_id, boite_id = None, "deleted", None, None

    m = ServedMessage(1, FauxComm(), FauxRatt(), store=None, blob_ref=None)
    assert "\\Deleted" not in m.flags, \
        "un message de la corbeille porterait \\Deleted, donc Thunderbird le masquerait"

    # …mais le client doit pouvoir le POSER : c'est sa façon de dire « supprime »
    from atombox.imap.session import WRITABLE_FLAGS, FLAGS
    assert "\\Deleted" in WRITABLE_FLAGS and "\\Deleted" in FLAGS, \
        "le client doit pouvoir poser \\Deleted : c'est ce STORE qui déplace vers la corbeille"


# ── IDLE (RFC 2177, RM3499) ─────────────────────────────────────────────────────────────────────
def test_idle_attend_et_sort_sur_done():
    s = Session(FausseVue(), store=None)
    assert s.line("a0 IDLE")[0].startswith("a0 NO"), "IDLE avant connexion est refusé"
    s.line("a1 LOGIN mathieu secret"); s.line("a2 SELECT INBOX")
    r = s.line("a3 IDLE")
    assert r == [r[0]] and r[0].startswith("+ "), r
    assert s.idling == "a3"
    r = s.line("done")
    assert r[-1] == "a3 OK IDLE terminé" and s.idling is None, r
    assert s.line("a4 NOOP")[-1].startswith("a4 OK"), "le dialogue reprend normalement"


def test_idle_n_avale_pas_une_commande_comme_si_de_rien_n_etait():
    """Une ligne autre que DONE pendant IDLE est une faute du client : on le lui dit, on ne l'exécute
    pas sous une étiquette qu'on ignorerait."""
    s = Session(FausseVue(), store=None)
    s.line("a1 LOGIN mathieu secret"); s.line("a2 SELECT INBOX"); s.line("a3 IDLE")
    r = s.line("a4 LOGOUT")
    assert r == ["a3 BAD IDLE attendait DONE"] and s.idling is None and not s.done, r
