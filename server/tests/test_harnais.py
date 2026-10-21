"""Le harnais se teste lui-même : sans ça, tout le reste ne prouve rien (RM3165)."""
from pathlib import Path


def test_le_code_teste_est_celui_du_repertoire_courant():
    """Un venv partagé entre worktrees fait importer le code du voisin. Ce contrôle casse AVANT
    qu'on passe une heure à chercher pourquoi une route neuve répond 405."""
    import atombox
    attendu = Path(__file__).resolve().parent.parent / "atombox" / "__init__.py"
    obtenu = Path(atombox.__file__).resolve()
    assert obtenu == attendu, (
        "pytest exécute %s alors qu'on teste %s — le venv est installé en editable sur un AUTRE "
        "worktree. tests/conftest.py doit mettre la racine en tête de sys.path." % (obtenu, attendu))
