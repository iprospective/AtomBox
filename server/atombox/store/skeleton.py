"""LE SQUELETTE D'UN MESSAGE (RM3631 — D208, D209) : le message sans ses pièces, reconstitué à l'octet.

Un message reçu n'est plus écrit tel quel. On écrit son SQUELETTE (le message privé du corps encodé
de chaque partie base64 assez grosse) et, à côté, chaque partie DÉCODÉE dans le blob dédupliqué —
celui que la pièce jointe occupe déjà (D011) : le même logo reçu mille fois reste un fichier.

Le piège est l'encodage. Dans le fichier, une pièce n'est pas son contenu : c'est son base64, en
lignes d'une certaine largeur, terminées par CRLF ou LF, la dernière plus courte, suivie ou non
d'une fin de ligne. Pour remettre la pièce « au même endroit », il faut reproduire CES octets. On
note donc, pour chaque partie, sa position dans le squelette et ses paramètres d'encodage, et on
VÉRIFIE à l'écriture, partie par partie : réencodée, elle doit redonner l'octet reçu. Sinon, elle
est gardée encodée telle quelle (« brut ») — elle sort quand même du squelette, et ne perd que la
déduplication entre encodages.

Puis on vérifie le MESSAGE ENTIER : reconstitué, il doit avoir l'empreinte du reçu. Sinon le
message entier est gardé dans le conteneur — compté, signalé, jamais perdu. La signature DKIM
porte sur ces octets : rien n'est recompressé avec perte, rien n'est réécrit.

LE CONTENEUR, écrit sous l'UUID du message :

    MAGIE · longueur du manifeste (4 octets) · manifeste JSON · squelette

La magie commence par un octet NUL, qu'aucun message ne porte en tête. Le manifeste porte
l'empreinte du message entier, VÉRIFIÉE à chaque lecture : un conteneur forgé (un message déposé
qui imiterait la magie) ne peut pas faire recopier le blob d'un autre — il faudrait en connaître le
contenu pour en produire l'empreinte. Ce module ne lit et n'écrit rien : il découpe et assemble."""
from __future__ import annotations

import base64
import email.parser
import email.policy
import hashlib
import json
import re
import struct

from ..journal import journal

log = journal("store")

MAGIC = b"\x00ABX-SQUELETTE-1\n"
MIN_SIZE = 1024          # en dessous, une partie reste dans le squelette : le blob coûterait plus qu'il ne rend
MAX_DEPTH = 12        # un multipart dans un multipart… borné : un message hostile ne fait pas déborder la pile

_HEADERS_END = re.compile(rb"\r?\n\r?\n")


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _headers(block: bytes):
    """les en-têtes d'une entité MIME (sans le corps), lus par la bibliothèque, en tolérant tout"""
    return email.parser.BytesHeaderParser(policy=email.policy.compat32).parsebytes(block + b"\r\n\r\n")


def _body_start(raw: bytes, start: int, fin: int, top: bool) -> int | None:
    """l'offset où commence le corps de l'entité [début, fin) ; None sans corps.
    Une partie qui commence par une fin de ligne n'a pas d'en-tête (RFC 2046 § 5.1.1)."""
    if not top:
        if raw.startswith(b"\r\n", start): return start + 2
        if raw.startswith(b"\n", start): return start + 1
    m = _HEADERS_END.search(raw, start, fin)
    return m.end() if m else None


def _parts(raw: bytes, start: int, fin: int, top: bool, depth: int, out: list):
    """ajoute à `out` les (début, fin) des corps base64 à sortir, dans l'ordre du fichier"""
    if depth > MAX_DEPTH: return
    c = _body_start(raw, start, fin, top)
    if c is None: return
    try: h = _headers(raw[start:c])
    except Exception: return
    ct = (h.get_content_type() or "").lower()
    cte = str(h.get("Content-Transfer-Encoding") or "").strip().lower()
    if ct.startswith("multipart/"):
        boundary = h.get_boundary()
        if not boundary: return
        body = raw[c:fin]
        # le CRLF qui précède une frontière appartient à la frontière (RFC 2046 § 5.1.1)
        sep = re.compile(rb"(?:\A|\r?\n)--" + re.escape(boundary.encode("latin-1", "replace")) + rb"(--)?[ \t]*(?=\r?\n|\Z)")
        opened = None
        for mo in sep.finditer(body):
            if opened is not None:
                _parts(raw, c + opened, c + mo.start(), False, depth + 1, out)
            if mo.group(1): return
            eol = body.find(b"\n", mo.end())
            if eol < 0: return
            opened = eol + 1
        return                                    # pas de frontière fermante : la fin reste au skeleton
    if ct == "message/rfc822" and cte in ("", "7bit", "8bit", "binary"):
        _parts(raw, c, fin, True, depth + 1, out)    # un message encapsulé : ses pièces aussi
        return
    if cte == "base64" and fin - c >= MIN_SIZE:
        out.append((c, fin))


def _params(enc: bytes) -> dict | None:
    """les paramètres d'encodage d'un base64 tel qu'il est sur le fil, et son contenu décodé ;
    None si le réencodage ne redonne pas exactement ces octets"""
    eol = b"\r\n" if b"\r\n" in enc else b"\n"
    lines = enc.split(eol)
    trailing = lines[-1] == b""
    if trailing: lines.pop()
    if not lines or not lines[0]: return None
    try: content = base64.b64decode(b"".join(lines), validate=True)
    except Exception: return None
    p = {"m": "b64", "w": len(lines[0]), "e": "crlf" if eol == b"\r\n" else "lf", "f": trailing}
    if reencode(p, content) != enc: return None
    return {"params": p, "content": content}


def reencode(p: dict, content: bytes) -> bytes:
    """le corps encodé d'une partie, à partir de son contenu et de ses paramètres"""
    if p.get("m") == "brut": return content
    b = base64.b64encode(content)
    w, eol = p["w"], (b"\r\n" if p["e"] == "crlf" else b"\n")
    out = eol.join(b[i:i + w] for i in range(0, len(b), w))
    return out + eol if p.get("f") else out


def decompose(raw: bytes) -> tuple[bytes, list[dict]]:
    """→ (squelette, segments) ; chaque segment : {o: position dans le squelette, contenu, params}.
    Un segment qui ne se réencode pas à l'octet est gardé encodé (`m: brut`)."""
    zones: list = []
    try: _parts(raw, 0, len(raw), True, 0, zones)
    except RecursionError: zones = []
    skeleton, segments, cursor = bytearray(), [], 0
    for start, fin in zones:
        if start < cursor: continue                      # chevauchement : impossible en principe, ignoré
        skeleton += raw[cursor:start]
        enc = raw[start:fin]
        r = _params(enc)
        seg = {"o": len(skeleton), "params": r["params"], "content": r["content"]} if r else \
              {"o": len(skeleton), "params": {"m": "brut"}, "content": enc}
        segments.append(seg)
        cursor = fin
    skeleton += raw[cursor:]
    log.debug("squelette : %d partie(s) sortie(s), %d → %d octets", len(segments), len(raw), len(skeleton))
    return bytes(skeleton), segments


def assemble(skeleton: bytes, manifest: dict, read_blob) -> bytes:
    """le message, à partir du squelette et des blobs (lus par `read_blob(empreinte)`)"""
    out, prev = bytearray(), 0
    for s in manifest.get("segments", []):
        o = s["o"]
        out += skeleton[prev:o]
        out += reencode(s, read_blob(s["b"]))
        prev = o
    out += skeleton[prev:]
    return bytes(out)


def container(skeleton: bytes, manifest: dict) -> bytes:
    j = json.dumps(manifest, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return MAGIC + struct.pack(">I", len(j)) + j + skeleton


def read_container(data: bytes) -> tuple[dict, bytes] | None:
    """(manifeste, squelette), ou None si `data` n'est pas un conteneur (un message d'avant RM3631)"""
    if not data.startswith(MAGIC): return None
    n = struct.unpack(">I", data[len(MAGIC):len(MAGIC) + 4])[0]
    start = len(MAGIC) + 4
    return json.loads(data[start:start + n]), data[start + n:]
