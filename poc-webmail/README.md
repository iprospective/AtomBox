# AtomBox — le dépôt

Un seul dépôt pour le produit (**D156**) :

| Dossier | Contenu |
|---|---|
| `webmail/` | l'interface — d'abord le POC (mode simulé, CDC lisible : `index.html`), et déjà le webmail du produit (`index.prod.html`) — **D141** |
| `serveur/` | le serveur, en Python (**D154**) : schéma, magasin d'octets, démon d'ingestion, moteur de filtres, API, page d'état — découpé par fonctionnalité de V0 |
| `outils/` | ce qui sert aux deux : `gen-dict.py` (le chapitre 16 depuis `dict/*.yml`), `gen-cdc-index.py` (l'index du CDC lisible dans le webmail), `gen-schema.py` (le DDL PostgreSQL depuis le dictionnaire), et le vérificateur de contrat à venir |

Le cahier des charges et le dictionnaire des données **ne sont pas ici** : ils vivent dans le dépôt
PM (`.mmi-pm/docs`, ticket RM2881). Le code les lit, il ne les possède pas.

```
python3 outils/gen-dict.py            # régénère le chapitre 16 du CDC
python3 outils/gen-cdc-index.py       # régénère webmail/js/services/cdc-index.js
python3 outils/gen-schema.py          # régénère serveur/atombox/schema/schema.sql (F114) — rapport vide exigé
cd webmail && python3 outils/bundle.py && node test/smoke.js   # le POC (voir webmail/README.md)
bash webmail/outils/deploy.sh         # mise en ligne du webmail
```

Branches : `main` (protégée, un jalon à la fois), `dev` (intégration), une branche courte par
fonctionnalité — `v0/F114-schema`, `v0/F001-ingestion`… — fusionnée dans `dev` par MR.
