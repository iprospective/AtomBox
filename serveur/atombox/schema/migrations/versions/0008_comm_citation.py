"""D163 / F125 — la citation d'un message est une relation, pas une copie

La table arrive avec le dictionnaire (le schéma est engendré de lui, tous jalons confondus) ;
elle ne sera écrite qu'à partir de F125, à l'émission. Les deux clés étrangères sont SANS
cascade, volontairement : un message cité ne s'efface pas sans qu'on matérialise la citation
chez ceux qui le citent.

Revision ID: 0008
Revises: 0007
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("""
CREATE TABLE "comm_citation" (
  "comm_citation_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "cite_comm_id" uuid,
  "cite_message_id" text,
  "part_citee" numeric NOT NULL,
  "part_modifiee" numeric NOT NULL,
  "position" text NOT NULL,
  "recette" jsonb,
  "origine" text NOT NULL,
  "detecte_le" timestamptz NOT NULL,
  CONSTRAINT "pk_comm_citation" PRIMARY KEY ("comm_citation_id"),
  CONSTRAINT "ck_comm_citation_position" CHECK ("position" IN ('avant', 'apres', 'intercale')),
  CONSTRAINT "ck_comm_citation_origine" CHECK ("origine" IN ('emission', 'ingestion'))
)""")
    op.execute('''ALTER TABLE "comm_citation" ADD CONSTRAINT "fk_comm_citation_comm_id"
                  FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE''')
    op.execute('''ALTER TABLE "comm_citation" ADD CONSTRAINT "fk_comm_citation_cite_comm_id"
                  FOREIGN KEY ("cite_comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE''')
    op.execute('CREATE INDEX "ix_comm_citation_comm_id" ON "comm_citation" ("comm_id")')
    op.execute('CREATE INDEX "ix_comm_citation_cite_comm_id" ON "comm_citation" ("cite_comm_id")')

def downgrade():
    op.execute('DROP TABLE "comm_citation"')
