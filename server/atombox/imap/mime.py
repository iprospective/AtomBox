"""LA STRUCTURE MIME servie en IMAP (RFC 3501 § 6.4.5 et § 7.4.2) — lue sur l'OCTET stocké.

Trois choses, et elles vont ensemble :

1. `BODYSTRUCTURE` / `BODY` : la vraie arborescence du message — ses parties, leurs types, leurs
   tailles, leurs dispositions. C'est ce que le client lit pour afficher un trombone, la liste des
   pièces jointes, et décider de ce qu'il télécharge ;
2. `BODY[1.2]`, `BODY[2.MIME]`, `BODY[3.HEADER]`… : chaque partie, par son numéro. Annoncer la
   structure sans servir les parties serait annoncer ce qu'on ne tient pas : le client demandera
   `BODY[2]` pour ouvrir la pièce jointe ;
3. `ENVELOPE`, construit sur les en-têtes, y compris pour un message encapsulé (`message/rfc822`).

POURQUOI UN DÉCOUPAGE À LA MAIN, et pas le paquet `email` de Python. `email` reconstruit : il replie
les en-têtes, normalise les fins de ligne, réencode. Ce qu'on sert doit être l'OCTET du magasin
(D025) — la partie 2 d'un message est la tranche exacte de ses octets entre deux frontières, et sa
taille annoncée doit être celle de cette tranche, sinon le client lit de travers tout ce qui suit.
On découpe donc les octets, et l'on ne fait qu'en LIRE les en-têtes.

Les chaînes sont des `str` décodées en latin-1 : un caractère par octet, sans rien interpréter. Un
en-tête 8 bits mal formé (fréquent) passe tel quel, et la taille d'un littéral reste celle des octets.
"""
from __future__ import annotations
import email.utils
import re

_SEP = re.compile(rb"\r?\n\r?\n")


class Part:
    """une partie MIME : ses en-têtes et son corps, en octets exacts, et ses enfants"""

    def __init__(self, raw: bytes, default_type=("text", "plain"), message: bool = True):
        self.is_message = message           # le message lui-même, ou un message encapsulé : il a des « parties »
        self.trailing = b""
        m = _SEP.search(raw)
        if raw.startswith(b"\r\n") or raw.startswith(b"\n"):
            # pas d'en-tête du tout : la partie commence par la ligne vide (RFC 2046 § 5.1.1)
            self.header_block, self.body = raw[:2 if raw.startswith(b"\r\n") else 1], raw[2 if raw.startswith(b"\r\n") else 1:]
        elif m:
            self.header_block, self.body = raw[:m.end()], raw[m.end():]
        else:
            self.header_block, self.body = raw, b""
        self.headers = _headers(self.header_block)
        ctype = self.get("content-type")
        if ctype:
            t, params = _content_type(ctype)
        else:
            t, params = "/".join(default_type), []
        self.type, _, self.subtype = t.partition("/")
        if not self.subtype: self.type, self.subtype = default_type
        self.params = params
        self.children: list[Part] = []
        self.message: Part | None = None
        if self.type.lower() == "multipart":
            b = _param(params, "boundary")
            child_default = ("message", "rfc822") if self.subtype.lower() == "digest" else ("text", "plain")
            if b:
                for chunk, eol in _split(self.body, b.encode("latin-1")):
                    c = Part(chunk, child_default, message=False)
                    c.trailing = eol
                    self.children.append(c)
        elif self.type.lower() == "message" and self.subtype.lower() == "rfc822":
            self.message = Part(self.body, message=True)

    def get(self, name: str):
        return self.headers.get(name.lower())

    # ── la navigation par numéro de partie (RFC 3501 § 6.4.5) ───────────────────────────────────
    def sub(self, n: int):
        """la n-ième partie de CE message ou de cette partie"""
        if self.children:
            return self.children[n - 1] if 1 <= n <= len(self.children) else None
        if self.message is not None:
            return self.message.sub(n)
        # une partie sans enfants : sa partie 1, c'est elle (pour un message simple comme pour une
        # pièce dans un multipart — c'est ce que sert Dovecot)
        return self if n == 1 else None


def _headers(block: bytes) -> dict:
    """les en-têtes dépliés, en latin-1 — la PREMIÈRE occurrence de chaque nom"""
    out: dict = {}
    current = None
    for line in block.decode("latin-1").splitlines():
        if not line: break
        if line[:1] in (" ", "\t") and current:
            out[current] += " " + line.strip()
            continue
        name, sep, value = line.partition(":")
        if not sep: continue
        current = name.strip().lower()
        if current in out:
            current = None                           # on garde la première, les suivantes s'ignorent
            continue
        out[current] = value.strip()
    return out


def _tokens(s: str):
    """`type/sub; a=b; c="d e"` → la valeur, puis les paires (nom, valeur) — guillemets compris"""
    parts, buf, q, esc = [], [], False, False
    for c in s:
        if esc: buf.append(c); esc = False; continue
        if c == "\\" and q: esc = True; continue
        if c == '"': q = not q; continue
        if c == ";" and not q: parts.append("".join(buf).strip()); buf = []; continue
        buf.append(c)
    parts.append("".join(buf).strip())
    return parts[0], [p for p in parts[1:] if p]


def _content_type(v: str):
    t, rest = _tokens(v)
    params = []
    for p in rest:
        k, _, val = p.partition("=")
        if k.strip(): params.append((k.strip().lower(), val.strip()))
    return (t.strip().lower() or "text/plain"), params


def _param(params, name):
    for k, v in params:
        if k == name: return v
    return None


def _split(body: bytes, boundary: bytes) -> list[tuple[bytes, bytes]]:
    """les parties entre les frontières, chacune avec la fin de ligne qui la sépare de la suivante.

    Le CRLF qui PRÉCÈDE une frontière lui appartient (RFC 2046 § 5.1.1) : il n'est pas dans la
    partie, et la taille annoncée ne le compte pas. On le garde à part, parce qu'une partie qui est
    ELLE-MÊME un multipart le rend avec ses octets — c'est ce que fait Dovecot, contre lequel cette
    structure est éprouvée (`tests/test_imap_dovecot.py`)."""
    delim = re.compile(rb"(?:\A|(\r?\n))--" + re.escape(boundary) + rb"(--)?[ \t]*(?:\r?\n|\Z)")
    out, start, ended = [], None, False
    for m in delim.finditer(body):
        if start is not None: out.append((body[start:m.start()], m.group(1) or b""))
        if m.group(2): ended = True; break
        start = m.end()
    if start is not None and not ended:
        out.append((body[start:], b""))             # message tronqué : on rend ce qui est là
    return out


# ── les sections : ce que `BODY[…]` rend ────────────────────────────────────────────────────────
_SECTION = re.compile(r"^((?:\d+\.)*\d+)?\.?(HEADER\.FIELDS\.NOT|HEADER\.FIELDS|HEADER|TEXT|MIME)?\s*(\(.*\))?$", re.I)


def section(root: Part, raw: bytes, spec: str):
    """les octets d'une section, ou None si elle n'existe pas"""
    spec = (spec or "").strip()
    if spec == "": return raw
    m = _SECTION.match(spec)
    if not m: return None
    nums = [int(x) for x in m.group(1).split(".")] if m.group(1) else []
    what = (m.group(2) or "").upper()
    node, leaf = root, False
    for n in nums:
        # Descendu dans l'UNIQUE partie d'un message simple, on est sur une feuille : « 1.1 » n'existe
        # pas, même si « 1 » désigne le message lui-même (Dovecot ne rend rien non plus).
        if leaf: return None
        nxt = node.sub(n)
        if nxt is None: return None
        leaf = nxt is node and node.is_message
        node = nxt
    if what == "MIME":
        return node.header_block if nums else None
    if not what:
        # « 2 » où 2 est un message encapsulé : le message entier (en-têtes et corps) ; sinon le corps.
        # Une partie MULTIPART rend aussi la fin de ligne qui clôt sa frontière de fermeture.
        return _multipart_bytes(node) if node.children else node.body
    target = node if not nums else node.message
    if target is None: return None              # HEADER / TEXT n'ont de sens que sur un message
    if what == "TEXT": return target.body
    if what == "HEADER": return target.header_block
    fields = {f.lower() for f in re.findall(r"[^\s()]+", m.group(3) or "")}
    keep, out = False, []
    for line in target.header_block.split(b"\n"):
        line = line.rstrip(b"\r")
        if not line: break
        if line[:1] in (b" ", b"\t"):
            if keep: out.append(line)
            continue
        name = line.split(b":", 1)[0].decode("latin-1").strip().lower()
        keep = (name in fields) != (what == "HEADER.FIELDS.NOT")
        if keep: out.append(line)
    return b"\r\n".join(out) + (b"\r\n" if out else b"") + b"\r\n"


def _multipart_bytes(node: Part) -> bytes:
    """les octets d'une partie qui est elle-même un multipart : jusqu'à la fin de la ligne de sa
    frontière de FERMETURE, épilogue exclu — et cette fin de ligne, si la frontière suivante du
    parent l'a « empruntée », lui est rendue. C'est ce que sert Dovecot."""
    b = _param(node.params, "boundary") or ""
    m = re.search(rb"--" + re.escape(b.encode("latin-1")) + rb"--[ \t]*(\r?\n)?", node.body)
    if not m: return node.body + node.trailing
    end = node.body[:m.end()]
    return end if m.group(1) else end + node.trailing


# ── la mise en forme IMAP, à l'octet ─────────────────────────────────────────────────────────────
def nstring(v) -> str:
    """NIL, une chaîne entre guillemets, ou un littéral — SANS réencoder : la chaîne est déjà un
    caractère par octet. `protocol.quote` réencode en UTF-8, ce qui doublerait les octets 8 bits
    d'un en-tête mal formé et fausserait la taille du littéral."""
    if v is None: return "NIL"
    s = str(v)
    if "\r" in s or "\n" in s or any(ord(c) > 126 or ord(c) < 32 for c in s):
        return "{%d}\r\n%s" % (len(s), s)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _plist(params):
    return "NIL" if not params else "(" + " ".join(nstring(k) + " " + nstring(v) for k, v in params) + ")"


def _addresses(value):
    if not value: return "NIL"
    out = []
    for name, addr in email.utils.getaddresses([value]):
        if not addr and not name: continue
        local, _, host = addr.rpartition("@") if "@" in addr else (addr, "", None)
        out.append("(%s NIL %s %s)" % (nstring(name or None), nstring(local or None), nstring(host)))
    return "(" + "".join(out) + ")" if out else "NIL"


def envelope(p: Part) -> str:
    """ENVELOPE (RFC 3501 § 7.4.2) — l'ordre des dix champs est imposé, et SENDER et REPLY-TO
    reprennent FROM quand ils manquent : c'est le serveur qui doit le faire, pas le client."""
    frm = p.get("from")
    return "(%s %s %s %s %s %s %s %s %s %s)" % (
        nstring(p.get("date")), nstring(p.get("subject")),
        _addresses(frm), _addresses(p.get("sender") or frm), _addresses(p.get("reply-to") or frm),
        _addresses(p.get("to")), _addresses(p.get("cc")), _addresses(p.get("bcc")),
        nstring(p.get("in-reply-to")), nstring(p.get("message-id")))


def _lines(b: bytes) -> int:
    """le nombre de lignes d'un corps texte : ses SAUTS de ligne. Comme Dovecot — le serveur que
    rencontrent la plupart des clients, et contre lequel cette structure est éprouvée."""
    return b.count(b"\n")


def _disposition(p: Part) -> str:
    v = p.get("content-disposition")
    if not v: return "NIL"
    t, rest = _content_type(v)
    return "(%s %s)" % (nstring(t), _plist(rest))


def structure(p: Part, extended: bool = True) -> str:
    """BODYSTRUCTURE (`extended`) ou BODY. La grammaire est celle de la RFC, au caractère près :
    les parties d'un multipart se suivent SANS espace (`1*body SP media-subtype`)."""
    if p.children:
        inner = "".join(structure(c, extended) for c in p.children)
        s = "(%s %s" % (inner, nstring(p.subtype))
        if extended:
            s += " %s %s %s %s" % (_plist([(k, v) for k, v in p.params]), _disposition(p),
                                   nstring(p.get("content-language")), nstring(p.get("content-location")))
        return s + ")"
    cte = p.get("content-transfer-encoding") or "7bit"            # tel qu'écrit : la casse est libre
    s = "(%s %s %s %s %s %s %d" % (nstring(p.type), nstring(p.subtype), _plist(p.params),
                                     nstring(p.get("content-id")), nstring(p.get("content-description")),
                                     nstring(cte), len(p.body))
    if p.message is not None:
        s += " %s %s %d" % (envelope(p.message), structure(p.message, extended), _lines(p.body))
    elif p.type.lower() == "text":
        s += " %d" % _lines(p.body)
    if extended:
        s += " %s %s %s %s" % (nstring(p.get("content-md5")), _disposition(p),
                               nstring(p.get("content-language")), nstring(p.get("content-location")))
    return s + ")"
