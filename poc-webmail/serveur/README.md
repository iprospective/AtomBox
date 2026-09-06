# AtomBox — le serveur

Python 3.12, `asyncio`, PostgreSQL ≥ 14 (**D154**). Découpé par fonctionnalité de V0 (**D156**) :

| Dossier | F… | Rôle |
|---|---|---|
| `atombox/schema/` | F114 | le schéma **engendré** depuis le dictionnaire (`outils/gen-schema.py`) et ses migrations (Alembic) |
| `atombox/magasin/` | F002 | le magasin d'octets `ab/cd/<id>`, zstd (D145) |
| `atombox/ingestion/` | F001, F113 | le démon IMAP : IDLE, PEEK, reprise par UID ; synchronisation des états |
| `atombox/filtres/` | F016 | le moteur de filtres |
| `atombox/api/` | — | le routage (routes = contrôleurs + actions), la sécurité, l'application FastAPI, le contrat Pydantic engendré |
| `atombox/controleurs/` | F124… | une classe par ressource, une méthode `@action(méthode, chemin)` par route de `routes.yml` — le contrat est vérifié au démarrage |
| `atombox/etat/` | F122 | la page d'état et les métriques |

```
cd serveur
uv venv && uv pip install -e ".[dev]"
python3 ../outils/gen-schema.py          # régénère atombox/schema/schema.sql depuis le dictionnaire
.venv/bin/pytest -q                       # sans base : la syntaxe et la fidélité au dictionnaire ;
                                          # avec DATABASE_URL : le schéma s'applique dans une base jetable
DATABASE_URL=postgresql://…/atombox .venv/bin/alembic upgrade head
```

Le schéma n'est **jamais** édité à la main : on corrige le dictionnaire, on régénère, on migre.

## La base, l'ORM et les migrations (D158)

- **ORM** : SQLAlchemy 2 sur `psycopg` 3 — les modèles sont **engendrés** du dictionnaire
  (`outils/gen-modeles.py` → `atombox/schema/modeles.py`), comme le DDL ; **aucune chaîne SQL**
  hors de `schema/` (un test le refuse) ; synchrone pour le démon, asynchrone pour l'API ;
- **migrations** : **Alembic**, la file est `atombox/schema/migrations/versions/` — `0001` applique
  la copie figée `0001_schema.sql`, chaque changement du dictionnaire ajoute une révision
  (`0002_reprise_par_uid.py`…) qui mène au `schema.sql` courant ; `tests/test_migrations.py`
  vérifie par lecture que la file couvre chaque colonne, et avec une base qu'elle s'applique ;
- **identifiants** : UUID v7 engendrés par l'application (`atombox/uuid7.py`, D145).

## Tout est module (D160)

`atombox/modules/` : un module est une classe (`Module`) qui déclare ses contrôleurs, ses
accroches (`@accroche("message.ingere")` sur des points nommés dans `accroches.py`), son
domaine de journal, ses migrations. Les internes (`session`, `etat`, `ingestion`) sont écrits
ainsi. Un module tiers s'installe par `pip` (point d'entrée `atombox.modules`) ou
`ATOMBOX_MODULES=paquet:Classe` ; ses routes propres vivent sous `/api/v1/modules/<nom>/`.

## F001, F002 — l'ingestion et le magasin

`atombox/magasin/` : `ab/cd/<id>`, zstd conditionnel, jamais réécrit. `atombox/ingestion/` :
`analyse.py` (le MIME par `email`), `identite.py` (D064), `ingestion.py` (une transaction par
message, déduplication, rattachements, pièces, fil), `imap.py` (PEEK, reprise par UID, IDLE),
`demon.py` (une tâche par boîte). Tests sans base : analyse, identité, magasin, migrations ;
avec `DATABASE_URL` : ingestion complète dans une base jetable. La relève IMAP et le démon se
valident sur le pilote (D052), pas dans le harnais.
