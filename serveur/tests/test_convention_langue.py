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
    # étage 2 — l'infrastructure : ce que tout le reste importe, donc ce qu'on convertit d'abord
    "atombox/journal.py",
    "atombox/db.py",
    "atombox/served_uid.py",
    "atombox/store/store.py",
    "atombox/settings.py",
    "atombox/uuid7.py",
    # étage 2b — la couche IMAP, de bout en bout : le protocole, la vue, la session, l'écouteur
    "atombox/imap/protocol.py",
    "atombox/imap/view.py",
    "atombox/imap/session.py",
    "atombox/imap/serveur.py",   # le FICHIER garde son nom : une unité systemd le nomme (étage 2bis)
    # étage 2c — l'ingestion et la synchronisation : les définitions, pas les locales
    "atombox/sync/sync.py",
    "atombox/ingestion/identite.py",
)

# Un dictionnaire, comme celui des réglages : des MOTS, pas une grammaire. Une heuristique sur les
# terminaisons (-er, -ir) prendrait `set_marker`, `polling` ou `folder` pour du français.
MOTS_FR = ("deplacer", "poser", "retirer", "ouvrir", "toucher", "etat", "etats", "dossier",
           "boite", "compte", "drapeau", "drapeaux", "marqueur", "marqueurs", "semer", "semences",
           "assurer", "tracer", "lire", "courant", "cible", "avant", "apres", "sortie", "sorties",
           "requete", "preparer", "verifier", "annuler", "releveur", "servi", "nom", "valeur",
           "maintenant", "modifiables", "corbeille", "integres", "travail", "court",
           # étage 2 — les mots retirés de l'infrastructure
           "magasin", "moteur", "fabrique", "niveau", "niveaux", "configurer", "attribuer",
           "domaines", "fichier", "verrou", "defaut", "forcer", "rendu", "normaliser", "racine",
           "magie", "seuil",   # pas "gain" : le mot est le même dans les deux langues
           # étage 2b — les mots retirés de la couche IMAP
           "litteral", "decouper", "citer", "crochets", "capacites", "selectionne", "selectionner",
           "authentifie", "chercher", "correspond", "rafraichir", "relever", "servie", "accueil",
           "criteres", "demandes", "seule", "methode", "motif", "silencieux", "vises", "trouves",
           "rendus", "frais", "anciens", "nouveaux", "presents", "permanents", "connus", "inconnus",
           "mdp", "texte", "vue", "ajouter", "contient", "aiguille", "champ", "champs", "couples",
           "attributs", "enveloppe", "octets", "brut", "tete", "annule", "ecouteur", "limite",
           "contexte", "envoyer", "ecrivain", "lecteur", "donnees", "hote", "places", "vivantes",
           "reponses", "attendu", "serveur", "principal",
           # étage 2c — les mots retirés de l'ingestion, de la synchronisation et du magasin
           "entetes", "valeurs", "releve", "ingerer", "descendante", "voulus", "analyser",
           "normaliser", "deposer", "existe", "chemin", "compresser", "remplacer", "ecrire",
           "surveiller", "resynchroniser", "suivant")


def test_les_fichiers_convertis_restent_en_anglais():
    """Chaque identifiant DÉFINI dans un fichier converti est en anglais — le mot français y est
    une régression, pas un choix de style.

    LES MÉTHODES COMPTENT. La première version de ce test ancrait son motif en colonne 0 : elle ne
    voyait donc que les fonctions et les classes de premier niveau, et pas une seule méthode. Des
    fichiers entiers de contrôleurs — dont tout le travail EST dans des méthodes — passaient au
    vert sans que rien n'ait été converti. Un garde-fou qui ne regarde pas où ça se passe rassure,
    ce qui est pire que de ne pas exister."""
    fautifs = {}
    for rel in CONVERTIS:
        f = RACINE / rel
        assert f.exists(), "fichier converti introuvable : %s (déplacé ? retirer de CONVERTIS)" % rel
        for nom in re.findall(r"^\s*(?:async )?(?:def|class)\s+(\w+)|^([A-Z][A-Z0-9_]{2,})\s*=",
                              f.read_text(encoding="utf-8"), re.M):
            nom = nom[0] or nom[1]
            morceaux = {m for m in nom.lower().split("_") if m}
            trouves = morceaux & set(MOTS_FR)
            if trouves: fautifs.setdefault(rel, []).append("%s (%s)" % (nom, ", ".join(sorted(trouves))))
    assert not fautifs, "identifiants français dans des fichiers convertis :\n" + "\n".join(
        "  %s : %s" % (f, ", ".join(n)) for f, n in sorted(fautifs.items()))


# `getattr(obj, "nom")` nomme un attribut par une CHAÎNE. Un renommage d'identifiants ne la voit
# pas — c'est précisément ce qu'on lui demande, pour que les commentaires et les chemins par défaut
# ne bougent pas. Mais quand la chaîne EST un nom d'attribut, elle doit suivre, et rien ne le dit.
#
# Les trois formes, parce que la plus dangereuse des trois n'était PAS un `getattr` : la garde
# d'authentification du serveur IMAP lisait `method.__dict__.get("_authentifie")`. Un motif qui ne
# cherche que `getattr` aurait laissé passer exactement celui qui comptait.
ATTRIBUT_PAR_CHAINE = re.compile(
    r"\b(?:get|set|has)attr\s*\(\s*[^,()]+,\s*[\"'](\w+)[\"']"      # getattr(o, "x")
    r"|__dict__\s*\.\s*get\s*\(\s*[\"'](\w+)[\"']"                  # o.__dict__.get("x")
    r"|__dict__\s*\[\s*[\"'](\w+)[\"']")                            # o.__dict__["x"]


def test_aucun_attribut_nomme_par_une_chaine_francaise():
    """Trois fois dans la même passe, un attribut nommé par une chaîne est resté en arrière.

    Le pire des trois était muet : `method.__dict__.get("_authentifie")` cherchait l'ancien nom
    tandis que le décorateur posait le nouveau, et le serveur IMAP répondait à SELECT **sans
    authentification**. Les deux autres faisaient taire un compteur de test et la garde anti-boucle
    de la synchronisation — un test au rouge dans un cas, rien du tout dans l'autre.

    Ce que ces trois-là ont en commun n'est pas le hasard : un identifiant écrit dans une chaîne
    échappe à l'outil, donc il faut un test qui regarde les chaînes."""
    fautifs = {}
    for rel in CONVERTIS:
        f = RACINE / rel
        for groupes in ATTRIBUT_PAR_CHAINE.findall(f.read_text(encoding="utf-8")):
            attr = next(g for g in groupes if g)
            trouves = {m for m in attr.lower().split("_") if m} & set(MOTS_FR)
            if trouves:
                fautifs.setdefault(rel, []).append("%s (%s)" % (attr, ", ".join(sorted(trouves))))
    assert not fautifs, ("un attribut est nommé par une chaîne restée en français — l'outil de "
                         "renommage ne touche pas aux chaînes :\n" + "\n".join(
                             "  %s : %s" % (f, ", ".join(n)) for f, n in sorted(fautifs.items())))
