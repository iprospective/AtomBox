#!/usr/bin/env python3
"""Produit une page autonome à partir des sources.

L'interface est multi-fichiers pour être maintenable ; elle doit aussi pouvoir
être déposée quelque part en un seul fichier, ou ouverte sans serveur. Ce script
lit index.html, inline la feuille de style et concatène les scripts DANS L'ORDRE
QU'IL DÉCLARE — le même ordre que le harnais de test.

Il n'y a qu'un index (D157) : le POC est une session, et ses fichiers sont écrits
par le chargeur en trois points. Deux bundles en découlent :

    python3 outils/bundle.py                       → dist/index.html : la page AUTONOME, tout
                                                     inline, POC compris (ABX_INLINE) ; poc/poc y marche hors ligne
    python3 outils/bundle.py dist/prod.html prod   → le PRODUIT seul : rien du POC (ABX_SANS_POC)
"""
import io, os, re, sys, datetime

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SORTIE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "dist", "index.html")
MODE = sys.argv[2] if len(sys.argv) > 2 else "poc"      # poc | prod

html = io.open(os.path.join(RACINE, "index.html"), encoding="utf-8").read()

# 1. la feuille de style
css = io.open(os.path.join(RACINE, "css", "app.css"), encoding="utf-8").read()
html = html.replace('<link rel="stylesheet" href="css/app.css">', "<style>\n" + css + "\n</style>")

# 2. les scripts, dans l'ordre déclaré — et, en mode poc, les listes du chargeur à leurs points
declares = re.findall(r'<script src="([^"]+)"></script>', html)
if not declares:
    sys.exit("aucun script trouvé dans index.html")

def liste_du_chargeur(nom):
    src = io.open(os.path.join(RACINE, "src", "noyau", "chargeur.js"), encoding="utf-8").read()
    m = re.search(r"const %s\s*=\s*\[(.*?)\];" % nom, src, re.S)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []

POINTS = { "src/noyau/chargeur.js": "TETE", "src/noyau/chargeur.donnees.js": "DONNEES", "src/noyau/chargeur.fin.js": "FIN" }
fichiers = []
for f in declares:
    fichiers.append(f)
    if MODE == "poc" and f in POINTS:
        fichiers.extend(liste_du_chargeur(POINTS[f]))

morceaux = ["window.ABX_INLINE = true;" if MODE == "poc" else "window.ABX_SANS_POC = true;"]
for f in fichiers:
    src = io.open(os.path.join(RACINE, f), encoding="utf-8").read()
    # Le CDC embarqué peut citer « </script> » : dans un script inline, le
    # navigateur fermerait la balise là. « <\/script » est identique en JS et en
    # JSON, et inoffensif pour le HTML.
    src = src.replace("</script", "<\\/script")
    morceaux.append("/* ===== " + f + " ===== */\n" + src)
bloc = "<script>\n" + "\n".join(morceaux) + "\n</script>"

premier = '<script src="%s"></script>' % declares[0]
html = html.replace(premier, bloc, 1)
for f in declares[1:]:
    html = re.sub(r'<script src="%s"></script>[^\n]*\n?' % re.escape(f), "", html, count=1)

# 3. commentaires d'inclusion devenus inutiles
html = re.sub(r"\n<!--[^>]*?-->\n(?=\s*(<script>|</body>))", "\n", html, flags=re.S)
html = re.sub(r"\n{3,}", "\n\n", html)

marque = ("<!-- Page %s engendrée par outils/bundle.py le %s.\n"
          "     NE PAS ÉDITER : les sources sont dans src/ (scss compris) et css/ est compilé. -->\n"
          % ("autonome" if MODE == "poc" else "produit", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
html = html.replace("<!doctype html>", "<!doctype html>\n" + marque, 1)

os.makedirs(os.path.dirname(os.path.abspath(SORTIE)), exist_ok=True)
io.open(SORTIE, "w", encoding="utf-8").write(html)
print("%s : %d fichiers, %.0f Ko" % (os.path.relpath(SORTIE, RACINE), len(fichiers) + 1, len(html.encode()) / 1024))
