"""D161 — la table evenement : la boîte d'envoi persistée, rejouable

Revision ID: 0004
Revises: 0003
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('''CREATE TABLE "evenement" (
  "evenement_id" uuid NOT NULL,
  "type" text NOT NULL,
  "module" text NOT NULL,
  "cible" text,
  "charge" jsonb NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "prochaine_tentative" timestamptz NOT NULL,
  "tentatives" bigint NOT NULL,
  "traite_le" timestamptz,
  "abandonne" boolean,
  "erreur" text,
  CONSTRAINT "pk_evenement" PRIMARY KEY ("evenement_id")
)''')
    op.execute('CREATE INDEX "ix_evenement_file" ON "evenement" ("prochaine_tentative") WHERE "traite_le" IS NULL')

def downgrade():
    op.execute('DROP TABLE "evenement"')
