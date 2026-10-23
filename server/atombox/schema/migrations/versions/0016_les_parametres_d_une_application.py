"""Les réglages d'une application connectée, propres à son type (D187 § 3, RM3518).

Revision ID: 0016
Revises: 0015

Pour Dolibarr : les HÔTES de ses Message-ID (`…-dolibarr-pro123@<hôte>`). La règle d'en-tête ne
reconnaît que ceux de l'instance déclarée — un fournisseur qui utilise aussi Dolibarr écrit
`dolibarr-inv45` chez lui, et sa facture 45 n'est pas la nôtre. Une colonne nullable : rien à
reprendre."""
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE "application" ADD COLUMN "parametres" jsonb')


def downgrade():
    op.execute('ALTER TABLE "application" DROP COLUMN "parametres"')
