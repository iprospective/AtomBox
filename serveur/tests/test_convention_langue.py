"""D181 — les identifiants en anglais, la prose en français.

Sans contrôle, une convention de nommage se perd au premier ajout : celui qui écrit la ligne
suivante copie ce qu'il voit au-dessus. Ce test rend la règle exécutoire là où elle compte le plus,
c'est-à-dire sur la SURFACE DE CONFIGURATION — ce qu'un exploitant tape sans connaître le projet.

Il ne contrôle PAS les identifiants de programme : leur conversion est opportuniste (on traduit un
fichier quand on y touche), donc un contrôle strict serait rouge pendant des mois et finirait
désactivé. Ce qui est fini se verrouille ; ce qui est en cours se mesure.
"""
from __future__ import annotations
import pathlib
import re
import subprocess

RACINE = pathlib.Path(__file__).resolve().parent.parent

# Des mots français qu'on ne veut plus voir dans un nom de variable d'environnement ou d'option.
FRANCAIS = ("HOTE", "MOT_DE_PASSE", "UTILISATEUR", "MAGASIN", "NIVEAU", "CIBLE", "ECOUTE",
            "PUBLIQUE", "EXPEDITEUR", "SECONDES", "TACHES", "TRACER", "MDP")
OPTIONS_FR = ("--boite", "--mot-de-passe", "--nom", "--partagee", "--email-secours", "--garder",
              "--racine", "--quand-meme", "--cle")


# Ce fichier-ci PORTE la liste des mots interdits, et `settings.py` porte celle des anciens noms :
# tous deux se détecteraient eux-mêmes. Ils s'excluent, et c'est la seule exception.
DICTIONNAIRES = ("settings.py", "test_convention_langue.py")


def _fichiers(*motifs):
    sortie = subprocess.run(["git", "ls-files"] + list(motifs), cwd=RACINE.parent,
                            capture_output=True, text=True).stdout.split()
    return [RACINE.parent / f for f in sortie if pathlib.Path(f).name not in DICTIONNAIRES]


def test_aucune_variable_d_environnement_en_francais():
    """La table de repli de `settings.py` est la seule exception : elle NOMME les anciens."""
    fautives = {}
    for f in _fichiers("*.py", "*.sh", "*.service", "*.exemple", "*.md"):
        if not f.exists(): continue
        texte = f.read_text(errors="replace")
        for nom in set(re.findall(r"\bATOMBOX_[A-Z_]+\b", texte)):
            if any(mot in nom for mot in FRANCAIS):
                fautives.setdefault(nom, []).append(f.name)
    assert not fautives, "réglages encore en français : " + ", ".join(
        "%s (%s)" % (n, ", ".join(sorted(set(v)))) for n, v in sorted(fautives.items()))


def test_aucune_option_de_ligne_de_commande_en_francais():
    fautives = {}
    for f in _fichiers("*.py", "*.sh"):
        if not f.exists(): continue
        texte = f.read_text(errors="replace")
        for opt in OPTIONS_FR:
            if re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(opt), texte):
                fautives.setdefault(opt, []).append(f.name)
    assert not fautives, "options encore en français : " + ", ".join(
        "%s (%s)" % (o, ", ".join(sorted(set(v)))) for o, v in sorted(fautives.items()))


def test_le_repli_nomme_son_remplacant():
    """Un avertissement qui dit « c'est vieux » sans dire par quoi le remplacer ne sert à rien."""
    from atombox.settings import FORMER_NAMES
    assert FORMER_NAMES, "la table de repli existe tant que des instances portent les anciens noms"
    for neuf, ancien in FORMER_NAMES.items():
        assert neuf.startswith("ATOMBOX_") and ancien.startswith("ATOMBOX_")
        assert neuf != ancien
        assert not any(mot in neuf for mot in FRANCAIS), "le NOUVEAU nom %s est encore français" % neuf


# ── la passe en anglais (RM3351, D181) : ce qui est CONVERTI ne régresse pas ────────────────────
# La passe se fait par étages — le code est trop gros pour un seul geste, et une branche voisine ne
# doit pas tomber en conflit avec l'ensemble. Ce test porte donc la LISTE de ce qui est déjà
# converti : ajouter un fichier à `CONVERTIS` le met sous garde, et rien ne peut l'y ramener au
# français sans faire rougir la suite.
#
# Les COMMENTAIRES restent en français (consigne explicite) : on ne regarde que les identifiants
# définis — `def`, `class`, et les constantes de module.
CONVERTIS = (
    "atombox/services/mailbox.py",
    "atombox/services/personal_state.py",
    "atombox/services/trace.py",
    "atombox/schema/seeds.py",
)

# Un dictionnaire, comme celui des réglages : des MOTS, pas une grammaire. Une heuristique sur les
# terminaisons (-er, -ir) prendrait `set_marker`, `polling` ou `folder` pour du français.
MOTS_FR = ("deplacer", "poser", "retirer", "ouvrir", "toucher", "etat", "etats", "dossier",
           "boite", "compte", "drapeau", "drapeaux", "marqueur", "marqueurs", "semer", "semences",
           "assurer", "tracer", "lire", "courant", "cible", "avant", "apres", "sortie", "sorties",
           "requete", "preparer", "verifier", "annuler", "releveur", "servi", "nom", "valeur",
           "maintenant", "modifiables", "corbeille", "integres", "travail", "court")


def test_les_fichiers_convertis_restent_en_anglais():
    """Chaque identifiant DÉFINI dans un fichier converti est en anglais — le mot français y est
    une régression, pas un choix de style."""
    fautifs = {}
    for rel in CONVERTIS:
        f = RACINE / rel
        assert f.exists(), "fichier converti introuvable : %s (déplacé ? retirer de CONVERTIS)" % rel
        for nom in re.findall(r"^(?:async )?(?:def|class)\s+(\w+)|^([A-Z][A-Z0-9_]{2,})\s*=",
                              f.read_text(encoding="utf-8"), re.M):
            nom = nom[0] or nom[1]
            morceaux = {m for m in nom.lower().split("_") if m}
            trouves = morceaux & set(MOTS_FR)
            if trouves: fautifs.setdefault(rel, []).append("%s (%s)" % (nom, ", ".join(sorted(trouves))))
    assert not fautifs, "identifiants français dans des fichiers convertis :\n" + "\n".join(
        "  %s : %s" % (f, ", ".join(n)) for f, n in sorted(fautifs.items()))
