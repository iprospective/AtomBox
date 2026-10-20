#!/usr/bin/env python3
"""Renomme des IDENTIFIANTS Python — et rien d'autre. L'outil de la passe en anglais (RM3351, D181).

POURQUOI PAS `sed`. Un `sed` sur `\\bmagasin\\b` touche trois choses qu'il ne doit pas toucher :
les COMMENTAIRES (qui restent en français — c'est la consigne), les CHAÎNES (`"./magasin"` est un
chemin par défaut, `/var/lib/atombox/magasin` le magasin déployé : les renommer change le
comportement sans toucher au code), et les NOMS DE COLONNES qui ressemblent à des variables.

On passe donc par `tokenize` : on ne repère que les jetons NAME, et on remplace le texte à leurs
positions — le fichier n'est pas regénéré, donc l'espacement sort à l'octet.

DEUX GARDE-FOUS, chacun né d'une faute réelle :

1. **Une règle sans effet est une erreur.** Faute de frappe, ou travail déjà fait : dans les deux
   cas on veut le savoir avant d'écrire, pas après. Rien n'est écrit si une règle ne porte pas.

2. **Un mot du dictionnaire est refusé.** Quatre fois dans la même journée, un renommage a pris une
   colonne pour une variable locale : `comm.taille`, `Dossier.nom`, `acces.debut`, `Acces(debut=…)`.
   Chacune s'est vue au rouge — mais après coup. Le dictionnaire SAIT lesquels de ces mots sont des
   colonnes ou des entités ; il suffisait de le lui demander AVANT. Les colonnes se renomment à
   l'étage 3 (avec le contrat d'API et une migration), les entités à l'étage 4.

   Quand le jeton n'est PAS la colonne dans le périmètre traité — `m.taille` d'un message servi est
   à nous —, on l'assume en terminant la règle par « ! ». L'exception devient alors visible dans le
   fichier de règles, ce qui est tout l'intérêt.

Usage :
    rename-identifiers.py <regles.txt> <fichier.py…>
    rename-identifiers.py --no-dict <regles.txt> <fichier.py…>

Un fichier de règles : une par ligne, « ancien -> nouveau », « # » en commentaire, « ! » en fin de
ligne pour assumer un mot du dictionnaire.
"""
from __future__ import annotations
import collections
import io
import os
import pathlib
import sys
import tokenize

try:
    import yaml
except ImportError:                                           # pragma: no cover
    yaml = None


def load(p):
    rules, assumes = {}, set()
    for line in pathlib.Path(p).read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        assume = line.endswith("!")
        a, n = [x.strip() for x in line.rstrip("!").split("->")]
        rules[a] = n
        if assume:
            assumes.add(a)
    return rules, assumes


def trouver_dict():
    """le dossier `dict/` du CDC — cherché en remontant, comme le fait `api/routage.py`"""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs", "dict")
        if os.path.isdir(c):
            return c
        d = os.path.dirname(d)
    cdc = os.environ.get("CDC_DIR")
    return os.path.join(cdc, "dict") if cdc else None


def reserves():
    """les noms de COLONNES et d'ENTITÉS, lus au dictionnaire — il fait autorité là-dessus"""
    d = trouver_dict()
    if d is None or yaml is None:
        return None
    names = set()
    champs = yaml.safe_load(open(os.path.join(d, "champs.yml"), encoding="utf-8")) or {}
    for entite, listing in champs.items():
        names.add(entite)
        for c in listing or []:
            if isinstance(c, dict) and c.get("nom"):
                names.add(str(c["nom"]))
    entites = yaml.safe_load(open(os.path.join(d, "entites.yml"), encoding="utf-8")) or []
    for e in entites:
        for k in ("id", "nom"):
            if isinstance(e, dict) and e.get(k):
                names.add(str(e[k]))
    return names


def reecrire(src: str, rules: dict, compte: collections.Counter) -> str:
    lines = src.splitlines(keepends=True)
    # Les jetons à remplacer, traités de la FIN vers le DÉBUT : sinon le premier remplacement
    # décale les positions de tous les suivants.
    cibles = [t for t in tokenize.generate_tokens(io.StringIO(src).readline)
              if t.type == tokenize.NAME and t.string in rules]
    for tok in reversed(cibles):
        i, (_, c0), (_, c1) = tok.start[0] - 1, tok.start, tok.end
        lines[i] = lines[i][:c0] + rules[tok.string] + lines[i][c1:]
        compte[tok.string] += 1
    return "".join(lines)


def main(argv):
    args = list(argv)
    avec_dict = True
    if args and args[0] == "--no-dict":
        avec_dict, args = False, args[1:]
    if len(args) < 2:
        print(__doc__.strip().splitlines()[0])
        return 64
    rules, assumes = load(args[0])
    fichiers = [pathlib.Path(f) for f in args[1:]]

    if avec_dict:
        interdits = reserves()
        if interdits is None:
            print("✗ dictionnaire introuvable (ou PyYAML absent). Le garde-fou qui empêche de "
                  "renommer une COLONNE ne peut pas tourner ; --no-dict pour s'en passer.")
            return 3
        heurts = sorted(a for a in rules if a in interdits and a not in assumes)
        if heurts:
            print("✗ ces mots sont des COLONNES ou des ENTITÉS au dictionnaire — les renommer ici "
                  "casserait l'accès à la base :\n    " + ", ".join(heurts))
            print("  Les colonnes passent à l'étage 3 (avec le contrat d'API et une migration), les")
            print("  entités à l'étage 4. Si le jeton n'est PAS la colonne ici, termine la règle par « ! ».")
            return 2

    compte = collections.Counter()
    nouveaux = {}
    for f in fichiers:
        before = dict(compte)
        res = reecrire(f.read_text(encoding="utf-8"), rules, compte)
        if dict(compte) != before:
            nouveaux[f] = res

    inutiles = [a for a in rules if not compte[a]]
    if inutiles:
        print("✗ règles sans effet (faute de frappe, ou déjà fait) — rien n'a été écrit :\n    "
              + ", ".join(sorted(inutiles)))
        return 1

    for f, res in nouveaux.items():
        f.write_text(res, encoding="utf-8")
    for a, n in sorted(rules.items()):
        print("  %-28s → %-28s %3d" % (a, n, compte[a]))
    print("✓ %d fichier(s) réécrit(s), %d jeton(s)" % (len(nouveaux), sum(compte.values())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
