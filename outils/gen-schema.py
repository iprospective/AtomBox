#!/usr/bin/env python3
"""Engendre le schéma PostgreSQL depuis le dictionnaire des données (F114, D154).

    python3 outils/gen-schema.py          (depuis la racine du dépôt)

Lit .mmi-pm/docs/dict/{entites,champs,relations,enumerations}.yml et écrit :
  serveur/atombox/schema/schema.sql      le DDL, une table par entité, TOUTES (F114 : les
                                         tables de la V1 existent, vides), clés, références,
                                         unicités, index des clés étrangères ;
  serveur/atombox/schema/manifest.json   ce que le DDL contient, pour les tests.

Le dictionnaire est la source : rien n'est écrit ici qui n'y soit — un champ `ref` sans
cible connue est rapporté, pas deviné. Les types sont LOGIQUES dans le dictionnaire ;
la correspondance vers PostgreSQL 16 est la table TYPES ci-dessous (D154, D145 : uuid).
"""
import io, os, re, sys, json, datetime, yaml

def trouver_cdc():
    d = os.path.dirname(os.path.abspath(__file__))
    while d != os.path.dirname(d):
        c = os.path.join(d, ".mmi-pm", "docs")
        if os.path.isdir(c): return c
        d = os.path.dirname(d)
    sys.exit("gen-schema : aucun .mmi-pm/docs au-dessus de " + __file__ + " — passer CDC_DIR")

CDC = os.environ.get("CDC_DIR") or trouver_cdc()
DICT = os.path.join(CDC, "dict")
DEPOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SORTIE = os.path.join(DEPOT, "serveur", "atombox", "schema")

def lire(nom): return yaml.safe_load(io.open(os.path.join(DICT, nom + ".yml"), encoding="utf-8"))
E = lire("entites"); CH = lire("champs"); REL = lire("relations"); EN = lire("enumerations")
ENT = {e["id"]: e for e in E}

# types logiques → PostgreSQL. L'empreinte est un hexadécimal (nomme les fichiers ab/cd/…, D145).
TYPES = { "id": "uuid", "ref": "uuid", "court": "text", "long": "text", "horodatage": "timestamptz",
          "date": "date", "enum": "text", "bool": "boolean", "entier": "bigint", "decimal": "numeric",
          "empreinte": "text", "jeton": "text", "json": "jsonb", "binaire": "bytea" }

def cle_de(ent):
    ids = [c["nom"] for c in CH.get(ent, []) if c["type"] == "id"]
    if ids: return ids
    if ENT[ent].get("cle"): return list(ENT[ent]["cle"])
    return None

def cible_de(ent, c):
    """l'entité visée par une référence : `vers` explicite, sinon <entité>_id, sinon inconnue"""
    if "vers" in c: return c["vers"]           # None = polymorphe, volontaire
    m = re.fullmatch(r"(\w+)_id", c["nom"])
    if m and m.group(1) in ENT and m.group(1) != ent: return m.group(1)
    if m and m.group(1) == ent: return None     # comm_id dans comm : la clé, pas une référence
    return "?"

def sql_type(c):
    t = TYPES.get(c["type"])
    if not t: raise SystemExit("type logique inconnu : %s.%s : %s" % ("?", c["nom"], c["type"]))
    return t

def q(s): return '"%s"' % s

rapport = []
tables, fks, index, contraintes = [], [], [], []
manifest = {"genere": datetime.datetime.now().isoformat(timespec="seconds"), "tables": {}}

for e in E:
    ent = e["id"]; champs = CH.get(ent)
    if not champs: rapport.append("SANS CHAMPS : %s — pas de table" % ent); continue
    cle = cle_de(ent)
    if not cle: rapport.append("SANS CLÉ : %s — ajouter `cle:` dans entites.yml" % ent); continue
    cols, checks, mcols = [], [], []
    for c in champs:
        ligne = "  %s %s" % (q(c["nom"]), sql_type(c))
        if c.get("obligatoire") == "oui" or c["nom"] in cle: ligne += " NOT NULL"
        if c["type"] == "enum" and c.get("enum") in EN:
            vals = [v["id"] for v in EN[c["enum"]]["valeurs"]]
            checks.append("  CONSTRAINT %s CHECK (%s IN (%s))" % (q("ck_%s_%s" % (ent, c["nom"])), q(c["nom"]), ", ".join("'%s'" % v for v in vals)))
        elif c["type"] == "enum":
            rapport.append("ENUM SANS LISTE : %s.%s — text libre" % (ent, c["nom"]))
        if c.get("unique") == "oui": contraintes.append("ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s);" % (q(ent), q("uq_%s_%s" % (ent, c["nom"])), q(c["nom"])))
        if c.get("unique_avec"): contraintes.append("ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s, %s);" % (q(ent), q("uq_%s_%s_%s" % (ent, c["unique_avec"], c["nom"])), q(c["unique_avec"]), q(c["nom"])))
        if c["type"] in ("ref", "empreinte") and c["nom"] not in cle or (c["type"] == "ref" and c["nom"] in cle and len(cle) > 1) or (c["type"] == "ref" and c["nom"] in cle and cible_de(ent, c) not in (None, "?")):
            cible = cible_de(ent, c)
            if cible == "?": rapport.append("RÉFÉRENCE SANS CIBLE : %s.%s — ajouter `vers:`" % (ent, c["nom"]))
            elif cible and cible in ENT and CH.get(cible):
                ccle = cle_de(cible)
                if ccle and len(ccle) == 1:
                    nom = "fk_%s_%s" % (ent, c["nom"])
                    fks.append("ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) REFERENCES %s (%s) DEFERRABLE INITIALLY IMMEDIATE;" % (q(ent), q(nom), q(c["nom"]), q(cible), q(ccle[0])))
                    if c["nom"] not in cle or cle.index(c["nom"]) > 0:
                        index.append("CREATE INDEX %s ON %s (%s);" % (q("ix_%s_%s" % (ent, c["nom"])), q(ent), q(c["nom"])))
                else: rapport.append("CIBLE À CLÉ COMPOSITE : %s.%s → %s" % (ent, c["nom"], cible))
            elif cible and cible not in ENT: rapport.append("CIBLE INCONNUE : %s.%s → %s" % (ent, c["nom"], cible))
        cols.append(ligne); mcols.append({"nom": c["nom"], "type": sql_type(c), "obligatoire": c.get("obligatoire") == "oui" or c["nom"] in cle})
    cols.append("  CONSTRAINT %s PRIMARY KEY (%s)" % (q("pk_" + ent), ", ".join(q(k) for k in cle)))
    tables.append("-- %s — %s\nCREATE TABLE %s (\n%s\n);" % (ent, (e.get("role") or "").strip().split("\n")[0][:110].replace("--", "—"), q(ent), ",\n".join(cols + checks)))
    manifest["tables"][ent] = {"cle": cle, "colonnes": mcols, "decisions": e.get("decisions") or []}

# les relations du dictionnaire : chacune doit être portée par une clé étrangère, ou dite polymorphe
portees = set()
for f in fks:
    m = re.search(r'ALTER TABLE "(\w+)".*REFERENCES "(\w+)"', f); portees.add((m.group(1), m.group(2)))
for r in REL:
    if r.get("polymorphe") == "oui": continue   # portée par (type, id) : pas de clé étrangère, c'est dit
    de, vers, card = r["de"], r["vers"], r["cardinalite"]
    porteur, cible = (de, vers) if card.startswith("n-") else (vers, de)   # 1-n : la clé est côté n
    if card == "1-0..1": porteur, cible = vers, de
    if (porteur, cible) not in portees and (cible, porteur) not in portees:
        rapport.append("RELATION SANS CLÉ ÉTRANGÈRE : %s → %s (%s) — champ porteur absent ou polymorphe" % (de, vers, card))

manifest["fks"] = len(fks); manifest["index"] = len(index); manifest["contraintes"] = len(contraintes); manifest["rapport"] = rapport
entete = ("-- SCHÉMA ATOMBOX — engendré par outils/gen-schema.py le %s depuis le dictionnaire des données.\n"
          "-- NE PAS ÉDITER : la source est .mmi-pm/docs/dict/*.yml (F114, D154). PostgreSQL ≥ 14 (D027).\n"
          "-- %d tables, %d clés étrangères, %d index, %d unicités. Identifiants : uuid v7 engendrés par\n"
          "-- l'application (D145). Le tronc comm n'est PAS partitionné en V0 : la partition par canal (D138)\n"
          "-- se pose quand un second canal existe — l'uuid rend la clé indépendante de la partition.\n"
          % (manifest["genere"], len(tables), len(fks), len(index), len(contraintes)))
sql = entete + "\nBEGIN;\n\n" + "\n\n".join(tables) + "\n\n-- clés étrangères, après toutes les tables : l'ordre de création n'importe plus\n" + "\n".join(fks) + "\n\n-- unicités\n" + "\n".join(contraintes) + "\n\n-- index des références\n" + "\n".join(index) + "\n\nCOMMIT;\n"
os.makedirs(SORTIE, exist_ok=True)
io.open(os.path.join(SORTIE, "schema.sql"), "w", encoding="utf-8").write(sql)
io.open(os.path.join(SORTIE, "manifest.json"), "w", encoding="utf-8").write(json.dumps(manifest, ensure_ascii=False, indent=1))
print("serveur/atombox/schema/schema.sql : %d tables, %d clés étrangères, %d index, %d unicités" % (len(tables), len(fks), len(index), len(contraintes)))
for r in rapport: print("  ! " + r)
