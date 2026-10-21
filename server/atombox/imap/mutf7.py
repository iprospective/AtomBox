"""Le MODIFIED UTF-7 des noms de boîtes aux lettres (RFC 3501 § 5.1.3).

IMAP transporte les noms de dossiers en ASCII. Un nom accentué y voyage codé : « Pièces » devient
`Pi&AOg-ces` — les caractères hors ASCII passent en UTF-16 gros-boutiste, puis en base64 modifié
(`,` au lieu de `/`, sans `=`), entre `&` et `-` ; et `&` lui-même s'écrit `&-`.

CE N'EST PAS L'UTF-7 DE PYTHON. Le codec `utf-7` utilise `+` comme caractère de bascule et le `/` du
base64 : il lisait « R+D » comme le début d'une séquence codée, et ne décodait rien de ce qu'un
serveur IMAP envoie réellement. La relève s'en servait (D183 § 6).

Deux sens, deux usages :
- `encode` : un nom LISIBLE (« Pièces », tapé dans le webmail) → le nom sur le FIL ;
- `decode` : un nom du FIL (envoyé par un client ou par le fournisseur) → le nom lisible.

Éprouvé contre `doveadm mailbox mutf7` (`tests/test_imap_dovecot.py`).
"""
from __future__ import annotations
import base64


def encode(name: str) -> str:
    out, run = [], []

    def flush():
        if run:
            b = base64.b64encode("".join(run).encode("utf-16-be")).decode("ascii").rstrip("=").replace("/", ",")
            out.append("&" + b + "-")
            run.clear()

    for c in name:
        if 0x20 <= ord(c) <= 0x7E:
            flush()
            out.append("&-" if c == "&" else c)
        else:
            run.append(c)
    flush()
    return "".join(out)


def decode(name: str) -> str:
    """tolérant : une séquence mal formée est rendue telle quelle, plutôt que de faire disparaître le
    dossier — on ne perd pas le nom d'un dossier parce qu'un serveur le code mal"""
    out, i, n = [], 0, len(name)
    while i < n:
        c = name[i]
        if c != "&":
            out.append(c); i += 1; continue
        j = name.find("-", i + 1)
        if j == -1:
            out.append(name[i:]); break
        chunk = name[i + 1:j]
        if chunk == "":
            out.append("&")
        else:
            try:
                b = chunk.replace(",", "/")
                # validate=True : sans lui, base64 IGNORE en silence les caractères invalides, et
                # « A&!!!-B » devenait « AB » — un nom de dossier amputé sans un mot
                out.append(base64.b64decode(b + "=" * (-len(b) % 4), validate=True).decode("utf-16-be"))
            except Exception:
                out.append(name[i:j + 1])
        i = j + 1
    return "".join(out)
