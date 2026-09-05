# AtomBox — le serveur

Python 3.12, `asyncio`, PostgreSQL ≥ 14 (**D154**). Découpé par fonctionnalité de V0 (**D156**) :

| Dossier | F… | Rôle |
|---|---|---|
| `atombox/schema/` | F114 | le schéma **engendré** depuis le dictionnaire (`outils/gen-schema.py`) et ses migrations (Alembic) |
| `atombox/magasin/` | F002 | le magasin d'octets `ab/cd/<id>`, zstd (D145) |
| `atombox/ingestion/` | F001, F113 | le démon IMAP : IDLE, PEEK, reprise par UID ; synchronisation des états |
| `atombox/filtres/` | F016 | le moteur de filtres |
| `atombox/api/` | — | l'API REST, une route par ligne de `routes.yml` |
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
