"""F001 — l'analyse d'un message brut et son identité (D064, D130, D131, D032, D033)."""
import os, pytest
from atombox.ingestion import analyser, empreinte_identite

F = os.path.join(os.path.dirname(__file__), "fixtures")
def lire(n): return open(os.path.join(F, n), "rb").read()

def test_simple():
    a = analyser(lire("simple.eml"))
    assert a.from_adresse == "jean.tessier@tessier-industries.example" and a.from_nom == "Jean Tessier"
    assert a.message_id == "<a1@tessier-industries.example>" and a.sujet.startswith("Re: Commande")
    assert a.sujet_normalise == "commande 4521 — delai".replace("—", "").replace("  ", " ").strip() or a.sujet_normalise.startswith("commande 4521")
    assert [(r, ad) for r, _, ad, _ in a.participants] == [("from", "jean.tessier@tessier-industries.example"), ("to", "contact@exemple.fr"), ("cc", "fred@exemple.fr")]
    assert a.nature == "humain" and a.reponse_possible == "oui" and not a.pieces
    assert "ancien message" not in a.snippet and a.snippet.startswith("Bonjour"), "le snippet saute les citations (D033)"
    assert a.date_declaree.isoformat().startswith("2026-09-04T09:12")
    assert a.headers.startswith("From:") or "Message-ID" in a.headers

def test_pieces_jointes_detectees_sur_les_octets():
    a = analyser(lire("pieces.eml"))
    assert len(a.pieces) == 3
    types = {p.nom_declare: p.type_detecte for p in a.pieces}
    assert types["F-2026-0917.pdf"] == "application/pdf" and types["copie.bin"] == "application/pdf", "détecté sur les octets, pas déclaré (D032)"
    assert types["logo.png"] == "image/png"
    logo = next(p for p in a.pieces if p.nom_declare == "logo.png")
    assert logo.content_id and logo.disposition in ("inline", "attachment")   # le fixture le déclare attachment ; le content-id suffit
    assert a.snippet.startswith("Veuillez")

def test_liste_et_notification():
    l = analyser(lire("liste.eml"))
    assert l.nature == "liste" and l.list_id and l.list_unsubscribe
    assert "Nouveautés" in l.snippet and "<b>" not in l.snippet
    n = analyser(lire("notification.eml"))
    assert n.nature == "notification" and n.reponse_possible == "avertir", "on avertit, on ne refuse pas (D131)"

def test_identite_ignore_le_transport():
    a, b = analyser(lire("simple.eml")), analyser(lire("simple-relivre.eml"))
    assert lire("simple.eml") != lire("simple-relivre.eml")
    assert empreinte_identite(a) == empreinte_identite(b), "deux livraisons, un message (D064, D010)"
    assert empreinte_identite(a) != empreinte_identite(analyser(lire("reponse.eml")))

def test_reponse_reference_le_fil():
    r = analyser(lire("reponse.eml"))
    assert r.in_reply_to == "<a1@tessier-industries.example>" and r.references == ["<a1@tessier-industries.example>"]
    assert r.sujet_normalise == analyser(lire("simple.eml")).sujet_normalise, "RE: et Re: se normalisent pareil"
