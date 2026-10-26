"""La famille : un niveau au-dessus de l'axe (D188, RM3519).

Revision ID: 0017
Revises: 0016

Une famille regroupe plusieurs axes (Dolibarr → propositions, commandes, factures…) ; un axe est
dans une famille au plus. Les axes existants n'ont pas de famille : le connecteur la posera à la
création de son application, ou on la configurera axe par axe. Rien à reprendre."""
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE "famille" (
  "famille_id" uuid NOT NULL,
  "nom" text NOT NULL,
  "libelle" text NOT NULL,
  "ordre" bigint,
  CONSTRAINT "pk_famille" PRIMARY KEY ("famille_id")
)''')
    op.execute('ALTER TABLE "famille" ADD CONSTRAINT "uq_famille_nom" UNIQUE ("nom")')
    op.execute('ALTER TABLE "axe" ADD COLUMN "famille_id" uuid')
    op.execute('ALTER TABLE "axe" ADD CONSTRAINT "fk_axe_famille_id" FOREIGN KEY ("famille_id") '
               'REFERENCES "famille" ("famille_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('CREATE INDEX "ix_axe_famille_id" ON "axe" ("famille_id")')


def downgrade():
    op.execute('ALTER TABLE "axe" DROP COLUMN "famille_id"')
    op.execute('DROP TABLE "famille"')
