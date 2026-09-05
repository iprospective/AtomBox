"""F001 — la reprise par UID : uid_validity et uid_suivant sur dossier ; un dossier IMAP par (boîte, alias)

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE "dossier" ADD COLUMN "uid_validity" bigint, ADD COLUMN "uid_suivant" bigint')
    op.execute('ALTER TABLE "dossier" ADD CONSTRAINT "uq_dossier_boite_id_alias_imap" UNIQUE ("boite_id", "alias_imap")')

def downgrade():
    op.execute('ALTER TABLE "dossier" DROP CONSTRAINT "uq_dossier_boite_id_alias_imap"')
    op.execute('ALTER TABLE "dossier" DROP COLUMN "uid_suivant", DROP COLUMN "uid_validity"')
