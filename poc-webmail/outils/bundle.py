#!/usr/bin/env python3
"""Produit une page autonome à partir des sources.

Le POC est multi-fichiers pour être maintenable ; il doit aussi pouvoir être
déposé quelque part en un seul fichier, ou ouvert sans serveur. Ce script lit
index.html, inline la feuille de style et concatène les scripts DANS L'ORDRE
QU'IL DÉCLARE — le même ordre que le harnais de test.

    python3 outils/bundle.py [destination.html]
"""
import io, os, re, sys, datetime

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SORTIE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RACINE, "dist", "index.html")

html = io.open(os.path.join(RACINE, "index.html"), encoding="utf-8").read()

# 1. la feuille de style
css = io.open(os.path.join(RACINE, "css", "app.css"), encoding="utf-8").read()
html = html.replace('<link rel="stylesheet" href="css/app.css">',
                    "<style>\n" + css + "\n</style>")

# 2. les scripts, dans l'ordre déclaré
fichiers = re.findall(r'<script src="([^"]+)"></script>', html)
if not fichiers:
    sys.exit("aucun script trouvé dans index.html")
morceaux = []
for f in fichiers:
    src = io.open(os.path.join(RACINE, f), encoding="utf-8").read()
    morceaux.append("/* ===== " + f + " ===== */\n" + src)
bloc = "<script>\n" + "\n".join(morceaux) + "\n</script>"

premier = '<script src="%s"></script>' % fichiers[0]
html = html.replace(premier, bloc, 1)
for f in fichiers[1:]:
    html = html.replace('<script src="%s"></script>\n' % f, "")
    html = html.replace('<script src="%s"></script>' % f, "")

# 3. commentaires d'inclusion devenus inutiles
html = re.sub(r"\n<!--[^>]*?-->\n(?=\s*(<script>|</body>))", "\n", html, flags=re.S)
html = re.sub(r"\n{3,}", "\n\n", html)

marque = ("<!-- Page autonome engendrée par outils/bundle.py le %s.\n"
          "     NE PAS ÉDITER : les sources sont dans js/ et css/. -->\n"
          % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
html = html.replace("<!doctype html>", "<!doctype html>\n" + marque, 1)

os.makedirs(os.path.dirname(os.path.abspath(SORTIE)), exist_ok=True)
io.open(SORTIE, "w", encoding="utf-8").write(html)
print("%s : %d fichiers, %.0f Ko" % (os.path.relpath(SORTIE, RACINE),
                                     len(fichiers) + 1, len(html.encode()) / 1024))
