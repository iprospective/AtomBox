"""F104 — comm.corps_texte et l'index GIN plein texte (français) sur sujet + corps (D031, D034)

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE "comm" ADD COLUMN "corps_texte" text')
    op.execute('''CREATE INDEX "ix_comm_plein_texte" ON "comm" USING GIN (to_tsvector('french', coalesce("sujet", '') || ' ' || coalesce("corps_texte", '')))''')

def downgrade():
    op.execute('DROP INDEX "ix_comm_plein_texte"')
    op.execute('ALTER TABLE "comm" DROP COLUMN "corps_texte"')
