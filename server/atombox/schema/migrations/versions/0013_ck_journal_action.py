"""La contrainte du journal parlait encore français — et elle refusait toute écriture (D054, D181).

Revision ID: 0013
Revises: 0012

CE QUI S'EST PASSÉ EN PRODUCTION, une heure après la mise en service. Un déplacement vers
« Indésirables » depuis Thunderbird rendait « erreur interne », puis TOUTES les commandes suivantes
de la session échouaient. La cause :

    new row for relation "journal" violates check constraint "ck_journal_action"
    Failing row contains (…, refiled, rattachement, …)

La migration 0011 a renommé les valeurs de l'énumération `action_journal` DANS LE DICTIONNAIRE —
donc dans `schema.sql`, dans les modèles et dans le code — mais elle n'a pas touché la contrainte
`ck_journal_action` de la base existante, qui acceptait toujours `lu`, `traite`, `partage`…

POURQUOI LE HARNAIS NE POUVAIT PAS LE VOIR, et c'est la vraie leçon : les bases de test sont montées
de `schema.sql`, qui est engendré du dictionnaire. Elles avaient donc la BONNE contrainte, et les
128 tests étaient verts. Seule une base passée par les MIGRATIONS gardait l'ancienne. C'est la
deuxième fois que cet angle mort coûte un incident (la première : `min(uuid)`, migration 0011), et
cette fois il est fermé par un test qui compare une base migrée à une base engendrée — pas par une
promesse de vigilance.

RÈGLE QUI EN DÉCOULE, à appliquer désormais sans y penser : **renommer une valeur d'énumération dans
le dictionnaire, c'est DEUX écritures** — le dictionnaire, et la contrainte de la base dans la même
migration. Le générateur ne peut pas la poser à notre place : il décrit un schéma neuf, il ne connaît
pas celui qui existe.
"""
from alembic import op
from atombox.journal import journal

log = journal("schema")

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Figées ici, comme dans toute migration : elle décrit une transition datée, pas l'état courant.
# Si le dictionnaire change encore, c'est une migration de plus — pas une relecture de celle-ci.
ACTIONS = ("opened", "processed", "archived", "deleted", "junked", "refiled", "status_changed",
           "marked", "shared", "revoked", "restored", "sender_trusted", "unsubscribed",
           "to_personal", "quarantine_released", "admin_read")

ANCIENNES = ("lu", "traite", "partage", "revoque", "supprime", "restaure", "valide_expediteur",
             "desabonne", "vers_personnel", "libere_quarantaine", "admin_lecture")

CORRESPONDANCE = {"lu": "opened", "traite": "processed", "partage": "shared", "revoque": "revoked",
                  "supprime": "deleted", "restaure": "restored",
                  "valide_expediteur": "sender_trusted", "desabonne": "unsubscribed",
                  "vers_personnel": "to_personal", "libere_quarantaine": "quarantine_released",
                  "admin_lecture": "admin_read"}


def _liste(valeurs):
    return ", ".join("'%s'" % v for v in valeurs)


def upgrade():
    # L'ORDRE COMPTE : on retire la contrainte AVANT de traduire les lignes, sinon la traduction
    # elle-même la viole. Le journal n'est jamais purgé (D054) : ces lignes sont l'historique, et
    # elles doivent parler la même langue que celles qu'on écrira demain.
    op.execute('ALTER TABLE "journal" DROP CONSTRAINT IF EXISTS "ck_journal_action"')
    for ancien, neuf in CORRESPONDANCE.items():
        op.execute("""UPDATE "journal" SET "action" = '%s' WHERE "action" = '%s'""" % (neuf, ancien))
    op.execute("""ALTER TABLE "journal" ADD CONSTRAINT "ck_journal_action"
                  CHECK ("action" IN (%s))""" % _liste(ACTIONS))


def downgrade():
    op.execute('ALTER TABLE "journal" DROP CONSTRAINT IF EXISTS "ck_journal_action"')
    # Les valeurs nées après 0011 n'ont pas d'ancien nom (`junked`, `refiled`, `status_changed`,
    # `marked`) : on ne les invente pas, on les laisse. La contrainte d'hier les refuserait, donc
    # on ne la repose que si rien ne la violerait — un retour arrière qui casse l'écriture du
    # journal serait pire que l'absence de contrainte.
    for ancien, neuf in CORRESPONDANCE.items():
        op.execute("""UPDATE "journal" SET "action" = '%s' WHERE "action" = '%s'""" % (ancien, neuf))
    cnx = op.get_bind()
    reste = cnx.exec_driver_sql("""SELECT count(*) FROM "journal" WHERE "action" NOT IN (%s)"""
                                % _liste(ANCIENNES)).scalar()
    if reste:
        log.warning("%d ligne(s) de journal portent une action née après 0011 : la contrainte "
                    "d'hier n'est pas reposée, elle les refuserait.", reste)
        return
    op.execute("""ALTER TABLE "journal" ADD CONSTRAINT "ck_journal_action"
                  CHECK ("action" IN (%s))""" % _liste(ANCIENNES))
