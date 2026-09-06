#!/usr/bin/env python3
"""Engendre les MODÈLES ORM (SQLAlchemy 2) et les SCHÉMAS du contrat (Pydantic) depuis le
dictionnaire des données (D158 : pas de SQL brut, un ORM ; une seule source, trois dérivés —
le DDL de gen-schema.py, les modèles, le contrat).

    python3 outils/gen-modeles.py        (depuis la racine du dépôt)

Écrit :
  serveur/atombox/schema/modeles.py     une classe par entité, une colonne par champ, une relation
                                        par référence à cible connue — NE PAS ÉDITER
  serveur/atombox/api/contrat.py        un schéma Pydantic par entité (les noms de champs.yml sont
                                        ceux du contrat JSON que le webmail lit — D141)
"""
import io, os, re, sys, datetime, yaml

def trouver_cdc():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs")
        if os.path.isdir(c): return c
        d = os.path.dirname(d)
    sys.exit("gen-modeles : aucun .mmi-pm/docs au-dessus de " + __file__)

CDC = os.environ.get("CDC_DIR") or trouver_cdc(); DICT = os.path.join(CDC, "dict")
DEPOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
def lire(n): return yaml.safe_load(io.open(os.path.join(DICT, n + ".yml"), encoding="utf-8"))
E = lire("entites"); CH = lire("champs"); EN = lire("enumerations"); ENT = {e["id"]: e for e in E}

SA = { "id": ("Uuid", "uuid.UUID"), "ref": ("Uuid", "uuid.UUID"), "court": ("Text", "str"), "long": ("Text", "str"),
       "enum": ("Text", "str"), "empreinte": ("Text", "str"), "jeton": ("Text", "str"), "horodatage": ("DateTime(timezone=True)", "datetime.datetime"),
       "date": ("Date", "datetime.date"), "bool": ("Boolean", "bool"), "entier": ("BigInteger", "int"), "decimal": ("Numeric", "decimal.Decimal"),
       "json": ("JSONB", "dict | list"), "binaire": ("LargeBinary", "bytes") }
PY = { "id": "uuid.UUID", "ref": "uuid.UUID", "court": "str", "long": "str", "enum": "str", "empreinte": "str", "jeton": "str",
       "horodatage": "datetime.datetime", "date": "datetime.date", "bool": "bool", "entier": "int", "decimal": "decimal.Decimal",
       "json": "dict | list", "binaire": "bytes" }

def classe(ent): return "".join(p.capitalize() for p in ent.split("_"))
def cle_de(ent):
    ids = [c["nom"] for c in CH.get(ent, []) if c["type"] == "id"]
    return ids or list(ENT[ent].get("cle") or [])
def cible_de(ent, c):
    if "vers" in c: return c["vers"]
    m = re.fullmatch(r"(\w+)_id", c["nom"])
    if m and m.group(1) in ENT and m.group(1) != ent: return m.group(1)
    return None

M = ['"""MODÈLES ORM — engendrés par outils/gen-modeles.py le %s depuis le dictionnaire (D158).' % datetime.datetime.now().isoformat(timespec="seconds"),
     'NE PAS ÉDITER : corriger .mmi-pm/docs/dict/*.yml, régénérer. Les tables sont celles de schema.sql (F114)."""',
     "from __future__ import annotations", "import datetime, decimal, uuid",
     "from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, LargeBinary, Numeric, PrimaryKeyConstraint, Text, UniqueConstraint, Uuid",
     "from sqlalchemy.dialects.postgresql import JSONB",
     "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship", "",
     "class Base(DeclarativeBase):", "    pass", ""]
C = ['"""CONTRAT — schémas Pydantic engendrés par outils/gen-modeles.py depuis le dictionnaire (D141, D158).',
     'Les noms sont ceux de champs.yml : ce que le webmail lit. NE PAS ÉDITER."""',
     "from __future__ import annotations", "import datetime, decimal, uuid", "from pydantic import BaseModel, ConfigDict", ""]
for e in E:
    ent = e["id"]; champs = CH.get(ent) or []
    if not champs: continue
    cle = cle_de(ent); noms = {c["nom"] for c in champs}
    M.append("class %s(Base):" % classe(ent))
    M.append('    """%s"""' % (e.get("role") or "").strip().split("\n")[0][:120].replace('"', "'"))
    M.append('    __tablename__ = "%s"' % ent)
    args = ["PrimaryKeyConstraint(%s, name=%s)" % (", ".join('"%s"' % k for k in cle), '"pk_%s"' % ent)]
    rels = []
    for c in champs:
        satype, pytype = SA[c["type"]]
        obligatoire = c.get("obligatoire") == "oui" or c["nom"] in cle
        col = "mapped_column(%s" % satype
        cible = cible_de(ent, c) if c["type"] in ("ref", "empreinte") else None
        if cible and cible in ENT and CH.get(cible) and len(cle_de(cible)) == 1:
            col += ', ForeignKey("%s.%s", name="fk_%s_%s")' % (cible, cle_de(cible)[0], ent, c["nom"])
            stem = c["nom"][:-3] if c["nom"].endswith("_id") else c["nom"]
            if stem not in noms and stem not in ("type",):
                rels.append((stem, classe(cible), c["nom"], cible == ent))
        col += ", nullable=%s)" % (not obligatoire)
        ann = pytype if obligatoire else pytype + " | None"
        M.append("    %s: Mapped[%s] = %s" % (c["nom"], ann, col))
        if c["type"] == "enum" and c.get("enum") in EN:
            vals = ", ".join("'%s'" % v["id"] for v in EN[c["enum"]]["valeurs"])
            args.append('CheckConstraint("\\"%s\\" IN (%s)", name="ck_%s_%s")' % (c["nom"], vals, ent, c["nom"]))
        if c.get("unique") == "oui": args.append('UniqueConstraint("%s", name="uq_%s_%s")' % (c["nom"], ent, c["nom"]))
        if c.get("unique_avec"): args.append('UniqueConstraint("%s", "%s", name="uq_%s_%s_%s")' % (c["unique_avec"], c["nom"], ent, c["unique_avec"], c["nom"]))
    for stem, cl, col, soi in rels:
        extra = ", remote_side=[%s]" % cle_de(ent)[0] if soi else ""
        M.append("    %s: Mapped[%s | None] = relationship(%s, foreign_keys=[%s]%s)" % (stem, cl, '"%s"' % cl, col, extra))
    M.append("    __table_args__ = (%s,)" % ", ".join(args))
    M.append("")
    C.append("class %s(BaseModel):" % classe(ent))
    C.append("    model_config = ConfigDict(from_attributes=True)")
    for c in champs:
        obligatoire = c.get("obligatoire") == "oui" or c["nom"] in cle
        C.append("    %s: %s%s" % (c["nom"], PY[c["type"]], "" if obligatoire else " | None = None"))
    C.append("")
M.append("MODELES = {%s}" % ", ".join('"%s": %s' % (e["id"], classe(e["id"])) for e in E if CH.get(e["id"])))
C.append("CONTRAT = {%s}" % ", ".join('"%s": %s' % (e["id"], classe(e["id"])) for e in E if CH.get(e["id"])))
os.makedirs(os.path.join(DEPOT, "serveur", "atombox", "api"), exist_ok=True)
io.open(os.path.join(DEPOT, "serveur", "atombox", "schema", "modeles.py"), "w", encoding="utf-8").write("\n".join(M) + "\n")
io.open(os.path.join(DEPOT, "serveur", "atombox", "api", "contrat.py"), "w", encoding="utf-8").write("\n".join(C) + "\n")
n = sum(1 for e in E if CH.get(e["id"]))
print("serveur/atombox/schema/modeles.py et api/contrat.py : %d modèles, %d colonnes" % (n, sum(len(CH[e["id"]]) for e in E if CH.get(e["id"]))))
