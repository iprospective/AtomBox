"""L'ANALYSE d'un message brut (F001 — D029, D032, D033, D064, D066, D130, D131).

Le module `email` de la bibliothèque standard fait le MIME (D154 : c'est le parseur qui a vu
le plus de courrier cassé). Ce fichier n'en fait qu'une lecture : ce qui remplit `comm`,
`comm_email`, `participant`, les pièces jointes — sans rien décider du stockage ni de la base.
"""
from __future__ import annotations
import email, email.policy, email.utils, re, unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

@dataclass
class Piece:
    ordre: int
    nom_declare: str | None
    type_declare: str | None
    type_detecte: str
    transfer_encoding: str | None
    disposition: str | None
    content_id: str | None
    parametres: dict
    octets: bytes

@dataclass
class Analyse:
    message_id: str | None
    in_reply_to: str | None
    references: list[str]
    return_path: str | None
    list_id: str | None
    list_unsubscribe: str | None
    sujet: str | None
    sujet_normalise: str | None
    date_declaree: datetime | None
    from_adresse: str
    from_nom: str | None
    participants: list[tuple[str, str | None, str, int]]   # (role, nom, adresse, ordre)
    corps_texte: str
    snippet: str | None
    pieces: list[Piece]
    structure_mime: dict
    headers: str
    est_chiffre: bool
    est_signe: bool
    nature: str
    reponse_possible: str
    taille: int
    auto_submitted: str | None = None
    precedence: str | None = None
    parties: list[bytes] = field(default_factory=list)   # les charges décodées, dans l'ordre — pour D064

MAGIES = [(b"%PDF", "application/pdf"), (b"\x89PNG", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
          (b"GIF8", "image/gif"), (b"PK\x03\x04", "application/zip"), (b"\x1f\x8b", "application/gzip"),
          (b"\x28\xb5\x2f\xfd", "application/zstd"), (b"Rar!", "application/vnd.rar"), (b"%!PS", "application/postscript")]

def type_detecte(octets: bytes, declare: str | None) -> str:
    """détecté sur les octets (D032) ; à défaut le type déclaré ; à défaut octets quelconques"""
    for magie, t in MAGIES:
        if octets.startswith(magie): return t
    if declare and declare.lower() not in ("application/octet-stream", ""): return declare.lower()
    try:
        octets[:2048].decode("utf-8"); return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"

def _adresse(nom_adr) -> tuple[str | None, str]:
    nom, adr = nom_adr
    return (nom.strip() or None), adr.strip().lower()

def normaliser_sujet(s: str | None) -> str | None:
    if not s: return None
    t = re.sub(r"^\s*((re|fw|fwd|tr|aw|sv)\s*:\s*)+", "", s, flags=re.I)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower() or None

def _snippet(texte: str, n: int = 200) -> str | None:
    """un extrait nettoyé, pas un résumé (D033) : les citations et signatures sautent"""
    lignes = [l for l in texte.splitlines() if l.strip() and not l.lstrip().startswith(">")]
    t = re.sub(r"\s+", " ", " ".join(lignes)).strip()
    return t[:n] or None

def nature_de(msg, from_adresse: str, auto_submitted: str | None, precedence: str | None) -> str:
    """D130 : humain / liste / notification / service — figée à l'ingestion"""
    ct = (msg.get_content_type() or "").lower()
    local = from_adresse.split("@")[0]
    if ct == "multipart/report" or local in ("mailer-daemon", "postmaster") or (auto_submitted or "").lower().startswith("auto-replied"):
        return "service"
    if msg["List-Id"] or msg["List-Unsubscribe"] or (precedence or "").lower() in ("bulk", "list"):
        return "liste"
    if (auto_submitted or "").lower().startswith("auto-generated") or re.match(r"^(no-?reply|ne-?pas-?repondre|donotreply|notifications?)", local):
        return "notification"
    return "humain"

def analyser(octets: bytes, date_recue: datetime | None = None) -> Analyse:
    msg = email.message_from_bytes(octets, policy=email.policy.default)
    headers = octets.split(b"\r\n\r\n", 1)[0] if b"\r\n\r\n" in octets else octets.split(b"\n\n", 1)[0]
    de = email.utils.getaddresses([msg["From"] or ""]) or [("", "")]
    from_nom, from_adresse = _adresse(de[0])
    participants, ordre = [], 0
    for role, entete in (("from", "From"), ("sender", "Sender"), ("reply_to", "Reply-To"), ("to", "To"), ("cc", "Cc"), ("bcc", "Bcc")):
        for na in email.utils.getaddresses(msg.get_all(entete, [])):
            nom, adr = _adresse(na)
            if adr: participants.append((role, nom, adr, ordre)); ordre += 1
    refs = [r for r in re.split(r"\s+", (msg["References"] or "").strip()) if r]
    pieces, parties, est_chiffre, est_signe, corps = [], [], False, False, ""
    def structure(part):
        d = {"type": part.get_content_type()}
        if part.is_multipart(): d["parties"] = [structure(p) for p in part.iter_parts()]
        return d
    corps_part = msg.get_body(preferencelist=("plain", "html")) if msg.is_multipart() else msg
    if corps_part is not None:
        try:
            brut = corps_part.get_content()
            corps = brut if isinstance(brut, str) else ""
            if corps_part.get_content_type() == "text/html": corps = re.sub(r"<[^>]+>", " ", corps)
        except Exception:
            corps = ""
    n = 0
    for part in msg.walk():
        ct = part.get_content_type().lower()
        if ct.startswith("multipart/"):
            if ct == "multipart/encrypted": est_chiffre = True
            if ct == "multipart/signed": est_signe = True
            continue
        if ct == "application/pkcs7-mime": est_chiffre = True
        try: charge = part.get_payload(decode=True) or b""
        except Exception: charge = b""
        parties.append(charge)
        est_pj = part.is_attachment() or bool(part.get_filename()) or part.get("Content-ID") or ct in ("message/rfc822", "application/pdf") or (ct.startswith("image/") and part is not corps_part)
        if est_pj and part is not corps_part and ct != "text/plain" or (est_pj and part.get_filename()):
            n += 1
            params = {k: v for k, v in part.get_params(header="content-type") or [] if k.lower() != part.get_content_type()}
            pieces.append(Piece(n, part.get_filename(), ct, type_detecte(charge, ct), (part.get("Content-Transfer-Encoding") or None),
                                (part.get_content_disposition() or None), (part.get("Content-ID") or None), params, charge))
    auto = msg["Auto-Submitted"]; prec = msg["Precedence"]
    nature = nature_de(msg, from_adresse, auto, prec)
    reponse = "avertir" if nature in ("notification", "service") or re.match(r"^(no-?reply|ne-?pas-?repondre|donotreply)", from_adresse.split("@")[0]) else "oui"
    try: date_declaree = email.utils.parsedate_to_datetime(msg["Date"]) if msg["Date"] else None
    except Exception: date_declaree = None
    if date_declaree and date_declaree.tzinfo is None: date_declaree = date_declaree.replace(tzinfo=timezone.utc)
    sujet = str(msg["Subject"]) if msg["Subject"] else None
    return Analyse(
        message_id=(msg["Message-ID"] or "").strip() or None, in_reply_to=(msg["In-Reply-To"] or "").strip() or None,
        references=refs, return_path=(msg["Return-Path"] or "").strip() or None,
        list_id=(msg["List-Id"] or "").strip() or None, list_unsubscribe=(msg["List-Unsubscribe"] or "").strip() or None,
        sujet=sujet, sujet_normalise=normaliser_sujet(sujet), date_declaree=date_declaree,
        from_adresse=from_adresse or "inconnu@invalide", from_nom=from_nom, participants=participants,
        corps_texte=corps, snippet=_snippet(corps), pieces=pieces, structure_mime=structure(msg),
        headers=headers.decode("utf-8", "replace"), est_chiffre=est_chiffre, est_signe=est_signe,
        nature=nature, reponse_possible=reponse, taille=len(octets), auto_submitted=auto, precedence=prec, parties=parties)
