#!/usr/bin/env python3
"""Génère le chapitre 16 du CDC (dictionnaire des données) depuis docs/dict/*.yml.

Les YAML sont la SOURCE ; le markdown est une VUE, synchronisée au wiki par
pm-wiki-sync. Le retaper à la main garantirait qu'il diverge :

    python3 outils/gen-dict.py
"""
import io, os, sys, yaml, datetime

CDC = os.environ.get("CDC_DIR",
    "/zfs/workspaces/iprospective/dev/atombox-webmail/.mmi-pm/docs")
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
w("Chaque geste que l'interface ou l'API permet. *Portée* : ce que le geste modifie. *Trace* : écrit au journal (**D54**).\n")
w(table([("Action", g("libelle")), ("Contexte", g("contexte")), ("Portée", g("portee")), ("Effet", g("effet")),
         ("Trace", g("trace")), ("POC", g("poc")), ("Décisions", lambda a: refs(a.get("decisions")))], ACT))

# ---- templates ----
w("\n\n---\n\n## 16.6 — Templates (vues partielles)\n")
w("Le registre de vues partielles : chaque partielle est surchargeable par variante sans toucher au code appelant.\n")
w(table([("Partielle", lambda t: "`%s`" % t["nom"]), ("Contexte", g("contexte")), ("Rôle", g("role")),
         ("Surchargeable", g("surchargeable")), ("Variantes", g("variantes")), ("Appelle", g("appelle"))], TPL))

# ---- composants ----
w("\n\n---\n\n## 16.7 — Composants réutilisables\n")
for fam, lab in (("noyau", "Noyau technique"), ("capacite", "Capacités enfichables (D94)"), ("embarquable", "Composants embarquables (D108)")):
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
w("> Hypothèse REST (**Q07** non tranchée) : ce tableau décrit les **opérations et leur portée**, pas un style définitif. "
  "Hors portée = 404, jamais 403 (**D108**).\n")
w(table([("Méthode", g("methode")), ("Chemin", lambda r: "`%s`" % r["chemin"]), ("Rôle", g("role")), ("Portée", g("portee")),
         ("Entités", g("entites")), ("État", g("etat")), ("Décisions", lambda r: refs(r.get("decisions")))], ROU))

# ---- jalons & fonctionnalités ----
w("\n\n---\n\n## 16.11 — Jalons\n")
for j in JAL:
    w("\n### %s — %s *(%s)*\n" % (j["id"], j["titre"], j.get("etat", "")))
    if j.get("note"): w("> %s\n" % j["note"])
    w("\n".join("- %s" % c for c in j.get("contenu", [])) + "\n")

w("\n---\n\n## 16.12 — Fonctionnalités\n")
w("La même liste que la page « Fonctionnalités » du POC — c'est la même source.\n")
doms = []
for f in FEA:
    if f["domaine"] not in doms: doms.append(f["domaine"])
for dom in doms:
    w("\n### %s\n" % dom)
    w(table([("#", g("id")), ("Fonctionnalité", g("libelle")), ("Jalon", lambda f: "V%s" % f["jalon"] if f.get("jalon") else "—"),
             ("État", g("etat")), ("Décisions", lambda f: refs(f.get("decisions"))), ("Questions", lambda f: refs(f.get("questions")))],
            [f for f in FEA if f["domaine"] == dom]))

io.open(SORTIE, "w", encoding="utf-8").write("\n".join(md) + "\n")
print("%s : %d entités, %d champs, %d relations, %d actions, %d routes, %d fonctionnalités"
      % (os.path.relpath(SORTIE), len(E), sum(len(v) for v in CH.values()), len(REL), len(ACT), len(ROU), len(FEA)))
