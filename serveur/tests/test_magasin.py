"""F002 — le magasin d'octets : ab/cd/<id>, jamais réécrit, zstd conditionnel, lecture transparente."""
import os, uuid, pytest
from atombox.magasin import Magasin, empreinte
from atombox.uuid7 import uuid7

@pytest.fixture
def magasin(tmp_path): return Magasin(str(tmp_path / "magasin"))

def test_chemin_ab_cd(magasin):
    e = "abcdef0123456789" * 4
    assert magasin.chemin(e).endswith(os.path.join("ab", "cd", e))
    u = str(uuid7())
    assert magasin.chemin(u).endswith(os.path.join(u[:2], u[2:4], u))
    with pytest.raises(ValueError): magasin.chemin("../evasion")

def test_deposer_lit_et_dedoublonne(magasin):
    octets = b"facture " * 1000
    e, info = magasin.deposer(octets)
    assert e == empreinte(octets) and info["nouveau"] and info["compression"] == "zstd" and info["taille_stockee"] < len(octets)
    assert magasin.lire(e) == octets
    e2, info2 = magasin.deposer(octets)
    assert e2 == e and not info2["nouveau"], "le même contenu n'est pas réécrit"

def test_compression_conditionnelle(magasin):
    aleatoire = os.urandom(4096)
    e, info = magasin.deposer(aleatoire)
    assert info["compression"] == "aucune" and info["taille_stockee"] == 4096, "ne pas compresser ce qui ne gagne rien (D069)"
    assert magasin.lire(e) == aleatoire

def test_message_brut_sous_uuid(magasin):
    u = uuid7(); brut = b"From: a@b\r\n\r\nbonjour\r\n" * 50
    info = magasin.ecrire(str(u), brut)
    assert info["nouveau"] and magasin.existe(str(u)) and magasin.lire(str(u)) == brut
    assert not magasin.ecrire(str(u), b"autre chose")["nouveau"] and magasin.lire(str(u)) == brut, "jamais réécrit"

def test_uuid7_croissant_et_versionne():
    a, b = uuid7(), uuid7()
    assert a.version == 7 and a.variant == uuid.RFC_4122
    assert a.bytes[:6] <= b.bytes[:6], "le préfixe est le temps : croissant"
