"""RM3499 — Dovecot comme JUGE de la structure MIME que l'on sert.

La leçon du certificat (21/10) : un test éprouvé par un client plus tolérant que celui de
l'utilisateur ne prouve rien. Pour la structure MIME, le juge le plus exigeant à portée de main est
Dovecot — le serveur que rencontrent la plupart des clients IMAP, et dont Thunderbird a l'habitude.
On lui donne les MÊMES octets dans une boîte jetable, et l'on compare ce qu'il sert à ce que nous
servons : BODYSTRUCTURE, BODY, ENVELOPE et une série de sections, au caractère près.

Le test s'ignore si le binaire de Dovecot est absent (en CI : l'image n'en a pas). Il tourne sur les
postes et sur la machine servie, où il a été écrit.
"""
from __future__ import annotations
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

from atombox.imap import mime

DOVECOT = "/usr/lib/dovecot/imap"
ICI = pathlib.Path(__file__).resolve().parent

SECTIONS = ["HEADER", "TEXT", "1", "1.MIME", "2", "2.MIME", "1.1", "1.2", "3", "3.HEADER", "3.TEXT",
            "3.1", "HEADER.FIELDS (SUBJECT FROM)", "HEADER.FIELDS.NOT (SUBJECT)"]


def _corpus():
    import sys
    sys.path.insert(0, str(ICI))
    from test_imap_mime import MESSAGE
    out = [("multipart-composite", MESSAGE)]
    for f in sorted((ICI / "fixtures").glob("*.eml")):
        out.append((f.name, f.read_bytes()))
    return out


def _dovecot(raw_messages: list[bytes], commands: list[str]) -> str:
    """lance le binaire imap de Dovecot en PREAUTH sur une boîte maildir jetable"""
    d = tempfile.mkdtemp(prefix="dvc", dir="/tmp")          # court : un socket Unix plafonne à 108 caractères
    try:
        for sub in ("mail/new", "mail/cur", "mail/tmp", "run", "state"):
            os.makedirs(os.path.join(d, sub))
        for i, raw in enumerate(raw_messages, 1):
            pathlib.Path(d, "mail", "new", "%d.%d.local" % (1000 + i, i)).write_bytes(raw)
        conf = pathlib.Path(d, "dovecot.conf")
        conf.write_text("base_dir = %s/run\nstate_dir = %s/state\nlog_path = /dev/null\n"
                        "mail_location = maildir:%s/mail\nssl = no\nprotocols = imap\n"
                        "default_internal_user = %s\ndefault_login_user = %s\n"
                        % (d, d, d, os.environ.get("USER") or "nobody", os.environ.get("USER") or "nobody"))
        script = "".join("t%d %s\r\n" % (i, c) for i, c in enumerate(["SELECT INBOX"] + commands + ["LOGOUT"]))
        r = subprocess.run([DOVECOT, "-c", str(conf)], input=script.encode(), capture_output=True,
                           timeout=30, env={"HOME": d, "USER": os.environ.get("USER", "nobody"), "PATH": "/usr/bin:/bin"})
        return r.stdout.decode("latin-1")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _item(response: str, name: str):
    """la valeur d'un élément de FETCH dans la réponse — parenthèses, chaînes et littéraux compris"""
    i = response.find(name + " ")
    if i < 0: return None
    i += len(name) + 1
    if response.startswith("{", i):
        n = int(response[i + 1:response.index("}", i)])
        start = response.index("\r\n", i) + 2
        return response[start:start + n]
    depth, j, q = 0, i, False
    while j < len(response):
        c = response[j]
        if q:
            if c == "\\": j += 1
            elif c == '"': q = False
        elif c == '"': q = True
        elif c == "{":
            n = int(response[j + 1:response.index("}", j)]); j = response.index("\r\n", j) + 1 + n
        elif c == "(": depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0: return response[i:j + 1]
        elif depth == 0 and c in " \r":
            return response[i:j]
        j += 1
    return response[i:]


pytestmark = pytest.mark.skipif(not os.access(DOVECOT, os.X_OK), reason="Dovecot absent : pas de juge ici")


@pytest.mark.parametrize("nom,raw", _corpus(), ids=[n for n, _ in _corpus()])
def test_la_structure_est_celle_que_sert_dovecot(nom, raw):
    out = _dovecot([raw], ["FETCH 1 (BODYSTRUCTURE)", "FETCH 1 (BODY)"])
    arbre = mime.Part(raw)
    assert _item(out, "BODYSTRUCTURE") == mime.structure(arbre, True), nom
    assert _item(out, "BODY") == mime.structure(arbre, False), nom


@pytest.mark.parametrize("nom,raw", _corpus(), ids=[n for n, _ in _corpus()])
def test_l_enveloppe_est_celle_que_sert_dovecot(nom, raw):
    out = _dovecot([raw], ["FETCH 1 (ENVELOPE)"])
    assert _item(out, "ENVELOPE") == mime.envelope(mime.Part(raw)), nom


@pytest.mark.parametrize("nom,raw", _corpus(), ids=[n for n, _ in _corpus()])
def test_chaque_section_rend_les_memes_octets_que_dovecot(nom, raw):
    out = _dovecot([raw], ["FETCH 1 (BODY.PEEK[%s])" % s for s in SECTIONS])
    arbre = mime.Part(raw)
    for s in SECTIONS:
        # Dovecot rend une section absente comme une chaîne VIDE ; nous ne la rendons pas du tout
        # (None). Le client ne demande que ce que la structure annonce : on compare ce qui existe.
        theirs = _item(out, "BODY[%s]" % s)
        ours = mime.section(arbre, raw, s)
        if ours is None:
            assert theirs in (None, "", "NIL"), "%s : Dovecot sert %r, nous rien" % (s, (theirs or "")[:60])
            continue
        assert theirs == ours.decode("latin-1"), "%s / %s : les octets diffèrent" % (nom, s)


# ── SEARCH : les mêmes réponses que Dovecot ─────────────────────────────────────────────────────
# Les critères qui dépendent de ce que nous SERVONS et Dovecot non sont tenus à part : RECENT, NEW et
# OLD (Dovecot pose \Recent sur une boîte neuve, nous jamais — c'est voulu, cf. `imap/search.py`).
CRITERES = [
    "ALL", "FROM fournisseur", "FROM FOURNISSEUR", "TO exemple.fr", "CC client", "BCC personne",
    "SUBJECT Commande", "SUBJECT commande", "SUBJECT Devis", "BODY Bonjour", "BODY bonjour", "TEXT Bonjour",
    "TEXT Message-ID", "HEADER Message-ID fournisseur", "HEADER List-Id \"\"", "HEADER X-Inexistant \"\"",
    "LARGER 500", "SMALLER 1000", "LARGER 100000", "NOT FROM fournisseur", "OR SUBJECT Devis SUBJECT Commande",
    "(FROM fournisseur SUBJECT Commande)", "NOT (OR FROM fournisseur TO exemple.fr)",
    "SENTSINCE 1-Jan-2026", "SENTBEFORE 1-Jan-2026", "SENTON 18-Sep-2026", "SENTSINCE 21-Oct-2026",
    "SINCE 15-Mar-2026", "BEFORE 15-Mar-2026", "ON 15-Mar-2026", "SINCE 16-Mar-2026",
    "UNSEEN", "SEEN", "UNDELETED", "DELETED", "FLAGGED", "UNFLAGGED", "UNANSWERED", "ANSWERED",
    "DRAFT", "UNDRAFT", "KEYWORD perso", "UNKEYWORD perso",
    "1:3", "2,4", "3:*", "UID 1:2", "UID 4:*", "NOT 1", "OR 1 7",
]
# midi UTC : la date interne tombe le même jour quel que soit le fuseau du serveur de Dovecot
INTERNE = 1773576000      # 2026-03-15 12:00:00 UTC


def _dovecot_boite(raws, commands):
    """comme `_dovecot`, mais avec une DATE INTERNE fixée (la date du fichier, pour un maildir)"""
    d = tempfile.mkdtemp(prefix="dvs", dir="/tmp")
    try:
        for sub in ("mail/new", "mail/cur", "mail/tmp", "run", "state"):
            os.makedirs(os.path.join(d, sub))
        for i, raw in enumerate(raws, 1):
            f = pathlib.Path(d, "mail", "cur", "%d.%d.local:2," % (1000 + i, i))
            f.write_bytes(raw); os.utime(f, (INTERNE, INTERNE))
        conf = pathlib.Path(d, "dovecot.conf")
        u = os.environ.get("USER") or "nobody"
        conf.write_text("base_dir = %s/run\nstate_dir = %s/state\nlog_path = /dev/null\n"
                        "mail_location = maildir:%s/mail\nssl = no\nprotocols = imap\n"
                        "default_internal_user = %s\ndefault_login_user = %s\n" % (d, d, d, u, u))
        script = "".join("t%d %s\r\n" % (i, c) for i, c in enumerate(["SELECT INBOX"] + commands + ["LOGOUT"]))
        r = subprocess.run([DOVECOT, "-c", str(conf)], input=script.encode(), capture_output=True, timeout=30,
                           env={"HOME": d, "USER": u, "PATH": "/usr/bin:/bin"})
        return r.stdout.decode("latin-1")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_la_recherche_trouve_ce_que_trouve_dovecot():
    from datetime import datetime, timezone
    from atombox.imap import search as S
    from atombox.imap.protocol import parse_line
    raws = [raw for _, raw in _corpus()]
    out = _dovecot_boite(raws, ["SEARCH " + c for c in CRITERES])
    # Dovecot traite les commandes EN LOT : toutes les lignes « * SEARCH » d'abord, dans l'ordre des
    # commandes, puis les réponses étiquetées. Une commande refusée (BAD) n'a pas de ligne : on
    # l'associe donc par l'ordre, en sautant celles que Dovecot a refusées.
    lignes = [l for l in out.split("\r\n") if l.startswith("* SEARCH")]
    refusees = {int(m) for m in re.findall(r"\r\nt(\d+) (?:BAD|NO)", "\r\n" + out)}
    theirs, k = {}, 0
    for i, c in enumerate(CRITERES, 1):
        if i in refusees: theirs[c] = None; continue
        theirs[c] = [int(x) for x in lignes[k][len("* SEARCH"):].split()]; k += 1
    uids = list(range(1, len(raws) + 1))
    interne = datetime.fromtimestamp(INTERNE, tz=timezone.utc)
    ecarts = []
    for c in CRITERES:
        tree = S.parse(parse_line(c), uids)
        ours = [u for u in uids if S.matches(tree, S.Message(u, uids, raws[u - 1], (), interne, len(raws[u - 1])))]
        if ours != theirs[c]: ecarts.append("%-40s Dovecot %s | nous %s" % (c, theirs[c], ours))
    assert not ecarts, "la recherche diffère de Dovecot :\n" + "\n".join(ecarts)
