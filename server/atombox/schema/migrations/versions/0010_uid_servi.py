"""Q024 — l'UID qu'AtomBox SERT à ses propres clients IMAP, et son UIDVALIDITY.

Revision ID: 0010
Revises: 0009

Deux invariants IMAP que le CDC réclame « maintenant » parce qu'ils se rattrapent très mal : un UID
stable, croissant, JAMAIS réutilisé, et un UIDVALIDITY qui dit au client de jeter son cache. Les
ajouter plus tard obligerait à réattribuer des UID à tout l'existant — et tout client déjà
synchronisé resynchroniserait intégralement.

Ne pas confondre avec `dossier.uid_validity` / `uid_suivant` / `rattachement.uid_imap`, qui sont
ceux du FOURNISSEUR chez qui AtomBox relève (D043, F001). Ceux-ci sont les nôtres.

La reprise attribue les UID dans l'ordre d'ARRIVÉE (`date_recue`, puis `comm_id` qui est un UUID v7,
donc lui-même ordonné) : un client qui se synchronise pour la première fois voit les messages dans
l'ordre où ils sont arrivés, et non dans celui, arbitraire, où la base les rend.
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('ALTER TABLE "dossier" ADD COLUMN "uid_validity_servie" bigint')
    op.execute('ALTER TABLE "dossier" ADD COLUMN "uid_servi_suivant" bigint')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "uid_servi" bigint')
    # UIDVALIDITY : un entier non nul, stable. L'heure de la migration suffit et se compare.
    op.execute("""UPDATE "dossier" SET "uid_validity_servie" = EXTRACT(EPOCH FROM now())::bigint
                  WHERE "uid_validity_servie" IS NULL""")
    # la reprise : numérotation par dossier, dans l'ordre d'arrivée
    op.execute("""
WITH ordonnes AS (
  SELECT r."comm_id", r."boite_id",
         row_number() OVER (PARTITION BY r."dossier_id" ORDER BY c."date_recue", r."comm_id") AS n
    FROM "rattachement" r JOIN "comm" c ON c."comm_id" = r."comm_id"
   WHERE r."dossier_id" IS NOT NULL
)
UPDATE "rattachement" r SET "uid_servi" = o.n
  FROM ordonnes o WHERE o."comm_id" = r."comm_id" AND o."boite_id" = r."boite_id"
""")
    # le compteur repart APRÈS le plus grand servi — jamais réutilisé
    op.execute("""
UPDATE "dossier" d SET "uid_servi_suivant" =
  COALESCE((SELECT max(r."uid_servi") FROM "rattachement" r WHERE r."dossier_id" = d."dossier_id"), 0) + 1
""")
    op.execute('CREATE UNIQUE INDEX "uq_rattachement_uid_servi" ON "rattachement" ("dossier_id", "uid_servi") WHERE "uid_servi" IS NOT NULL')


def downgrade():
    op.execute('DROP INDEX IF EXISTS "uq_rattachement_uid_servi"')
    op.execute('ALTER TABLE "rattachement" DROP COLUMN "uid_servi"')
    op.execute('ALTER TABLE "dossier" DROP COLUMN "uid_servi_suivant"')
    op.execute('ALTER TABLE "dossier" DROP COLUMN "uid_validity_servie"')
