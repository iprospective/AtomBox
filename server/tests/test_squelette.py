"""RM3631 (D208, D209) : le message est stocké en SQUELETTE, ses pièces décodées dans les blobs dédupliqués,
et il se reconstitue À L'OCTET — sinon la signature DKIM ne se vérifie plus.

Ce qui casserait en silence : un encodage reproduit « presque » (largeur de ligne, CRLF/LF, fin de ligne
finale) ; un message encapsulé ou imbriqué dont on perdrait un octet ; un conteneur forgé qui ferait
recopier le blob d'un autre ; un repli qui perdrait le message."""
import base64, hashlib, os
import pytest
from atombox.store import Store
from atombox.store import skeleton as Sq

PDF = b"%PDF-1.4\n" + bytes(range(256)) * 40          # 10 Kio, octets quelconques
PNG = b"\x89PNG\r\n\x1a\n" + os.urandom(3000)


def b64(data, w=76, eol=b"\r\n", fin=True):
    e = base64.b64encode(data)
    out = eol.join(e[i:i + w] for i in range(0, len(e), w))
    return out + eol if fin else out


def message(pieces, eol=b"\r\n", boundary=b"==B1=="):
    """un multipart/mixed ; `pieces` = [(type, corps encodé)]"""
    L = [b"From: Expediteur <exp@exemple.fr>", b"To: dest@exemple.fr", b"Subject: test squelette",
         b"Message-ID: <sq-%s@exemple.fr>" % os.urandom(4).hex().encode(), b"MIME-Version: 1.0",
         b'Content-Type: multipart/mixed; boundary="' + boundary + b'"', b"", "Préambule ignoré.".encode("utf-8"),
         b"--" + boundary, b"Content-Type: text/plain; charset=utf-8", b"", b"Bonjour, voici les pieces."]
    for t, corps in pieces:
        L += [b"--" + boundary, b"Content-Type: " + t, b"Content-Transfer-Encoding: base64",
              b'Content-Disposition: attachment; filename="f.bin"', b""]
        L.append(corps)           # tel quel : une fin de ligne finale fait une ligne vide avant la frontière
    L += [b"--" + boundary + b"--", b""]
    return eol.join(L)


def aller_retour(tmp_path, raw):
    m = Store(str(tmp_path))
    w = m.write_message("0190f0f0-0000-7000-8000-000000000001", raw)
    assert m.read_message("0190f0f0-0000-7000-8000-000000000001") == raw, "reconstitué à l'octet"
    return m, w


@pytest.mark.parametrize("w,eol,fin", [(76, b"\r\n", True), (76, b"\n", True), (72, b"\r\n", True), (64, b"\n", False), (76, b"\r\n", False)])
def test_encodages_reproduits_a_l_octet(tmp_path, w, eol, fin):
    raw = message([(b"application/pdf", b64(PDF, w, eol, fin))], eol=eol)
    m, info = aller_retour(tmp_path, raw)
    assert not info["brut_garde"] and info["compression"] == "squelette"
    assert [e for e, _ in info["blobs"]] == [hashlib.sha256(PDF).hexdigest()], "la pièce est stockée DÉCODÉE"
    sq = Sq.read_container(m.read("0190f0f0-0000-7000-8000-000000000001"))[1]
    assert len(sq) < len(raw) - 10000, "le squelette ne porte plus la pièce"


def test_la_meme_piece_sous_deux_encodages_n_est_qu_un_blob(tmp_path):
    m = Store(str(tmp_path))
    a = m.write_message("0190f0f0-0000-7000-8000-00000000000a", message([(b"image/png", b64(PNG, 76))]))
    b = m.write_message("0190f0f0-0000-7000-8000-00000000000b", message([(b"image/png", b64(PNG, 60, b"\n"))], eol=b"\n"))
    assert a["blobs"][0][0] == b["blobs"][0][0] == hashlib.sha256(PNG).hexdigest()


def test_base64_non_reproductible_garde_l_encode_et_reste_exact(tmp_path):
    irregulier = b64(PDF, 76)[:300] + b"\r\n" + b64(PDF, 76)[300:]          # une ligne coupée de travers
    raw = message([(b"application/pdf", irregulier)])
    m, info = aller_retour(tmp_path, raw)
    assert not info["brut_garde"]
    man = Sq.read_container(m.read("0190f0f0-0000-7000-8000-000000000001"))[0]
    assert man["segments"][0]["m"] == "brut", "gardé encodé tel quel — il ne perd que la déduplication"


def test_imbrique_et_encapsule(tmp_path):
    inner = message([(b"application/pdf", b64(PDF))], boundary=b"in")
    raw = (b"From: a@exemple.fr\r\nSubject: transfert\r\nMIME-Version: 1.0\r\n"
           b'Content-Type: multipart/mixed; boundary="ext"\r\n\r\n'
           b"--ext\r\nContent-Type: multipart/alternative; boundary=\"alt\"\r\n\r\n"
           b"--alt\r\nContent-Type: text/plain\r\n\r\ntexte\r\n--alt\r\nContent-Type: text/html\r\nContent-Transfer-Encoding: base64\r\n\r\n"
           + b64(b"<p>" + b"x" * 2000 + b"</p>") + b"--alt--\r\n"
           b"--ext\r\nContent-Type: message/rfc822\r\n\r\n" + inner +
           b"\r\n--ext\r\nContent-Type: image/png\r\nContent-Transfer-Encoding: base64\r\n\r\n" + b64(PNG) + b"--ext--\r\n")
    m, info = aller_retour(tmp_path, raw)
    assert len(info["blobs"]) == 3, "html, pdf du message encapsulé, png : trois parties sorties"


@pytest.mark.parametrize("raw", [
    b"From: a@exemple.fr\r\nSubject: simple\r\n\r\nCorps sans MIME.\r\n",
    b"From: a@exemple.fr\r\nContent-Type: multipart/mixed; boundary=x\r\n\r\n--x\r\nContent-Transfer-Encoding: base64\r\n\r\n" + b64(PDF),   # sans fermeture
    b"Pas un message du tout \x00\xff",
    b"",
])
def test_messages_casses_restent_exacts(tmp_path, raw):
    aller_retour(tmp_path, raw)


def test_conteneur_forge_ne_fait_pas_recopier_un_autre_blob(tmp_path):
    m = Store(str(tmp_path))
    secret, _ = m.put(b"le contenu d'un autre " * 100)
    forge = Sq.container(b"", {"h": "0" * 64, "segments": [{"o": 0, "b": secret, "m": "brut"}]})
    # déposé comme un message (APPEND) : il est emballé, et relu tel quel
    m.write_message("0190f0f0-0000-7000-8000-0000000000f1", forge)
    assert m.read_message("0190f0f0-0000-7000-8000-0000000000f1") == forge
    # écrit avant RM3631 (sans emballage) : l'empreinte vérifiée à la lecture refuse
    m.write("0190f0f0-0000-7000-8000-0000000000f2", forge)
    with pytest.raises(ValueError):
        m.read_message("0190f0f0-0000-7000-8000-0000000000f2")


def test_repli_garde_le_message_entier(tmp_path, monkeypatch):
    raw = message([(b"application/pdf", b64(PDF))])
    vrai = Sq.assemble        # une reconstitution infidèle dès qu'il y a des pièces (un défaut qu'on ne connaît pas encore)
    monkeypatch.setattr(Sq, "assemble", lambda sq, man, lire: b"faux" if man.get("segments") else vrai(sq, man, lire))
    m, info = aller_retour(tmp_path, raw)
    assert info["brut_garde"] and info["compression"] == "squelette-brut" and info["blobs"] == []


def test_message_d_avant_rm3631_se_lit_tel_quel(tmp_path):
    m = Store(str(tmp_path)); raw = message([(b"application/pdf", b64(PDF))])
    m.write("0190f0f0-0000-7000-8000-0000000000c1", raw)
    assert m.read_message("0190f0f0-0000-7000-8000-0000000000c1") == raw
