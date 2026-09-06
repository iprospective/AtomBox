#!/usr/bin/env python3
"""Génère src/poc/cdc-index.js depuis le CDC réel.

Le POC affiche le registre des décisions ; le retaper à la main garantirait
qu'il diverge. Ce script lit les tableaux de synthèse des fichiers 90 et 99 du
CDC et en produit un module JS. À relancer après chaque décision consignée :

    python3 outils/gen-cdc-index.py          (depuis la racine du dépôt — écrit webmail/src/poc/cdc-index.js)
"""
import io, os, re, sys, json, datetime

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
DEPOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SORTIE = os.path.join(DEPOT, "webmail", "src", "poc", "cdc-index.js")

def propre(t):
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)       # liens markdown
    t = t.replace("~~", "").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", t).strip()

def etat(cel):
    c = propre(cel)
    if "amendée" in c or "amendee" in c: return "amendee"
    if c.startswith("✅"): return "valide"
    if c.startswith("🟡"): return "propose"
    if c.startswith("❌"): return "amendee"
    return "autre"

def urgence(cel):
    c = propre(cel).lower()
    if "tranchée" in c or "répondue" in c: return "tranchee"
    if "haute" in c: return "haute"
    if "moyenne" in c: return "moyenne"
    if "basse" in c: return "basse"
    return "autre"

def lignes(fichier, motif):
    src = io.open(os.path.join(CDC, fichier), encoding="utf-8").read()
    out = []
    for ligne in src.split("\n"):
        if not ligne.startswith("|"): continue
        cel = [c.strip() for c in ligne.strip("|").split("|")]
        if not cel or not re.match(motif, propre(cel[0])): continue
        out.append(cel)
    return out

decisions = []
for cel in lignes("cdc-rm2881-90-decisions.md", r"^D\d+"):
    decisions.append({ "id": propre(cel[0]), "objet": propre(cel[1]),
                       "etat": etat(cel[2]) if len(cel) > 2 else "autre" })

# les CONSEILS (C) font partie du registre : le dictionnaire les cite (conseils: [C05])
conseils = []
for cel in lignes("cdc-rm2881-90-decisions.md", r"^C\d+"):
    conseils.append({ "id": propre(cel[0]), "objet": propre(cel[1]),
                      "etat": propre(cel[3]) if len(cel) > 3 else "" })

# contrôle : une décision rédigée en section mais absente de la vue d'ensemble est
# invisible du POC, du dictionnaire et de tout ce qui lit l'index — on le dit.
_src = io.open(os.path.join(CDC, "cdc-rm2881-90-decisions.md"), encoding="utf-8").read()
_sections = set(re.findall(r"^#{2,3} (D\d+b?) ", _src, re.M))
_table = set(d["id"] for d in decisions)
for _d in sorted(_sections - _table):
    print("⚠ %s est rédigée en section mais ABSENTE de la vue d'ensemble — invisible de l'index" % _d, file=sys.stderr)

questions = []
for cel in lignes("cdc-rm2881-99-questions-ouvertes.md", r"^Q\d+"):
    questions.append({ "id": propre(cel[0]), "objet": propre(cel[1]),
                       "bloque": propre(cel[2]) if len(cel) > 2 else "",
                       "urgence": urgence(cel[3]) if len(cel) > 3 else "autre" })

chapitres = []
for f in sorted(os.listdir(CDC)):
    m = re.match(r"cdc-rm2881-(\d+)-(.+)\.md$", f)
    if not m: continue
    titre = io.open(os.path.join(CDC, f), encoding="utf-8").readline()
    chapitres.append({ "n": m.group(1), "fichier": f,
                       "titre": propre(titre.lstrip("# ")).split(" — ")[0] })

# ---- le dictionnaire des données (docs/dict/*.yml) : la même source que le chapitre 16 ----
import yaml
DICT = os.path.join(CDC, "dict")
def yml(nom):
    return yaml.safe_load(io.open(os.path.join(DICT, nom + ".yml"), encoding="utf-8"))
dico = { k: yml(k) for k in ("entites", "champs", "relations", "enumerations", "workflows",
                              "actions", "templates", "composants", "protocoles", "normes",
                              "routes", "fonctionnalites", "jalons") }

# ---- le PLAN du sommaire : objet et avancement par chapitre, tels que docs/ les tient ----
plan = {}
for cel in lignes("cdc-rm2881-00-sommaire.md", r"^\d{2}$"):
    if len(cel) >= 4:
        plan[propre(cel[0])] = { "objet": propre(cel[2]), "avancement": propre(cel[3]) }

# ---- le VRAC : chaque note du demandeur, tracée jusqu'à sa résolution ----
vrac = []
for cel in lignes("cdc-rm2881-91-vrac.md", r"^N\d+"):
    vrac.append({ "id": propre(cel[0]), "verbatim": propre(cel[1]),
                  "etat": propre(cel[2]) if len(cel) > 2 else "",
                  "traite_par": propre(cel[3]) if len(cel) > 3 else "" })

# ---- le MODÈLE de CDC (docs/modele-cdc/) : les gabarits, pour les lire dans la maquette ----
modele = {}
_md = os.path.join(CDC, "modele-cdc")
if os.path.isdir(_md):
    for f in sorted(os.listdir(_md)):
        if f.endswith(".md"):
            modele[f] = io.open(os.path.join(_md, f), encoding="utf-8").read()
    _mdd = os.path.join(_md, "dict")
    if os.path.isdir(_mdd):
        for f in sorted(os.listdir(_mdd)):
            modele["dict/" + f] = io.open(os.path.join(_mdd, f), encoding="utf-8").read()

# ---- le TEXTE complet : chaque chapitre, et chaque décision/question/conseil découpé ----
# La maquette montre tout le CDC, pas seulement les tableaux de synthèse. C'est lourd
# (~650 Ko de markdown) mais c'est du texte, et c'est ce qui rend la page « CDC » vraie.
textes = {}
for ch in chapitres:
    textes[ch["n"]] = io.open(os.path.join(CDC, ch["fichier"]), encoding="utf-8").read()
sections = {}
_titre = re.compile(r"^#{2,3} ~{0,2}([DQC]\d+b?)~{0,2}\b")
for fichier in ("cdc-rm2881-90-decisions.md", "cdc-rm2881-99-questions-ouvertes.md"):
    src = io.open(os.path.join(CDC, fichier), encoding="utf-8").read().split("\n")
    cur, buf = None, []
    def flush():
        if cur and buf: sections.setdefault(cur, "\n".join(buf).strip())
    for ligne in src:
        m = _titre.match(ligne)
        if m:
            flush(); cur, buf = m.group(1), [ligne]
        elif cur:
            if re.match(r"^## ", ligne) and not _titre.match(ligne):   # fin de la zone des sections
                flush(); cur, buf = None, []
            else: buf.append(ligne)
    flush()

js = """/* INDEX DU CDC — FICHIER GÉNÉRÉ, ne pas éditer à la main.
   Produit par outils/gen-cdc-index.py depuis le CDC réel (RM2881). Le retaper
   garantirait qu'il diverge ; le générer garantit que la page « CDC » du POC dit
   ce que dit le registre, et rien d'autre.

   Généré le %s — %d décisions, %d questions, %d chapitres. */
(function (ABX) {
  "use strict";
  ABX.CDC = %s;
})(window.ABX = window.ABX || {});
""" % (datetime.date.today().isoformat(), len(decisions), len(questions), len(chapitres),
       json.dumps({ "genere": datetime.date.today().isoformat(), "ticket": "RM2881",
                    "depot": "iprospective/tools/atombox-webmail-core",
                    "chapitres": chapitres, "decisions": decisions, "questions": questions,
                    "conseils": conseils, "dict": dico,
                    "textes": textes, "sections": sections,
                    "plan": plan, "vrac": vrac, "modele": modele },
                  ensure_ascii=False, indent=2))

io.open(os.path.abspath(SORTIE), "w", encoding="utf-8").write(js)
print("%s : %d décisions, %d questions, %d chapitres, %d fonctionnalités, %d entités, %d sections, %d notes de vrac, %d fichiers du modèle, %d Ko"
      % (os.path.relpath(SORTIE), len(decisions), len(questions), len(chapitres),
         len(dico["fonctionnalites"]), len(dico["entites"]), len(sections), len(vrac), len(modele), len(js) // 1024))
