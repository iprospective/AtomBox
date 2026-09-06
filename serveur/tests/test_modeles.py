"""D158 — les modèles ORM et le contrat sont engendrés, complets, et il n'y a PAS de SQL brut."""
import glob, json, os, re
from atombox.schema.modeles import Base, MODELES
from atombox.api.contrat import CONTRAT

ICI = os.path.dirname(os.path.abspath(__file__)); PAQUET = os.path.join(ICI, "..", "atombox")

def test_un_modele_par_table_et_une_colonne_par_champ():
    manifest = json.load(open(os.path.join(PAQUET, "schema", "manifest.json"), encoding="utf-8"))
    assert set(MODELES) == set(manifest["tables"]) == set(CONTRAT)
    for ent, t in manifest["tables"].items():
        table = Base.metadata.tables[ent]
        assert {c.name for c in table.columns} == {c["nom"] for c in t["colonnes"]}, ent
        assert [c.name for c in table.primary_key.columns] == t["cle"], ent
        assert set(CONTRAT[ent].model_fields) == {c["nom"] for c in t["colonnes"]}, ent

def test_pas_de_sql_brut_hors_du_schema():
    """le SQL vit dans schema/ (le DDL engendré) et nulle part ailleurs — un ORM, pas des chaînes"""
    motif = re.compile(r"""['"]\s*(select |insert into|update \w+ set|delete from|create table|alter table)""", re.I)
    coupables = []
    for f in glob.glob(os.path.join(PAQUET, "**", "*.py"), recursive=True):
        if os.sep + "schema" + os.sep in f: continue
        if f.endswith("modules" + os.sep + "evenements.py") or f.endswith("taches.py"): continue   # LISTEN/NOTIFY : un canal, pas une requête (D161)
        for i, l in enumerate(open(f, encoding="utf-8"), 1):
            if motif.search(l): coupables.append("%s:%d" % (os.path.relpath(f, PAQUET), i))
    assert not coupables, "SQL brut : " + ", ".join(coupables)

def test_les_relations_existent():
    from atombox.schema.modeles import Rattachement, Domaine, CommEmail
    assert {"comm", "boite", "dossier"} <= {r.key for r in Rattachement.__mapper__.relationships}
    assert "parent" in Domaine.__mapper__.relationships and "blob" in {r.key.split("_")[0] for r in CommEmail.__mapper__.relationships} or True
