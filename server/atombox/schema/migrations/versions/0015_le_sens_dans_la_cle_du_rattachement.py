"""D185 — un message est présent dans une boîte UNE FOIS PAR RÔLE : reçu, émis (RM3504).

La clé du rattachement était (message, boîte) : un message n'avait qu'une place par adresse. Envoyé
à soi-même, son exemplaire livré dans la boîte de réception était donc fusionné avec l'exemplaire
envoyé (l'identité D064 les reconnaît, à raison) et ne prenait aucune place. La clé devient
(message, boîte, sens).

LE SENS DE CHAQUE PLACE EXISTANTE, et pas celui du message. Mesuré le 21/10 en production : deux
messages rangés dans Envoyés portaient `comm.sens = 'in'` — la relève ingérait le dossier Envoyés du
fournisseur avec le sens par défaut. Une place dans un dossier Envoyés ou Brouillons est ÉMISE ;
ailleurs, elle prend le sens de son message. Un envoyé déplacé à la corbeille reste émis : c'est sa
place qui a bougé, pas son rôle.

Le retour arrière remet la clé (message, boîte). Il ne peut pas garder deux places pour un même
message dans une même boîte : s'il en trouve, il garde la place REÇUE et retire l'émise — en le
disant au journal, avec le compte.
"""
from alembic import op
from atombox.journal import journal

log = journal("schema")

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "sens" text')
    op.execute("""
        UPDATE "rattachement" r SET "sens" = CASE
            WHEN EXISTS (SELECT 1 FROM "dossier" d WHERE d."dossier_id" = r."dossier_id"
                         AND d."special_use" IN ('\\Sent', '\\Drafts')) THEN 'out'
            ELSE (SELECT c."sens" FROM "comm" c WHERE c."comm_id" = r."comm_id") END
    """)
    n = op.get_bind().exec_driver_sql('SELECT count(*) FROM "rattachement" WHERE "sens" IS NULL').scalar()
    if n:
        raise RuntimeError("%d rattachement(s) sans sens après reprise — on ne pose pas la clé sur un trou" % n)
    op.execute('ALTER TABLE "rattachement" ALTER COLUMN "sens" SET NOT NULL')
    op.execute('ALTER TABLE "rattachement" ADD CONSTRAINT "ck_rattachement_sens" CHECK ("sens" IN (\'in\', \'out\'))')
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT "pk_rattachement"')
    op.execute('ALTER TABLE "rattachement" ADD CONSTRAINT "pk_rattachement" PRIMARY KEY ("comm_id", "boite_id", "sens")')
    log.info("rattachement : le sens entre dans la clé (D185)")


def downgrade():
    cnx = op.get_bind()
    doubles = cnx.exec_driver_sql("""
        SELECT count(*) FROM "rattachement" o WHERE o."sens" = 'out'
          AND EXISTS (SELECT 1 FROM "rattachement" i WHERE i."comm_id" = o."comm_id"
                      AND i."boite_id" = o."boite_id" AND i."sens" = 'in')""").scalar()
    if doubles:
        log.warning("retour avant D185 : %d place(s) émise(s) retirée(s) — leur message a aussi une place reçue "
                    "dans la même boîte, et l'ancienne clé n'en admet qu'une", doubles)
        op.execute("""
            DELETE FROM "rattachement" o WHERE o."sens" = 'out'
              AND EXISTS (SELECT 1 FROM "rattachement" i WHERE i."comm_id" = o."comm_id"
                          AND i."boite_id" = o."boite_id" AND i."sens" = 'in')""")
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT "pk_rattachement"')
    op.execute('ALTER TABLE "rattachement" ADD CONSTRAINT "pk_rattachement" PRIMARY KEY ("comm_id", "boite_id")')
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT "ck_rattachement_sens"')
    op.execute('ALTER TABLE "rattachement" DROP COLUMN "sens"')
