"""F113 / D043 — l'UID IMAP appartient au rattachement : c'est (boîte, dossier) qui le définit, pas le message

Revision ID: 0007
Revises: 0006
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "uid_imap" bigint')
    # reprise : l'UID posé à l'ingestion sur comm_email vaut pour le rattachement d'origine
    op.execute('''UPDATE "rattachement" r SET "uid_imap" = e."uid"
                  FROM "comm_email" e WHERE e."comm_id" = r."comm_id" AND e."uid" IS NOT NULL AND r."uid_imap" IS NULL''')
    op.execute('CREATE INDEX "ix_rattachement_uid_imap" ON "rattachement" ("dossier_id", "uid_imap")')

def downgrade():
    op.execute('DROP INDEX "ix_rattachement_uid_imap"')
    op.execute('ALTER TABLE "rattachement" DROP COLUMN "uid_imap"')
