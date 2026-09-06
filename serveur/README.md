# AtomBox — le serveur

Python 3.12, `asyncio`, PostgreSQL ≥ 14 (**D154**). Découpé par fonctionnalité de V0 (**D156**) :

| Dossier | F… | Rôle |
|---|---|---|
| `atombox/schema/` | F114 | le schéma **engendré** depuis le dictionnaire (`outils/gen-schema.py`) et ses migrations (Alembic) |
| `atombox/magasin/` | F002 | le magasin d'octets `ab/cd/<id>`, zstd (D145) |
| `atombox/ingestion/` | F001, F113 | le démon IMAP : IDLE, PEEK, reprise par UID ; synchronisation des états |
| `atombox/filtres/` | F016 | le moteur de filtres |
| `atombox/api/` | — | le routage (routes = contrôleurs + actions), la sécurité, l'application FastAPI, le contrat Pydantic engendré |
| `atombox/controleurs/` | F124, F122, liste, message, fil, rattachement, création | une classe par ressource, une méthode `@action(méthode, chemin)` par route de `routes.yml` — le contrat est vérifié au démarrage |
| `atombox/services/` | — | le métier appelé par les contrôleurs, sans HTTP : `messages.py` sert le contrat que le webmail lit (dossiers spéciaux par alias IMAP, compteurs en une passe, sérialisation, rattachement) |
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

## Lancer une instance (V0)

```
export DATABASE_URL=postgresql:///atombox ATOMBOX_MAGASIN=/var/lib/atombox/magasin
.venv/bin/alembic upgrade head                                          # le schéma, par la file des migrations
.venv/bin/python -m atombox.amorcer --login mathieu --nom "Mathieu" --mot-de-passe … --boite contact@exemple.fr
ATOMBOX_IMAP_HOTE=imap.exemple.fr ATOMBOX_IMAP_MOT_DE_PASSE=… .venv/bin/python -m atombox.ingestion.demon   # la relève
ATOMBOX_SMTP_HOTE=smtp.exemple.fr .venv/bin/python -m atombox.taches                                        # événements, envois, tâches
.venv/bin/uvicorn atombox.api.app:app --host 0.0.0.0 --port 8010        # l'API sous /api/v1, le webmail sur /
```

Dans un conteneur, `localhost` est le sien : `--host 0.0.0.0` écoute sur toutes ses interfaces, et
depuis l'hôte on ouvre `http://dev.lxc:8010/` (le nom du conteneur ; 8000 y est déjà pris). Se connecter avec le compte amorcé : c'est le webmail du POC,
branché sur le vrai serveur — `serveur.poc.js` n'est pas chargé (D141, D157).

## Derrière Apache, en service (conteneur dev)

`outils/deployer-apache.sh` (avec `sudo`) installe le vhost **`atombox.dev.lxc`** (reverse proxy vers
l'API sur `127.0.0.1:8010`, qui sert aussi le webmail), le fichier `/etc/atombox/env` (les secrets :
base, magasin, IMAP, SMTP — copié de `outils/atombox.env.exemple` s'il n'existe pas) et trois unités
systemd : `atombox-api` (démarrée), `atombox-ingestion` et `atombox-taches` (installées, à démarrer
une fois l'environnement rempli). Idempotent. Puis, depuis l'hôte : `http://atombox.dev.lxc/`.

```
sudo bash serveur/outils/deployer-apache.sh          # ou --apache / --systemd
sudo systemctl start atombox-ingestion atombox-taches
journalctl -u atombox-api -f                          # et logs/ pour le journal applicatif (D152)
```

## Quatre mécanismes d'extension (D161, chapitre 19)

| | décorateur | niveau | garantie |
|---|---|---|---|
| accroche | `@accroche("message.ingere")` | noyau, synchrone, dans la transaction | échec journalisé et ignoré |
| déclencheur | `@declencheur("comm.apres_insertion")` | ORM, six points par entité | idem ; `RefusDeclencheur` refuse |
| événement | `@evenement("message.ingere")` | hors processus, table `evenement`, au moins une fois | tentatives 30 s → 24 h, abandon bruyant |
| tâche | `@tache(chaque="10m")` | cadencée par `python -m atombox.taches` | échec journalisé, reprogrammée |

Processus : `uvicorn atombox.api.app:app` (N travailleurs), `python -m atombox.ingestion.demon`
(`ATOMBOX_PART=2/4` pour partitionner les boîtes), `python -m atombox.taches` (N travailleurs).

## F001, F002 — l'ingestion et le magasin

`atombox/magasin/` : `ab/cd/<id>`, zstd conditionnel, jamais réécrit. `atombox/ingestion/` :
`analyse.py` (le MIME par `email`), `identite.py` (D064), `ingestion.py` (une transaction par
message, déduplication, rattachements, pièces, fil), `imap.py` (PEEK, reprise par UID, IDLE),
`demon.py` (une tâche par boîte). Tests sans base : analyse, identité, magasin, migrations ;
avec `DATABASE_URL` : ingestion complète dans une base jetable. La relève IMAP et le démon se
valident sur le pilote (D052), pas dans le harnais.
