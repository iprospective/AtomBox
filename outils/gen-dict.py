#!/usr/bin/env python3
"""Génère le chapitre 16 du CDC (dictionnaire des données) depuis docs/dict/*.yml.

Les YAML sont la SOURCE ; le markdown est une VUE, synchronisée au wiki par
pm-wiki-sync. Le retaper à la main garantirait qu'il diverge :

    python3 outils/gen-dict.py
"""
import io, os, sys, yaml, datetime

def trouver_cdc():
    """Le CDC vit dans le dépôt PM, atteint par le lien .mmi-pm du workspace : on remonte
    depuis ce fichier jusqu'à le trouver — jamais un chemin en dur (D156, portabilité)."""
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs")
        if os.path.isdir(c): return c
        d = os.path.dirname(d)
    sys.exit("gen : aucun .mmi-pm/docs au-dessus de " + __file__ + " — passer CDC_DIR")

CDC = os.environ.get("CDC_DIR") or trouver_cdc()
DICT = os.path.join(CDC, "dict")
SORTIE = os.path.join(CDC, "cdc-rm2881-16-dictionnaire.md")

def charge(nom):
    return yaml.safe_load(io.open(os.path.join(DICT, nom + ".yml"), encoding="utf-8"))

def cel(v):
    if v is None: return "—"
    if isinstance(v, bool): return "oui" if v else "non"
    if isinstance(v, list): return ", ".join(str(x) for x in v) if v else "—"
    return str(v).replace("|", "\\|").replace("\n", " ").strip()

def refs(v):
    return ", ".join("**%s**" % x for x in v) if v else "—"

def table(cols, lignes):
    out = ["| " + " | ".join(c[0] for c in cols) + " |", "|" + "---|" * len(cols)]
    for l in lignes:
        out.append("| " + " | ".join(cel(c[1](l)) for c in cols) + " |")
    return "\n".join(out)

def g(k): return lambda d: d.get(k)

E = charge("entites"); CH = charge("champs"); REL = charge("relations")
EN = charge("enumerations"); WF = charge("workflows"); ACT = charge("actions")
TPL = charge("templates"); CMP = charge("composants"); PRO = charge("protocoles")
NOR = charge("normes"); ROU = charge("routes"); FEA = charge("fonctionnalites"); JAL = charge("jalons")

md = []
w = md.append
w("# 16 — Dictionnaire des données\n")
w("> **Fichier généré** le %s par `outils/gen-dict.py` depuis `docs/dict/*.yml`. Ne pas éditer à la "
  "main : modifier les YAML, qui sont la source — du CDC, du POC, et plus tard du DDL, des classes et "
  "de la spécification d'API dans le langage et le SGBD retenus.\n" % datetime.date.today().isoformat())
w("Ce chapitre fait autorité sur **ce qui existe** : entités, champs, relations, énumérations, workflows, "
  "actions, templates, composants, protocoles, normes, routes, fonctionnalités, jalons. Le registre des "
  "décisions (90) fait autorité sur **pourquoi**. Les types sont **logiques**, jamais SQL : le SGBD n'est "
  "pas définitivement statué.\n")
w("| Table | Lignes |\n|---|---|")
for nom, d in (("Entités", E), ("Relations", REL), ("Énumérations", EN), ("Workflows", WF),
               ("Actions", ACT), ("Templates", TPL), ("Protocoles", PRO), ("Normes", NOR),
               ("Routes", ROU), ("Fonctionnalités", FEA), ("Jalons", JAL)):
    n = len(d) if isinstance(d, list) else len(d)
    w("| %s | %d |" % (nom, n))
w("| Champs | %d |" % sum(len(v) for v in CH.values()))
w("| Composants | %d |" % sum(len(v) for v in CMP.values()))

# ---- entités ----
w("\n---\n\n## 16.1 — Entités\n")
for dom in ["communication", "stockage", "identite", "portee", "classement", "emission", "analyse", "interne", "exploitation"]:
    ents = [e for e in E if e.get("domaine") == dom]
    if not ents: continue
    w("\n### %s\n" % dom.capitalize())
    for e in ents:
        w("#### `%s` %s\n" % (e["nom"], e.get("etat", "")))
        w(cel(e.get("role")) + "\n")
        extra = []
        if e.get("partition"): extra.append("**Partition** : %s" % e["partition"])
        if e.get("jalon"): extra.append("**Jalon** : V%s" % e["jalon"])
        extra.append("**Décisions** : %s" % refs(e.get("decisions")))
        if e.get("notes"): extra.append("*%s*" % e["notes"])
        w("  \n".join(extra) + "\n")
        champs = CH.get(e["id"])
        if champs:
            w(table([("Champ", g("nom")), ("Type", g("type")), ("Oblig.", g("obligatoire")),
                     ("Nature", g("nature")), ("Rôle", g("role"))], champs) + "\n")

# ---- relations ----
w("\n---\n\n## 16.2 — Relations\n")
w(table([("De", g("de")), ("Vers", g("vers")), ("Card.", g("cardinalite")), ("Datée", g("datee")),
         ("Rôle", g("role")), ("Décision", g("decision"))], REL))

# ---- énumérations ----
w("\n\n---\n\n## 16.3 — Énumérations\n")
for nom, en in EN.items():
    w("\n### `%s`\n\n%s\n" % (nom, cel(en.get("role"))))
    vals = en.get("valeurs", [])
    cols = [("Valeur", g("id")), ("Libellé", g("libelle"))]
    for k in ("ordre", "jalon", "attend_action", "repondable", "entre_en_file", "geste_si_non_aligne", "sortie", "fille"):
        if any(k in v for v in vals): cols.append((k, g(k)))
    cols.append(("Note", g("note")))
    w(table(cols, vals))
    if en.get("questions"): w("\n*Questions ouvertes : %s*" % refs(en["questions"]))

# ---- workflows ----
w("\n\n---\n\n## 16.4 — Workflows\n")
for wf in WF:
    w("\n### %s\n" % wf["nom"])
    w("Entité `%s`%s — décisions %s\n" % (wf.get("entite"), (", champ `%s`" % wf["champ"]) if wf.get("champ") else "", refs(wf.get("decisions"))))
    if wf.get("etats"): w("États : %s\n" % " → ".join("`%s`" % s for s in wf["etats"]))
    if wf.get("regles"):
        w("\n".join("- %s" % r for r in wf["regles"]) + "\n")
    if wf.get("transitions"):
        w(table([("De", g("de")), ("Vers", g("vers")), ("Geste", g("geste")), ("Qui", g("qui")), ("Effet", g("effet"))], wf["transitions"]))
    if wf.get("garde_fous"):
        w("\n**Garde-fous** :\n" + "\n".join("- %s" % r for r in wf["garde_fous"]))
    if wf.get("questions"): w("\n*Questions : %s*" % refs(wf["questions"]))
    w("")

# ---- actions ----
w("\n---\n\n## 16.5 — Actions\n")
w("Chaque geste que l'interface ou l'API permet. *Portée* : ce que le geste modifie. *Trace* : écrit au journal (**D054**).\n")
w(table([("Action", g("libelle")), ("Contexte", g("contexte")), ("Portée", g("portee")), ("Effet", g("effet")),
         ("Trace", g("trace")), ("POC", g("poc")), ("Décisions", lambda a: refs(a.get("decisions")))], ACT))

# ---- templates ----
w("\n\n---\n\n## 16.6 — Templates (vues partielles)\n")
w("Le registre de vues partielles : chaque partielle est surchargeable par variante sans toucher au code appelant.\n")
w(table([("Partielle", lambda t: "`%s`" % t["nom"]), ("Contexte", g("contexte")), ("Rôle", g("role")),
         ("Surchargeable", g("surchargeable")), ("Variantes", g("variantes")), ("Appelle", g("appelle"))], TPL))

# ---- composants ----
w("\n\n---\n\n## 16.7 — Composants réutilisables\n")
for fam, lab in (("noyau", "Noyau technique"), ("capacite", "Capacités enfichables (D094)"), ("embarquable", "Composants embarquables (D108)")):
    w("\n### %s\n" % lab)
    cols = [("Composant", g("nom")), ("Rôle", g("role"))]
    if fam != "embarquable": cols.append(("Contrat", g("contrat")))
    if fam == "capacite": cols.append(("Fournisseurs", g("fournisseurs")))
    if fam == "embarquable": cols.append(("Exigences", g("exigences")))
    if fam == "noyau": cols.append(("POC", g("poc")))
    cols.append(("Décisions", lambda c: refs(c.get("decisions"))))
    w(table(cols, CMP[fam]))

# ---- protocoles ----
w("\n\n---\n\n## 16.8 — Protocoles\n")
w(table([("Protocole", g("nom")), ("Sens", g("sens")), ("Jalon", lambda p: "V%s" % p.get("jalon")), ("Rôle", g("role")),
         ("Normes", g("normes")), ("Décisions", lambda p: refs(p.get("decisions")))], PRO))

# ---- normes ----
w("\n\n---\n\n## 16.9 — Normes à respecter\n")
w("Une norme par ligne, avec le point précis qui engage AtomBox.\n")
w(table([("Référence", g("id")), ("Type", g("type")), ("Nom", g("nom")), ("Ce que ça engage", g("engage"))], NOR))

# ---- routes ----
w("\n\n---\n\n## 16.10 — Routes d'API\n")
w("> Hypothèse REST (**Q007** non tranchée) : ce tableau décrit les **opérations et leur portée**, pas un style définitif. "
  "Hors portée = 404, jamais 403 (**D108**).\n")
w(table([("Méthode", g("methode")), ("Chemin", lambda r: "`%s`" % r["chemin"]), ("Rôle", g("role")), ("Portée", g("portee")),
         ("Entités", g("entites")), ("État", g("etat")), ("Décisions", lambda r: refs(r.get("decisions")))], ROU))

# ---- ordre de réalisation : tri topologique du graphe depend_de ----
def ordre_realisation(feats):
    par = { f["id"]: f for f in feats }
    deps = { f["id"]: list(f.get("depend_de") or []) for f in feats }
    # Kahn, stable : à égalité, le jalon le plus bas puis l'identifiant
    entrants = { k: len(v) for k, v in deps.items() }
    suiv = {}
    for k, v in deps.items():
        for d in v: suiv.setdefault(d, []).append(k)
    prets = sorted([k for k, n in entrants.items() if n == 0], key=lambda k: (par[k].get("jalon") if par[k].get("jalon") is not None else 99, k))
    ordre = []
    while prets:
        k = prets.pop(0); ordre.append(k)
        for s2 in suiv.get(k, []):
            entrants[s2] -= 1
            if entrants[s2] == 0:
                prets.append(s2); prets.sort(key=lambda x: (par[x].get("jalon") if par[x].get("jalon") is not None else 99, x))
    cycle = [k for k, n in entrants.items() if n > 0]
    return ordre, cycle, par

# ---- jalons : la feuille de route DÉRIVÉE des fonctionnalités ----
# Deux vues des mêmes F… : ici par jalon, dans l'ordre de réalisation ; en 16.13 par domaine.
# Le « contenu » libre de jalons.yml devient une note d'intention ; la liste est calculée.
w("\n\n---\n\n## 16.11 — Feuille de route\n")
w("Chaque jalon liste **toutes** ses fonctionnalités (`F…`), **dans l'ordre de réalisation** (16.12). "
  "C'est la même donnée que 16.13, organisée par jalon plutôt que par domaine — aucune fonctionnalité "
  "n'existe hors d'un jalon, sauf celles écartées volontairement.\n")
_ordre_j, _cycle_j, _par_j = ordre_realisation(FEA)
_rang = { k: i for i, k in enumerate(_ordre_j) }
for j in JAL:
    v = int(j["id"].lstrip("V"))
    feats = sorted([f for f in FEA if f.get("jalon") == v], key=lambda f: (_rang.get(f["id"], 10**6), f["id"]))
    w("\n### %s — %s *(%s)* — %d fonctionnalités\n" % (j["id"], j["titre"], j.get("etat", ""), len(feats)))
    if j.get("note"): w("> %s\n" % j["note"])
    if j.get("contenu"):
        w("*Intention :* " + " · ".join(j["contenu"]) + "\n")
    w(table([("Ordre", lambda f: (_rang[f["id"]] + 1) if f["id"] in _rang else "—"), ("#", g("id")),
             ("Fonctionnalité", g("libelle")), ("Domaine", g("domaine")), ("État", g("etat")),
             ("Dépend de", lambda f: f.get("depend_de") if f.get("depend_de") is not None else "à renseigner")], feats))
_ecartees = [f for f in FEA if f.get("jalon") is None]
if _ecartees:
    w("\n### Écartées volontairement — %d\n" % len(_ecartees))
    w(table([("#", g("id")), ("Fonctionnalité", g("libelle")), ("État", g("etat")), ("Questions", lambda f: refs(f.get("questions")))], _ecartees))

w("\n---\n\n## 16.12 — Ordre de réalisation\n")
w("Calculé depuis `depend_de` (tri topologique, stable par jalon puis identifiant). **C'est l'ordre "
  "dans lequel coder** : une fonctionnalité n'apparaît qu'après tout ce dont elle dépend. Les "
  "identifiants `F…` sont stables — on n'en réattribue jamais un.\n")
_ordre, _cycle, _par = ordre_realisation(FEA)
_ren = [f for f in FEA if f.get("depend_de") is not None]
w("| Renseignées | Racines (aucune dépendance) | À renseigner (`null`) | Cycle |\n|---|---|---|---|")
w("| %d / %d | %d | %d | %s |" % (len(_ren), len(FEA), sum(1 for f in _ren if not f["depend_de"]),
   len(FEA) - len(_ren), ("⚠ " + ", ".join(_cycle)) if _cycle else "aucun"))
w("")
w(table([("Rang", lambda k: _ordre.index(k) + 1), ("#", lambda k: k), ("Fonctionnalité", lambda k: _par[k]["libelle"]),
         ("Jalon", lambda k: "V%s" % _par[k]["jalon"] if _par[k].get("jalon") is not None else "—"),
         ("Dépend de", lambda k: _par[k].get("depend_de") or "—")],
        [k for k in _ordre if _par[k].get("depend_de") is not None]))
w("\n*Les fonctionnalités dont `depend_de` est encore `null` ne figurent pas dans l'ordre : elles sont à renseigner.*\n")

w("\n---\n\n## 16.13 — Fonctionnalités\n")
w("La même liste que la page « Fonctionnalités » du POC — c'est la même source.\n")
doms = []
for f in FEA:
    if f["domaine"] not in doms: doms.append(f["domaine"])
for dom in doms:
    w("\n### %s\n" % dom)
    w(table([("#", g("id")), ("Fonctionnalité", g("libelle")), ("Jalon", lambda f: "V%s" % f["jalon"] if f.get("jalon") is not None else "—"),
             ("État", g("etat")), ("Dépend de", lambda f: f.get("depend_de") if f.get("depend_de") is not None else "à renseigner"),
             ("Décisions", lambda f: refs(f.get("decisions"))), ("Questions", lambda f: refs(f.get("questions")))],
            [f for f in FEA if f["domaine"] == dom]))

io.open(SORTIE, "w", encoding="utf-8").write("\n".join(md) + "\n")
print("%s : %d entités, %d champs, %d relations, %d actions, %d routes, %d fonctionnalités"
      % (os.path.relpath(SORTIE), len(E), sum(len(v) for v in CH.values()), len(REL), len(ACT), len(ROU), len(FEA)))
