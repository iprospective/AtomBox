"""L'IDENTITÉ d'un message (D064) : ce que l'expéditeur a envoyé — les parties décodées et une
liste blanche d'en-têtes — jamais les en-têtes de transport (Received, X-Spam…), qui changent
d'une livraison à l'autre et feraient d'un même envoi deux messages (D010, D028)."""
import hashlib, re
from .analysis import Analysis

HEADERS = ("message-id", "date", "from", "to", "cc", "subject", "in-reply-to")

def _values(headers: str) -> dict:
    d, cle, val = {}, None, []
    for line in headers.replace("\r\n", "\n").split("\n"):
        if line[:1] in (" ", "\t") and cle: val.append(line.strip()); continue
        if cle and cle in HEADERS: d.setdefault(cle, " ".join(val))
        if ":" in line:
            cle, v = line.split(":", 1); cle = cle.strip().lower(); val = [v.strip()]
        else: cle, val = None, []
    if cle and cle in HEADERS: d.setdefault(cle, " ".join(val))
    return d

def identity_fingerprint(a: Analysis) -> str:
    h = hashlib.sha256()
    v = _values(a.headers)
    for k in HEADERS:
        h.update(k.encode()); h.update(b"\0"); h.update(re.sub(r"\s+", " ", v.get(k, "")).strip().lower().encode()); h.update(b"\n")
    for p in a.parties:
        h.update(hashlib.sha256(p).digest())
    return h.hexdigest()
