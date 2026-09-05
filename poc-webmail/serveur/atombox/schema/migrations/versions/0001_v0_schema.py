"""V0 — le schéma complet, engendré depuis le dictionnaire (F114, D138 : les tables de la V1 existent, vides)

Revision ID: 0001
Revises:
"""
import os
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

ICI = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(ICI, "..", "..", "schema.sql")

def upgrade():
    sql = open(SCHEMA, encoding="utf-8").read()
    # Alembic tient la transaction : on retire le BEGIN/COMMIT du fichier autonome
    sql = sql.replace("\nBEGIN;\n", "\n").replace("\nCOMMIT;\n", "\n")
    op.execute(sql)

def downgrade():
    import json
    manifest = json.load(open(os.path.join(ICI, "..", "..", "manifest.json"), encoding="utf-8"))
    for t in reversed(list(manifest["tables"])):
        op.execute('DROP TABLE IF EXISTS "%s" CASCADE' % t)
