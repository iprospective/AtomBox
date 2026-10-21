"""RM3499 — la structure MIME servie en IMAP, éprouvée sur un message comme on en reçoit.

Un multipart/mixed qui contient : une alternative texte / HTML, une pièce jointe PDF en base64, et
un message TRANSFÉRÉ (message/rfc822) — avec un en-tête 8 bits mal formé, parce qu'on en reçoit.
Chaque partie servie doit être la TRANCHE EXACTE des octets stockés : c'est ce que le client
télécharge, et sa taille annoncée doit correspondre au dernier octet près.
"""
from __future__ import annotations
from atombox.imap import mime
from atombox.imap.protocol import parse_line

PDF = b"JVBERi0xLjQKJcOkw7zDtsOfCjIgMCBvYmoKPDwvTGVuZ3RoIDMgMCBSPj4Kc3RyZWFtCg=="
TRANSFERE = (b"From: Fournisseur <achats@fournisseur.example>\r\nTo: contact@exemple.fr\r\n"
             b"Subject: Commande 4412\r\nMessage-ID: <c4412@fournisseur.example>\r\n"
             b"Content-Type: text/plain; charset=iso-8859-1\r\n\r\n"
             b"Livraison pr\xe9vue jeudi.\r\n")
MESSAGE = (b"From: Mathieu <contact@exemple.fr>\r\n"
           b"To: Client <client@client.example>, Autre <autre@client.example>\r\n"
           b"Cc: copie@client.example\r\n"
           b"Subject: Devis et pi\xe8ces\r\n"
           b"Date: Wed, 21 Oct 2026 09:00:00 +0200\r\n"
           b"Message-ID: <devis-mime@exemple.fr>\r\n"
           b"MIME-Version: 1.0\r\n"
           b"Content-Type: multipart/mixed; boundary=\"EXT\"\r\n\r\n"
           b"Ceci est un message MIME.\r\n"
           b"--EXT\r\n"
           b"Content-Type: multipart/alternative; boundary=ALT\r\n\r\n"
           b"--ALT\r\n"
           b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
           b"Bonjour,\r\nle devis est joint.\r\n"
           b"--ALT\r\n"
           b"Content-Type: text/html; charset=utf-8\r\n\r\n"
           b"<p>Bonjour,</p><p>le devis est joint.</p>\r\n"
           b"--ALT--\r\n"
           b"--EXT\r\n"
           b"Content-Type: application/pdf; name=\"devis.pdf\"\r\n"
           b"Content-Transfer-Encoding: base64\r\n"
           b"Content-Disposition: attachment; filename=\"devis.pdf\"\r\n\r\n"
           + PDF + b"\r\n"
           b"--EXT\r\n"
           b"Content-Type: message/rfc822\r\n\r\n"
           + TRANSFERE +
           b"--EXT--\r\n"
           b"Epilogue ignore.\r\n")


def _arbre():
    return mime.Part(MESSAGE)


def _relire(s: str):
    """relit une réponse IMAP comme le ferait un client : les littéraux {n} compris"""
    import re
    out, i = [], 0
    for m in re.finditer(r"\{(\d+)\}\r\n", s):
        if m.start() < i: continue
        out.append(s[i:m.start()]); n = int(m.group(1)); val = s[m.end():m.end() + n]
        out.append('"' + val.replace("\\", "\\\\").replace('"', '\\"') + '"'); i = m.end() + n
    out.append(s[i:])
    return parse_line("".join(out))[0]


def test_l_arbre_a_la_forme_du_message():
    r = _arbre()
    assert (r.type, r.subtype) == ("multipart", "mixed") and len(r.children) == 3
    alt, pdf, fwd = r.children
    assert (alt.subtype, len(alt.children)) == ("alternative", 2)
    assert (pdf.type, pdf.subtype) == ("application", "pdf")
    assert fwd.message is not None and fwd.message.get("subject") == "Commande 4412"


def test_chaque_partie_est_la_tranche_exacte_des_octets():
    """la taille annoncée = les octets rendus = une tranche du message stocké"""
    r = _arbre()
    # Le CRLF qui précède une frontière APPARTIENT à la frontière (RFC 2046 § 5.1.1) : il n'est pas
    # dans la partie. Le premier jet de ce test le comptait — c'est le test qui avait tort.
    for spec, attendu in (("1.1", b"Bonjour,\r\nle devis est joint."),
                          ("1.2", b"<p>Bonjour,</p><p>le devis est joint.</p>"),
                          ("2", PDF),
                          ("3", TRANSFERE[:-2])):
        data = mime.section(r, MESSAGE, spec)
        assert data == attendu, (spec, data)
        assert data in MESSAGE, "%s : une tranche du message, pas une reconstruction" % spec
    assert mime.section(r, MESSAGE, "") == MESSAGE


def test_les_sections_d_en_tetes_et_du_message_encapsule():
    r = _arbre()
    assert mime.section(r, MESSAGE, "2.MIME").startswith(b"Content-Type: application/pdf")
    assert mime.section(r, MESSAGE, "3.HEADER").startswith(b"From: Fournisseur")
    assert mime.section(r, MESSAGE, "3.TEXT") == b"Livraison pr\xe9vue jeudi."
    assert mime.section(r, MESSAGE, "3.1") == b"Livraison pr\xe9vue jeudi.", \
        "la partie 1 d'un message encapsulé d'une seule partie, c'est son corps"
    champs = mime.section(r, MESSAGE, "HEADER.FIELDS (SUBJECT CC)")
    assert champs == b"Cc: copie@client.example\r\nSubject: Devis et pi\xe8ces\r\n\r\n"
    assert b"Subject" not in mime.section(r, MESSAGE, "HEADER.FIELDS.NOT (SUBJECT)")
    for absente in ("4", "1.3", "2.HEADER", "9.MIME"):
        assert mime.section(r, MESSAGE, absente) is None, absente


def test_bodystructure_suit_la_grammaire_et_annonce_la_piece_jointe():
    s = mime.structure(_arbre(), extended=True)
    # 1*body SP media-subtype : les parties d'un multipart se suivent SANS espace
    assert s.startswith("(((") and ')("application" "pdf"' in s and ')("message" "rfc822"' in s
    arbre = _relire(s)                                # la réponse se relit : parenthèses équilibrées
    alt, pdf, fwd, sous_type = arbre[0], arbre[1], arbre[2], arbre[3]
    assert sous_type == "mixed"
    assert pdf[:2] == ["application", "pdf"] and pdf[5].lower() == "base64" and int(pdf[6]) == len(PDF)
    assert pdf[8] == ["attachment", ["filename", "devis.pdf"]], "la disposition : c'est elle qui fait le trombone"
    assert fwd[:2] == ["message", "rfc822"] and int(fwd[6]) == len(TRANSFERE) - 2
    assert fwd[7][1] == "Commande 4412", "l'ENVELOPE du message encapsulé"
    assert alt[2] == "alternative" and alt[0][:2] == ["text", "plain"] and alt[1][:2] == ["text", "html"]


def test_body_sans_extension_n_en_porte_aucune():
    court, long = mime.structure(_arbre(), extended=False), mime.structure(_arbre(), extended=True)
    assert len(court) < len(long) and "attachment" not in court and "attachment" in long


def test_l_enveloppe_porte_tous_les_destinataires():
    """l'ancienne enveloppe rendait l'expéditeur partout et NIL pour To et Cc"""
    e = mime.envelope(_arbre())
    env = _relire(e)
    assert len(env) == 10
    assert [a[2] for a in env[5]] == ["client", "autre"], "To : les deux"
    assert env[6][0][2:] == ["copie", "client.example"], "Cc"
    assert env[3] == env[2] and env[4] == env[2], "Sender et Reply-To reprennent From quand ils manquent"
    assert env[9] == "<devis-mime@exemple.fr>"


def test_un_en_tete_8_bits_passe_a_l_octet_dans_un_litteral():
    """« pi\\xe8ces » n'est pas de l'UTF-8 : le rendre par `quote` l'aurait réencodé en deux octets,
    et la taille du littéral aurait menti"""
    e = mime.envelope(_arbre())
    assert "{15}\r\nDevis et pi\xe8ces" in e
    assert len("Devis et pi\xe8ces".encode("latin-1")) == 15


def test_un_message_d_une_seule_partie():
    simple = b"From: a@b.example\r\nSubject: x\r\n\r\nUne ligne.\r\nDeux.\r\n"
    r = mime.Part(simple)
    assert mime.section(r, simple, "1") == b"Une ligne.\r\nDeux.\r\n"
    assert mime.section(r, simple, "TEXT") == b"Une ligne.\r\nDeux.\r\n"
    s = parse_line(mime.structure(r, extended=False))[0]
    assert s[:2] == ["text", "plain"] and int(s[6]) == len(b"Une ligne.\r\nDeux.\r\n") and int(s[7]) == 2, "deux sauts de ligne"
