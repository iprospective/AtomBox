"""F002 — le magasin d'octets : ab/cd/<id>, jamais réécrit, zstd conditionnel, lecture transparente."""
import os, uuid, pytest
from atombox.store import Store, fingerprint
from atombox.uuid7 import uuid7

@pytest.fixture
def store(tmp_path): return Store(str(tmp_path / "magasin"))

def test_chemin_ab_cd(store):
    e = "abcdef0123456789" * 4
    assert store.path(e).endswith(os.path.join("ab", "cd", e))
    u = str(uuid7())
    assert store.path(u).endswith(os.path.join(u[:2], u[2:4], u))
    with pytest.raises(ValueError): store.path("../evasion")

def test_deposer_lit_et_dedoublonne(store):
    raw_bytes = b"facture " * 1000
    e, info = store.put(raw_bytes)
    assert e == fingerprint(raw_bytes) and info["nouveau"] and info["compression"] == "zstd" and info["taille_stockee"] < len(raw_bytes)
    assert store.read(e) == raw_bytes
    e2, info2 = store.put(raw_bytes)
    assert e2 == e and not info2["nouveau"], "le même contenu n'est pas réécrit"

def test_compression_conditionnelle(store):
    aleatoire = os.urandom(4096)
    e, info = store.put(aleatoire)
    assert info["compression"] == "aucune" and info["taille_stockee"] == 4096, "ne pas compresser ce qui ne gagne rien (D069)"
    assert store.read(e) == aleatoire

def test_message_brut_sous_uuid(store):
    u = uuid7(); raw = b"From: a@b\r\n\r\nbonjour\r\n" * 50
    info = store.write(str(u), raw)
    assert info["nouveau"] and store.exists(str(u)) and store.read(str(u)) == raw
    assert not store.write(str(u), b"autre chose")["nouveau"] and store.read(str(u)) == raw, "jamais réécrit"

def test_uuid7_croissant_et_versionne():
    a, b = uuid7(), uuid7()
    assert a.version == 7 and a.variant == uuid.RFC_4122
    assert a.bytes[:6] <= b.bytes[:6], "le préfixe est le temps : croissant"


def test_ab_cd_decoupe_le_temps_pas_l_espace(tmp_path):
    """D145b — la propriété mesurée au chapitre 20, figée ici : un code qui changerait
    l'adressage sans y penser casserait ce test, et relirait la décision."""
    from atombox.uuid7 import uuid7
    from atombox.store.store import Store, fingerprint
    m = Store(str(tmp_path))

    ids = [str(uuid7()) for _ in range(500)]
    feuilles = {i[:4] for i in ids}
    assert len(feuilles) == 1, "500 UUID v7 émis d'affilée partagent leur répertoire (préfixe temporel)"

    blobs = {fingerprint(("%d" % k).encode())[:4] for k in range(500)}
    assert len(blobs) > 400, "les blobs, eux, se répartissent : l'empreinte est aléatoire"

    # et le chemin reste calculable, sans index
    i = ids[0]
    assert m.path(i).endswith("/%s/%s/%s" % (i[:2], i[2:4], i))
