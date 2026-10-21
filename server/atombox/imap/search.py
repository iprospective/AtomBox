"""LA RECHERCHE IMAP (RFC 3501 § 6.4.4) — tous les critères, et leur grammaire.

`IMAP4rev1` promet SEARCH avec TOUS ses critères : l'annoncer en n'en servant qu'une partie, c'est
annoncer ce qu'on ne tient pas. Ce module les sert tous, sur une façade de message qui ne dépend ni
de la base ni du socket — c'est ce qui permet de l'éprouver contre Dovecot (`tests/test_imap_dovecot.py`).

Les critères qui portent sur ce que nous ne servons pas répondent comme ce que nous servons :
`\\Deleted`, `\\Draft`, `\\Recent` et les mots-clés ne sont jamais posés chez nous (D183 : supprimer,
c'est être dans la corbeille) — DELETED, DRAFT, RECENT, NEW et KEYWORD ne trouvent donc rien, et
leurs contraires trouvent tout. C'est cohérent avec FETCH FLAGS, ce qui compte plus que tout : un
client qui cherche UNSEEN doit trouver exactement les messages qu'il affiche en gras.
"""
from __future__ import annotations
import email.header
import email.utils
import re
from datetime import date, datetime

_MOIS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                                      "oct", "nov", "dec"), 1)}


class SearchError(ValueError):
    """un critère illisible : la session répond BAD, jamais une liste vide qui ferait croire à rien"""


def parse_date(v) -> date:
    """« 1-Feb-1994 » (RFC 3501 § 9, date) — à la main : `%b` suit la locale du processus"""
    m = re.match(r"^\s*(\d{1,2})-([A-Za-z]{3})-(\d{4})\s*$", str(v))
    if not m or m.group(2).lower() not in _MOIS: raise SearchError("date illisible : %s" % v)
    try:
        return date(int(m.group(3)), _MOIS[m.group(2).lower()], int(m.group(1)))
    except ValueError:
        raise SearchError("date impossible : %s" % v)


def parse(args: list, uids: list[int]):
    """les arguments de SEARCH → un arbre de critères. Plusieurs critères à la suite : ET."""
    items = list(args)
    keys = []
    while items:
        keys.append(_key(items, uids))
    return ("AND", keys)


def _key(items: list, uids):
    if not items: raise SearchError("critère attendu")
    tok = items.pop(0)
    if isinstance(tok, list):                       # ( critères ) : un ET
        sub, keys = list(tok), []
        while sub: keys.append(_key(sub, uids))
        return ("AND", keys)
    t = str(tok).upper()
    def arg():
        if not items: raise SearchError("%s attend un argument" % t)
        return items.pop(0)
    if t in ("ALL", "ANSWERED", "DELETED", "DRAFT", "FLAGGED", "NEW", "OLD", "RECENT", "SEEN",
             "UNANSWERED", "UNDELETED", "UNDRAFT", "UNFLAGGED", "UNSEEN"):
        return (t,)
    if t in ("BCC", "BODY", "CC", "FROM", "SUBJECT", "TEXT", "TO", "KEYWORD", "UNKEYWORD"):
        return (t, str(arg()))
    if t in ("BEFORE", "ON", "SINCE", "SENTBEFORE", "SENTON", "SENTSINCE"):
        return (t, parse_date(arg()))
    if t in ("LARGER", "SMALLER"):
        v = str(arg())
        if not v.isdigit(): raise SearchError("%s attend un nombre" % t)
        return (t, int(v))
    if t == "HEADER":
        name = str(arg()); return ("HEADER", name, str(arg()))
    if t == "NOT":
        return ("NOT", _key(items, uids))
    if t == "OR":
        a = _key(items, uids); return ("OR", a, _key(items, uids))
    if t == "UID":
        return ("UID", str(arg()))
    if re.match(r"^[\d*:,]+$", t):
        return ("SEQ", t)
    raise SearchError("critère inconnu : %s" % t)


def _decoded(value: str) -> str:
    """un en-tête, ses mots encodés (RFC 2047) DÉCODÉS — on cherche ce que l'utilisateur lit, pas
    « =?utf-8?q?Devis?= »"""
    try:
        parts = email.header.decode_header(value)
        return "".join(p.decode(c or "latin-1", "replace") if isinstance(p, bytes) else p for p, c in parts)
    except Exception:
        return value


def matches(key, m) -> bool:
    """`m` : une façade — seq, uid, flags, internal (datetime), size, header(nom), headers_text(),
    body_text(). Le texte est comparé sans casse, en sous-chaîne (RFC 3501 § 6.4.4)."""
    op = key[0]
    if op == "AND": return all(matches(k, m) for k in key[1])
    if op == "OR": return matches(key[1], m) or matches(key[2], m)
    if op == "NOT": return not matches(key[1], m)
    if op == "ALL": return True
    if op in ("SEEN", "UNSEEN"): return ("\\Seen" in m.flags) == (op == "SEEN")
    if op in ("FLAGGED", "UNFLAGGED"): return ("\\Flagged" in m.flags) == (op == "FLAGGED")
    if op in ("ANSWERED", "UNANSWERED"): return ("\\Answered" in m.flags) == (op == "ANSWERED")
    if op in ("DELETED", "DRAFT", "RECENT", "NEW"): return False     # jamais posés chez nous
    if op in ("UNDELETED", "UNDRAFT", "OLD"): return True
    if op == "KEYWORD": return False
    if op == "UNKEYWORD": return True
    if op in ("FROM", "TO", "CC", "BCC", "SUBJECT"):
        return _contains(_decoded(m.header(op) or ""), key[1]) if m.header(op) is not None else False
    if op == "HEADER":
        v = m.header(key[1])
        if v is None: return False
        return key[2] == "" or _contains(_decoded(v), key[2])
    if op == "BODY": return _contains(m.body_text(), key[1])
    if op == "TEXT": return _contains(m.headers_text() + "\n" + m.body_text(), key[1])
    if op in ("BEFORE", "ON", "SINCE"):
        return _compare(op, m.internal.date() if m.internal else None, key[1])
    if op in ("SENTBEFORE", "SENTON", "SENTSINCE"):
        return _compare(op[4:], _sent_date(m.header("date")), key[1])
    if op == "LARGER": return m.size > key[1]
    if op == "SMALLER": return m.size < key[1]
    if op == "UID":
        from .protocol import sequence
        return m.uid in set(sequence(key[1], m.all_uids, True))
    if op == "SEQ":
        from .protocol import sequence
        return m.uid in set(sequence(key[1], m.all_uids, False))
    raise SearchError("critère inconnu : %s" % op)


def _contains(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _compare(op, d, ref) -> bool:
    if d is None: return False
    if op == "BEFORE": return d < ref
    if op == "ON": return d == ref
    return d >= ref                                   # SINCE : à partir de ce jour, inclus


def _sent_date(v):
    """la date du message selon SON en-tête Date, dans SON fuseau — « en ignorant l'heure et le fuseau »
    (RFC 3501 § 6.4.4) veut dire : le jour du calendrier qu'il porte"""
    if not v: return None
    try:
        return email.utils.parsedate_to_datetime(v).date()
    except Exception:
        return None


class Message:
    """la façade qu'interroge `matches` — le même objet pour le serveur et pour le juge (Dovecot).

    Les octets ne sont lus qu'au besoin : chercher UNSEEN dans dix mille messages ne doit pas les
    décompresser tous."""

    def __init__(self, uid: int, all_uids: list[int], raw, flags=(), internal=None, size=None):
        self.uid, self.all_uids, self.flags, self.internal = uid, all_uids, list(flags), internal
        self._raw_src, self._size = raw, size
        self._tree = self._body = None

    @property
    def raw(self) -> bytes:
        if callable(self._raw_src): self._raw_src = self._raw_src() or b""
        return self._raw_src or b""

    @property
    def size(self) -> int:
        return self._size if self._size is not None else len(self.raw)

    def _parsed(self):
        if self._tree is None:
            from .mime import Part
            self._tree = Part(self.raw)
        return self._tree

    def header(self, name: str):
        return self._parsed().get(name.lower())

    def headers_text(self) -> str:
        return _decoded(self._parsed().header_block.decode("latin-1"))

    def body_text(self) -> str:
        """le TEXTE du message, décodé (base64, quoted-printable, jeu de caractères) : on cherche ce
        que l'utilisateur lit. Les parties non textuelles ne sont pas fouillées."""
        if self._body is None:
            import email
            from email import policy
            out = []
            try:
                msg = email.message_from_bytes(self.raw, policy=policy.compat32)
                for part in msg.walk():
                    if part.get_content_maintype() != "text": continue
                    data = part.get_payload(decode=True) or b""
                    out.append(data.decode(part.get_content_charset() or "latin-1", "replace"))
            except Exception:
                out = [self.raw.decode("latin-1")]
            self._body = "\n".join(out)
        return self._body
