"""D164 / F129 — mot de passe oublié : adresse de secours et jeton à usage unique

Revision ID: 0009
Revises: 0008
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE "compte" ADD COLUMN "email_secours" text')
    op.execute("""
CREATE TABLE "reinitialisation" (
  "reinitialisation_id" uuid NOT NULL,
  "compte_id" uuid NOT NULL,
  "jeton_empreinte" text NOT NULL,
  "envoye_a" text NOT NULL,
  "demande_le" timestamptz NOT NULL,
  "expire_le" timestamptz NOT NULL,
  "utilise_le" timestamptz,
  "demande_par_ip" text,
  CONSTRAINT "pk_reinitialisation" PRIMARY KEY ("reinitialisation_id")
)""")
    op.execute('''ALTER TABLE "reinitialisation" ADD CONSTRAINT "fk_reinitialisation_compte_id"
                  FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE''')
    op.execute('CREATE INDEX "ix_reinitialisation_compte_id" ON "reinitialisation" ("compte_id")')
    op.execute('ALTER TABLE "reinitialisation" ADD CONSTRAINT "uq_reinitialisation_jeton_empreinte" UNIQUE ("jeton_empreinte")')

def downgrade():
    op.execute('DROP TABLE "reinitialisation"')
    op.execute('ALTER TABLE "compte" DROP COLUMN "email_secours"')
