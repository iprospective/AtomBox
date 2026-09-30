"""D180 — le serveur IMAP en lecture seule : le DIALOGUE, éprouvé sans socket ni base.

La session ne connaît ni le réseau ni la base : on lui pose une vue doublée et on lui parle. C'est
ce qui permet d'éprouver les cas tordus — littéraux, crochets, `*` dans une plage, CAPABILITY
honnête — sans monter un serveur ni attendre.
"""
from __future__ import annotations
import pytest
from atombox.imap.protocole import BesoinDeLitteral, citer, decouper, sequence
from atombox.imap.session import CAPACITES, Session


class FauxMessage:
    def __init__(self, uid, brut, drapeaux=()):
        self.uid, self.brut, self.drapeaux = uid, brut, list(drapeaux)
        self.taille, self.date_interne = len(brut), "18-Sep-2026 10:00:00 +0200"

    def enveloppe(self): return ["Fri, 18 Sep 2026 10:00:00 +0200", "Sujet %d" % self.uid, None, None, None, None, None, None, None, "<m%d@x>" % self.uid]
    def structure(self): return ["TEXT", "PLAIN", ["CHARSET", "UTF-8"], None, None, "7BIT", self.taille, 1]

    def octets(self, section):
        if section == "": return self.brut
        if section.upper() == "HEADER": return self.brut.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
        if section.upper() == "TEXT": return self.brut.split(b"\r\n\r\n", 1)[1]
        return None


class FausseBoite:
    def __init__(self, nom, messages):
        self.nom, self.attributs = nom, ["\\HasNoChildren"]
        self.messages = {m.uid: m for m in messages}
        self.uids = sorted(self.messages)
        self.uid_validity, self.uid_next = 1234, (max(self.uids) + 1 if self.uids else 1)


class FausseVue:
    def __init__(self):
        brut = b"From: a@x.fr\r\nTo: contact@exemple.fr\r\nSubject: Devis\r\n\r\nBonjour.\r\n"
        self.b = {"INBOX": FausseBoite("INBOX", [FauxMessage(1, brut, ["\\Seen"]), FauxMessage(4, brut), FauxMessage(9, brut)]),
                  "Projets/Dupont": FausseBoite("Projets/Dupont", [])}

    def authentifier(self, ident, mdp): return "compte" if (ident, mdp) == ("mathieu", "secret") else None

    def rollback(self): self.annule = getattr(self, "annule", 0) + 1
    def boites(self, compte): return list(self.b.values())
    def ouvrir(self, compte, nom): return self.b.get(nom)
    def etat(self, compte, nom):
        b = self.b.get(nom)
        return None if b is None else {"MESSAGES": len(b.uids), "UIDNEXT": b.uid_next, "UIDVALIDITY": b.uid_validity, "UNSEEN": 2}
    def message(self, boite, uid): return boite.messages.get(uid)
    def contient(self, boite, uid, champ, aiguille): return aiguille in boite.messages[uid].brut.decode().lower()


def dialogue(*lignes, connecte=True):
    s = Session(FausseVue(), magasin=None)
    sortie = [s.accueil()]
    if connecte: s.ligne("a0 LOGIN mathieu secret")
    for l in lignes: sortie.append(s.ligne(l))
    return s, sortie[1:] if connecte else sortie


def test_la_capability_n_annonce_que_ce_qu_on_sert():
    """Le garde-fou de D180, dans les deux sens. Un client à qui l'on promet CONDSTORE sans le tenir
    CORROMPT SON CACHE, et le symptôme apparaît des jours plus tard, chez lui. Mais l'inverse coûte
    aussi : ne pas annoncer MOVE alors qu'on le sert, c'est laisser tous les clients faire
    COPY+STORE+EXPUNGE pour rien.

    Ce test tient donc les deux bouts, et il se maintient seul : il lit la liste annoncée."""
    s = Session(FausseVue(), magasin=None)
    annonce = " ".join(s.accueil())
    for jamais in ("CONDSTORE", "QRESYNC", "IDLE", "NOTIFY", "APPENDLIMIT"):
        assert jamais not in annonce, "%s est annoncé alors qu'on ne le sert pas" % jamais
    assert "IMAP4rev1" in annonce
    servies = {n[3:].upper().replace("_", ".") for n in dir(Session) if n.startswith("_c_")}
    assert "FETCH" in servies and "SELECT" in servies
    # ce qu'on annonce et qui est une COMMANDE doit exister
    for cap in ("MOVE",):
        assert cap in annonce and cap in servies, "%s est annoncé mais pas servi" % cap
    # APPEND n'est pas annoncé, donc pas servi : on ne prend pas de message par IMAP (D140b)
    assert "APPEND" not in servies, "APPEND existe alors qu'on n'accepte pas de dépôt par IMAP"


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
    permanents = next(l for l in r if "PERMANENTFLAGS" in l)
    for d in ("\\Seen", "\\Flagged", "\\Deleted"):
        assert d in permanents, "%s est modifiable : le client doit le savoir" % d
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
    ligne = next(l for l in r if l.startswith("* "))
    assert "UID 4" in ligne, "un UID FETCH rend TOUJOURS l'UID, même non demandé — la RFC l'impose"
    assert "* 2 FETCH" in ligne, "le numéro de séquence, lui, est le rang : l'UID 4 est le 2e"
    corps = ligne.split("{", 1)[1]
    taille = int(corps.split("}", 1)[0])
    assert corps.split("\r\n", 1)[1].encode("latin-1")[:taille].endswith(b"Bonjour.\r\n")


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
    v = FausseVue(); s = Session(v, magasin=None)
    s.ligne("a0 LOGIN mathieu secret")
    assert "* 3 EXISTS" in s.ligne("a1 SELECT INBOX")
    del v.b["INBOX"].messages[4]; v.b["INBOX"].uids = sorted(v.b["INBOX"].messages)
    r = s.ligne("a2 NOOP")
    assert r[0] == "* 2 EXPUNGE", "l'UID 4 était le 2e de la liste : c'est son RANG qu'on annonce, pas son UID"
    assert s.ligne("a3 NOOP") == ["a3 OK NOOP"], "et on ne le répète pas au tour suivant"


def test_les_rangs_d_expunge_s_entendent_sur_la_liste_qui_retrecit():
    """Retirer les 2e et 5e d'une liste de six, c'est annoncer « 2 » puis « 4 » — pas « 2 » puis
    « 5 ». Les annoncer sur la liste d'origine décale le client d'un cran par suppression, en
    silence : il croit avoir retiré le bon, et se trompe de message à chaque fois."""
    v = FausseVue()
    brut = b"From: a@x.fr\r\n\r\nx\r\n"
    v.b["INBOX"] = FausseBoite("INBOX", [FauxMessage(u, brut) for u in (1, 2, 3, 4, 5, 6)])
    s = Session(v, magasin=None); s.ligne("a0 LOGIN mathieu secret"); s.ligne("a1 SELECT INBOX")
    for u in (2, 5): del v.b["INBOX"].messages[u]
    v.b["INBOX"].uids = sorted(v.b["INBOX"].messages)
    assert [l for l in s.ligne("a2 NOOP") if "EXPUNGE" in l] == ["* 2 EXPUNGE", "* 4 EXPUNGE"]


def test_un_message_qui_ARRIVE_est_annonce_aussi():
    v = FausseVue(); s = Session(v, magasin=None)
    s.ligne("a0 LOGIN mathieu secret"); s.ligne("a1 SELECT INBOX")
    b = v.b["INBOX"]
    b.messages[12] = FauxMessage(12, b"From: a@x.fr\r\n\r\nneuf\r\n"); b.uids = sorted(b.messages)
    assert "* 4 EXISTS" in s.ligne("a2 NOOP")


def test_aucun_expunge_pendant_un_fetch_ou_un_search():
    """RFC 3501 § 5.2 : le client y compte par NUMÉRO DE SÉQUENCE, et retirer une ligne au milieu
    décale tout ce qu'il est en train de lire."""
    v = FausseVue(); s = Session(v, magasin=None)
    s.ligne("a0 LOGIN mathieu secret"); s.ligne("a1 SELECT INBOX")
    del v.b["INBOX"].messages[4]; v.b["INBOX"].uids = sorted(v.b["INBOX"].messages)
    for commande in ("a2 UID FETCH 1:* (UID)", "a3 UID SEARCH ALL"):
        assert not any("EXPUNGE" in l for l in s.ligne(commande)), commande


def test_un_critere_de_recherche_inconnu_est_une_ERREUR_pas_une_liste_vide():
    """Rendre « rien trouvé » ferait conclure à l'utilisateur que son message a disparu."""
    _, (_, r) = dialogue("a1 SELECT INBOX", "a2 UID SEARCH YOUNGER 3600")
    assert r[0].startswith("a2 NO"), r
    _, (_, ok) = dialogue("a1 SELECT INBOX", "a2 UID SEARCH FROM a@x.fr")
    assert ok[0].startswith("* SEARCH 1 4 9"), ok


def test_les_crochets_ne_sont_pas_des_listes():
    """`BODY.PEEK[HEADER.FIELDS (FROM TO)]` est UN élément — Thunderbird envoie exactement ça."""
    e = decouper("a5 UID FETCH 1:* (UID BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT)])")
    assert e[4] == ["UID", "BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT)]"], e


def test_un_litteral_suspend_l_analyse():
    with pytest.raises(BesoinDeLitteral) as e:
        decouper('a3 LOGIN "jean" {12}')
    assert e.value.n == 12
    s = Session(FausseVue(), magasin=None)
    assert s.ligne('a3 LOGIN mathieu {6}')[0].startswith("+ "), "le serveur demande la suite"
    assert s.ligne("secret")[0].startswith("a3 OK"), "et la recolle à la commande"


def test_on_ne_demande_pas_de_donnees_pour_une_commande_refusee():
    """`APPEND INBOX {3}` obtenait un « + » : le client envoyait son message, le serveur le jetait,
    et les deux se désynchronisaient — la commande suivante était lue comme le contenu du littéral.
    Sur un serveur en lecture seule, c'est aussi accepter un téléversement de taille arbitraire."""
    s = Session(FausseVue(), magasin=None)
    s.ligne("a0 LOGIN mathieu secret")
    r = s.ligne("a7 APPEND INBOX {3}")
    assert r[0].startswith("a7 BAD"), r
    assert s.attente_litteral is None, "le serveur n'attend RIEN : la commande est refusée séance tenante"
    assert s.ligne("a8 NOOP")[0].startswith("a8 OK"), "et le dialogue continue, non désynchronisé"


def test_citer_bascule_en_litteral_quand_il_le_faut():
    assert citer(None) == "NIL" and citer(12) == "12"
    assert citer('il a dit "non"') == '"il a dit \\"non\\""'
    assert citer("deux\r\nlignes").startswith("{12}"), "une chaîne IMAP ne porte pas de CRLF"
    assert citer(["a", None]) == '("a" NIL)'


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
        def message(self, boite, uid): raise RuntimeError("écriture refusée par la base")

    v = VueQuiCasse()
    s = Session(v, magasin=None)
    s.ligne("a0 LOGIN mathieu secret")
    s.ligne("a1 SELECT INBOX")
    r = s.ligne("a2 UID FETCH 1 (FLAGS)")
    assert r[-1].startswith("a2 NO"), r
    assert getattr(v, "annule", 0) == 1, "la transaction doit être annulée, sinon la suite est perdue"
    assert s.ligne("a3 NOOP")[-1].startswith("a3 OK"), "et la commande suivante doit passer"


def test_un_message_de_la_corbeille_n_est_pas_masque():
    """LE DÉFAUT QUE SEUL UN VRAI CLIENT RÉVÈLE — et il rendait la corbeille VIDE à l'écran.

    `\\Deleted` veut dire en IMAP « marqué pour suppression, en attente d'EXPUNGE ». Thunderbird
    masque par défaut les messages qui le portent. On le servait sur tout message dont
    `exit_reason` valait `deleted` : le client recevait bien les trois messages de la corbeille, et
    les cachait tous les trois. Côté serveur tout était juste — la base, l'API, le FETCH. Il a fallu
    lire ce que le serveur met SUR LE FIL pour le voir.

    Chez nous un message de la corbeille n'attend rien : il y est, et il n'en sortira pas seul
    (D118). L'état est porté par la boîte aux lettres, pas par un drapeau (D183)."""
    from atombox.imap.vue import MessageServi

    class FauxComm:
        taille, date_recue, sujet, from_adresse, from_nom, corps_texte = 10, None, "x", "a@b.c", None, ""

    class FauxRatt:
        repondu_le, exit_reason, comm_id, boite_id = None, "deleted", None, None

    m = MessageServi(1, FauxComm(), FauxRatt(), magasin=None, blob_ref=None)
    assert "\\Deleted" not in m.drapeaux, \
        "un message de la corbeille porterait \\Deleted, donc Thunderbird le masquerait"

    # …mais le client doit pouvoir le POSER : c'est sa façon de dire « supprime »
    from atombox.imap.session import WRITABLE_FLAGS, DRAPEAUX
    assert "\\Deleted" in WRITABLE_FLAGS and "\\Deleted" in DRAPEAUX, \
        "le client doit pouvoir poser \\Deleted : c'est ce STORE qui déplace vers la corbeille"
