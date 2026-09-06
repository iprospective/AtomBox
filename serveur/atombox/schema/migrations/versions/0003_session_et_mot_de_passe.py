"""F124 / D158 — la table session (jeton haché, expiration, révocation) et compte.mot_de_passe_empreinte

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE "compte" ADD COLUMN "mot_de_passe_empreinte" text')
    op.execute('''CREATE TABLE "session" (
  "session_id" uuid NOT NULL,
  "compte_id" uuid NOT NULL,
  "jeton_empreinte" text NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "expire_le" timestamptz NOT NULL,
  "revoque_le" timestamptz,
  "agent" text,
  CONSTRAINT "pk_session" PRIMARY KEY ("session_id")
)''')
    op.execute('ALTER TABLE "session" ADD CONSTRAINT "fk_session_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('ALTER TABLE "session" ADD CONSTRAINT "uq_session_jeton_empreinte" UNIQUE ("jeton_empreinte")')
    op.execute('CREATE INDEX "ix_session_compte_id" ON "session" ("compte_id")')

def downgrade():
    op.execute('DROP TABLE "session"')
    op.execute('ALTER TABLE "compte" DROP COLUMN "mot_de_passe_empreinte"')
