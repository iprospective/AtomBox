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
UNITES = RACINE / "tools"


def _execstart():
    for u in sorted(UNITES.glob("*.service")):
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
    """Sinon le test ci-dessus passerait au vert en ne regardant rien.

    ET IL L'A FAIT. Quand `serveur/outils/` est devenu `serveur/tools/` (RM3351, étage 2d), ce test
    comparait deux ensembles VIDES — aucune unité trouvée, aucune attendue — et passait au vert.
    Le test d'à côté, lui, ne trouvait aucun ExecStart à vérifier, et passait aussi. La garde
    écrite pour le jour du renommage a été désarmée par le renommage lui-même, et rien ne l'a dit.
    D'où la première assertion : on sait combien d'unités le serveur déploie, et zéro n'en est pas
    un nombre possible."""
    attendues = {f.name for f in UNITES.glob("*.service")}
    assert attendues, ("aucune unité systemd sous %s — le dossier a bougé ? Sans unités, ce fichier "
                       "ne vérifie RIEN et passe au vert" % UNITES)
    vues = {nom for nom, _ in _execstart()}
    assert vues == attendues, "unités sans ExecStart : " + ", ".join(sorted(attendues - vues))


def _rendre(*args):
    import subprocess
    out = {}
    for u in sorted(UNITES.glob("atombox-*.service")):
        if u.name == "atombox-tunnel.service": continue          # posée à part (RM3267)
        out[u.name] = subprocess.run(["bash", str(UNITES / "render-unit.sh"), *args], input=u.read_text(encoding="utf-8"),
                                     capture_output=True, text=True, check=True).stdout
    return out


def test_le_rendu_commun_ne_laisse_aucun_marqueur():
    """RM3516 — un seul rendu (render-unit.sh) pour dev et pour une machine dédiée. Sans paramètre, il
    rend l'unité du conteneur dev, à l'identique de ce qui y est installé ; avec un utilisateur et un
    venv, celle de mmi. Un marqueur oublié, c'est un service qui ne démarre pas."""
    dev = _rendre("/srv/x")
    assert dev and all("__" not in t for t in dev.values()), "marqueur non rendu"
    assert all("User=mathieu" in t and "/srv/x/.venv/bin/" in t for t in dev.values())
    dediee = _rendre("/opt/atombox/current/server", "atombox", "/opt/atombox/venv")
    assert all("User=atombox" in t and "Group=atombox" in t and "ExecStart=/opt/atombox/venv/bin/" in t
               and "WorkingDirectory=/opt/atombox/current/server" in t for t in dediee.values())


def test_les_scripts_de_deploiement_se_lisent():
    import subprocess
    for s in ("render-unit.sh", "install-host.sh", "ship.sh", "deploy.sh", "deploy-apache.sh"):
        r = subprocess.run(["bash", "-n", str(UNITES / s)], capture_output=True, text=True)
        assert r.returncode == 0, "%s : %s" % (s, r.stderr)


def test_l_exemple_d_environnement_n_a_pas_de_commentaire_en_fin_de_ligne():
    """systemd (EnvironmentFile) ne connaît pas le commentaire de fin de ligne : `X=a   # note` donne la
    valeur « a   # note ». L'exemple en avait un — sur ATOMBOX_IMAP_MASTER, rien de moins."""
    fautives = [l for l in (UNITES / "atombox.env.example").read_text(encoding="utf-8").splitlines()
                if re.match(r"^[A-Z_]+=.*\s#", l)]
    assert not fautives, fautives
