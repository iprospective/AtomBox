"""La FILE des migrations mène au schéma courant : chaque colonne de manifest.json est dans la
copie figée 0001 ou ajoutée par une révision postérieure. Sans base, par lecture des fichiers."""
import os, re, json, glob

ICI = os.path.dirname(os.path.abspath(__file__))
VERS = os.path.join(ICI, "..", "atombox", "schema", "migrations", "versions")

def test_toutes_les_colonnes_sont_migrees():
    manifest = json.load(open(os.path.join(ICI, "..", "atombox", "schema", "manifest.json"), encoding="utf-8"))
    fige = open(os.path.join(VERS, "0001_schema.sql"), encoding="utf-8").read()
    ajouts = "\n".join(open(f, encoding="utf-8").read() for f in sorted(glob.glob(os.path.join(VERS, "0*.py"))))
    manquent = []
    for table, t in manifest["tables"].items():
        m = re.search(r'CREATE TABLE "%s" \((.*?)\n\);' % table, fige, re.S)
        colonnes_figees = set(re.findall(r'^\s*"(\w+)" ', m.group(1), re.M)) if m else set()
        for c in t["colonnes"]:
            if c["nom"] not in colonnes_figees and not re.search(r'ALTER TABLE "%s" ADD COLUMN "%s"' % (table, c["nom"]), ajouts) \
               and not re.search(r'ADD COLUMN "%s"[^;]*' % c["nom"], ajouts):
                manquent.append(table + "." + c["nom"])
    assert not manquent, "colonnes du schéma courant sans migration : " + ", ".join(manquent)

def test_les_revisions_se_suivent():
    revs = {}
    for f in sorted(glob.glob(os.path.join(VERS, "0*.py"))):
        s = open(f, encoding="utf-8").read()
        revs[re.search(r'^revision = "(\w+)"', s, re.M).group(1)] = re.search(r'^down_revision = (None|"(\w+)")', s, re.M).group(2)
    assert list(revs)[0] and revs[list(revs)[0]] is None
    for i, r in enumerate(list(revs)[1:], 1): assert revs[r] == list(revs)[i - 1], r
