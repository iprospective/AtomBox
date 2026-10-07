"""Les unités systemd nomment des modules — et un nom de module est un CONTRAT DE DÉPLOIEMENT.

`ExecStart=… -m atombox.imap.server` vit dans deux endroits : le dépôt, et
`/etc/systemd/system/` sur la machine servie. Le déployeur ne réinstalle pas les unités (il dit
comment le faire) : renommer le module dans le dépôt fait donc échouer le service au prochain
démarrage, avec un `ModuleNotFoundError` que personne ne lit — le service est simplement « failed ».

Ce test est la garde qui rend ce renommage POSSIBLE : il refuse qu'une unité nomme un module qui
n'existe pas. Le jour où l'on convertit ces noms en anglais (RM3351, étage 2bis), il rougit
jusqu'à ce que l'unité soit changée elle aussi, dans le même commit.

Il ne regarde pas la machine : un test ne doit pas dépendre de ce qui est installé. Il compare le
dépôt à lui-même — ce qui suffit, parce que l'unité du dépôt est la SOURCE de celle qui est posée.
"""
from __future__ import annotations
import importlib.util
import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parent.parent


def _execstart():
    for u in sorted((RACINE / "outils").glob("*.service")):
        for line in u.read_text(encoding="utf-8").splitlines():
            if line.startswith("ExecStart="):
                yield u.name, line


def test_les_modules_nommes_par_les_unites_existent():
    """`-m atombox.x.y` et `uvicorn atombox.x.y:app` doivent désigner un module importable."""
    manquants = []
    for nom, line in _execstart():
        for module in (re.findall(r"-m\s+(atombox[\w.]*)", line)
                       + re.findall(r"\s(atombox[\w.]*):", line)):
            if importlib.util.find_spec(module) is None:
                manquants.append("%s → %s" % (nom, module))
    assert not manquants, ("une unité nomme un module qui n'existe pas — le service ne démarrera "
                           "pas, et son journal ne dira que « failed » : " + ", ".join(manquants))


def test_chaque_unite_de_service_a_bien_un_execstart():
    """Sinon le test ci-dessus passerait au vert en ne regardant rien."""
    vues = {nom for nom, _ in _execstart()}
    attendues = {f.name for f in (RACINE / "outils").glob("*.service")}
    assert vues == attendues, "unités sans ExecStart : " + ", ".join(sorted(attendues - vues))
