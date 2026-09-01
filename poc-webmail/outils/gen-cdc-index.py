#!/usr/bin/env python3
"""Génère js/services/cdc-index.js depuis le CDC réel.

Le POC affiche le registre des décisions ; le retaper à la main garantirait
qu'il diverge. Ce script lit les tableaux de synthèse des fichiers 90 et 99 du
CDC et en produit un module JS. À relancer après chaque décision consignée :

    python3 outils/gen-cdc-index.py
"""
import io, os, re, sys, json, datetime

CDC = os.environ.get("CDC_DIR",
    "/zfs/workspaces/iprospective/dev/atombox-webmail/.mmi-pm/docs")
SORTIE = os.path.join(os.path.dirname(__file__), "..", "js", "services", "cdc-index.js")

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
                    "chapitres": chapitres, "decisions": decisions, "questions": questions },
                  ensure_ascii=False, indent=2))

io.open(os.path.abspath(SORTIE), "w", encoding="utf-8").write(js)
print("%s : %d décisions, %d questions, %d chapitres"
      % (os.path.relpath(SORTIE), len(decisions), len(questions), len(chapitres)))
