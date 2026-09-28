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
    """Le garde-fou de D180. Un client à qui l'on promet CONDSTORE sans le tenir corrompt son
    cache, et le symptôme apparaît des jours plus tard, chez lui."""
    s = Session(FausseVue(), magasin=None)
    annonce = " ".join(s.accueil())
    for jamais in ("CONDSTORE", "QRESYNC", "IDLE", "MOVE", "NOTIFY"):
        assert jamais not in annonce, "%s est annoncé alors qu'on ne le sert pas" % jamais
    assert "IMAP4rev1" in annonce
    servies = {n[3:].upper().replace("_", ".") for n in dir(Session) if n.startswith("_c_")}
    assert "FETCH" in servies and "SELECT" in servies
    for ecriture in ("STORE", "APPEND", "EXPUNGE", "COPY", "MOVE"):
        assert ecriture not in servies, "%s existe alors que le serveur est en LECTURE SEULE" % ecriture


def test_rien_avant_de_s_etre_connecte():
    s, (r,) = dialogue("a1 SELECT INBOX", connecte=False)[0], dialogue("a1 SELECT INBOX", connecte=False)[1][1:]
    assert r[0].startswith("a1 NO"), r
    assert dialogue("a2 LOGIN mathieu FAUX")[1][0][0].startswith("a2 NO")


def test_selectionner_annonce_la_lecture_seule():
    _, (r,) = dialogue("a1 SELECT INBOX")
    assert "* 3 EXISTS" in r
    assert "* OK [UIDVALIDITY 1234] " in r
    assert "* OK [UIDNEXT 10] " in r
    assert any("[PERMANENTFLAGS ()]" in l for l in r), "aucun drapeau modifiable : le client doit le savoir"
    assert r[-1].startswith("a1 OK [READ-ONLY]"), \
        "sans [READ-ONLY], le client croit que ses STORE ont porté et son affichage diverge en silence"


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
