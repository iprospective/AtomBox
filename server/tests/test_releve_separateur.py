"""La relève traduit le séparateur de hiérarchie du fournisseur — à la frontière, et nulle part ailleurs.

Mesuré le 21/10 sur la machine servie : le fournisseur (Dovecot) sépare les niveaux par un POINT.
AtomBox, lui, sert « / » et range ses alias avec « / ». Thunderbird a créé « truc » sous la boîte de
réception : AtomBox a envoyé `CREATE INBOX/truc`, le fournisseur a refusé, et Thunderbird n'a lu
qu'« erreur interne ».

On éprouve la relève contre un faux fournisseur qui parle avec un POINT, comme le vrai.
"""
from __future__ import annotations
import pytest

from doublures import FauxImap


class FournisseurAPoint(FauxImap):
    SEP = "."


@pytest.fixture
def fournisseur():
    f = FournisseurAPoint(dossiers=("INBOX", "Sent", "Projets", "Projets.Dupont"))
    f.start()
    yield f
    f.arret = True


def _releve(f):
    from atombox.ingestion.imap import Poller
    return Poller("127.0.0.1", f.port, tls=False).connect("contact@exemple.fr", "x")


def test_le_separateur_du_fournisseur_est_lu(fournisseur):
    r = _releve(fournisseur)
    try:
        assert r.delimiter() == "."
    finally:
        r.close()


def test_ses_sous_dossiers_arrivent_comme_une_hierarchie(fournisseur):
    """« Projets.Dupont » chez lui, c'est « Projets/Dupont » chez nous — un sous-dossier, pas un nom
    contenant un point"""
    r = _releve(fournisseur)
    try:
        assert r.folders() == ["INBOX", "Sent", "Projets", "Projets/Dupont"]
    finally:
        r.close()


def test_ce_qu_on_lui_envoie_porte_son_separateur(fournisseur):
    r = _releve(fournisseur)
    try:
        r.create_folder("INBOX/truc")
        r.select_folder("Projets/Dupont")
    finally:
        r.close()
    envoye = " | ".join(fournisseur.journal)
    assert 'CREATE "INBOX.truc"' in envoye, envoye
    assert '"Projets.Dupont"' in envoye and "Projets/Dupont" not in envoye, envoye


def test_un_refus_du_fournisseur_se_lit_comme_un_refus():
    """`FolderRefused` (CANNOT) et sa raison — pas une RuntimeError qui devient « erreur interne »"""
    from atombox.services import folders_util as f

    class Refuse:
        def create_folder(self, nom): raise RuntimeError("CREATE %s : NO" % nom)
        def close(self): pass

    ancien = f._poller_for
    f._poller_for = lambda adresse: Refuse()
    try:
        with pytest.raises(f.FolderRefused) as e:
            f._mirror("contact@exemple.fr", "create_folder", "INBOX/truc")
        assert e.value.code == "CANNOT" and "le fournisseur refuse" in str(e.value)
    finally:
        f._poller_for = ancien
