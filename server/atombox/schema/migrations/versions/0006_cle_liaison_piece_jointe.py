"""D011 — la clé de comm_piece_jointe devient (comm_id, ordre) : une même pièce peut être jointe deux fois à un message

Revision ID: 0006
Revises: 0005
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade():
    op.execute('ALTER TABLE "comm_piece_jointe" DROP CONSTRAINT "pk_comm_piece_jointe"')
    op.execute('ALTER TABLE "comm_piece_jointe" ADD CONSTRAINT "pk_comm_piece_jointe" PRIMARY KEY ("comm_id", "ordre")')
    op.execute('CREATE INDEX IF NOT EXISTS "ix_comm_piece_jointe_piece_jointe_id" ON "comm_piece_jointe" ("piece_jointe_id")')

def downgrade():
    op.execute('ALTER TABLE "comm_piece_jointe" DROP CONSTRAINT "pk_comm_piece_jointe"')
    op.execute('ALTER TABLE "comm_piece_jointe" ADD CONSTRAINT "pk_comm_piece_jointe" PRIMARY KEY ("comm_id", "piece_jointe_id")')
