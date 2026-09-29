"""D175, D177, D178 — l'état d'un message se lit sur TROIS PLANS, et il change de place.

Revision ID: 0011
Revises: 0010

Ce que le rattachement mélangeait, et que cette migration sépare :

    le FAIT       « ouvert le 3 à 9 h 12, par moi »   → read_state, par personne, JAMAIS effacé
    l'INTENTION   « à revoir »                        → marker_personal, creux
    l'ACTE SIGNÉ  « traité par Untel le 10 »           → le rattachement, un par boîte

`lu_le` confondait les deux premiers, et sur une boîte partagée il confondait en plus le personnel
et le collectif. Conséquence vécue : **« marquer comme non lu » détruisait la seule trace que
quelqu'un avait regardé.** On n'efface pas un fait pour exprimer une intention.

QUATRE COUPLES DE DATES, PAS UNE. `sorti_le` disparaît au profit de `processed_at`, `archived_at`,
`deleted_at`, `junk_at`. La raison n'est pas l'esthétique : un message est généralement traité, PUIS
archivé des années après. Si archiver écrasait la date de traitement, on perdrait la clé d'archivage
(D014) — c'est-à-dire la donnée qui commande la transition suivante. L'état COURANT reste unique et
exclusif (`exit_reason`), parce qu'un message est dans une et une seule boîte aux lettres.

LA REPRISE DE `lu_le` EST LE POINT DÉLICAT, et elle ne peut pas être parfaite : l'ancien `lu_le`
d'une boîte partagée dit « quelqu'un l'a ouvert », sans dire qui. On ne l'invente pas. On attribue
donc la lecture :

  1. au compte du rattachement s'il en porte un (brouillon, envoi) ;
  2. sinon au SEUL accès actif de la boîte, quand il n'y en a qu'un — le cas des boîtes
     personnelles, qui est aussi celui de tout l'existant au jour de cette migration ;
  3. sinon à personne, et la ligne n'est pas créée : le message redeviendra « non lu » pour chacun.
     Perdre un affichage est moins grave que d'écrire que trois personnes ont ouvert un message
     qu'une seule a lu — un faux fait ne se distingue plus d'un vrai, ensuite.

Le compte de ce qui n'a pas pu être attribué est JOURNALISÉ par la migration : sans ça, la décision
ci-dessus serait invisible à celui qui constate le lendemain que sa boîte partagée est toute en gras.
"""
from alembic import op
from atombox.journal import journal

log = journal("schema")

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# Les deux marqueurs livrés d'office (D178) viennent de `atombox/schema/semences.py` : une base
# créée de `schema.sql` (les tests, une instance neuve) n'en reçoit aucun, et deux listes auraient
# divergé au premier marqueur ajouté. Une seule table de vérité, deux chemins qui la lisent.
from atombox.schema.semences import MARQUEURS_INTEGRES
MARQUEUR_A_REVOIR = MARQUEURS_INTEGRES[0]["marker_id"]
MARQUEUR_SOMMEIL = MARQUEURS_INTEGRES[1]["marker_id"]


def upgrade():
    # ── 1. les faits de lecture, par personne (D175 § 1) ────────────────────────────────────────
    op.execute("""
CREATE TABLE "read_state" (
  "compte_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "opened_at" timestamptz,
  "last_seen_at" timestamptz,
  "open_count" bigint NOT NULL,
  "flagged" boolean NOT NULL,
  CONSTRAINT "pk_read_state" PRIMARY KEY ("compte_id", "comm_id", "boite_id")
)""")
    op.execute('ALTER TABLE "read_state" ADD CONSTRAINT "fk_read_state_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('ALTER TABLE "read_state" ADD CONSTRAINT "fk_read_state_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('ALTER TABLE "read_state" ADD CONSTRAINT "fk_read_state_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('CREATE INDEX "ix_read_state_comm_id" ON "read_state" ("comm_id")')
    op.execute('CREATE INDEX "ix_read_state_boite_id" ON "read_state" ("boite_id")')

    # ── 2. les marqueurs : la déclaration, puis les deux tables de pose (D178) ──────────────────
    op.execute("""
CREATE TABLE "marker" (
  "marker_id" uuid NOT NULL,
  "code" text NOT NULL,
  "libelle" text NOT NULL,
  "scope" text NOT NULL,
  "value_type" text NOT NULL,
  "domaine_id" uuid,
  "options" jsonb,
  "actif" boolean NOT NULL,
  "integre" boolean NOT NULL,
  CONSTRAINT "pk_marker" PRIMARY KEY ("marker_id"),
  CONSTRAINT "ck_marker_scope" CHECK ("scope" IN ('collective', 'personal')),
  CONSTRAINT "ck_marker_value_type" CHECK ("value_type" IN ('presence', 'moment', 'choix'))
)""")
    op.execute('ALTER TABLE "marker" ADD CONSTRAINT "uq_marker_code" UNIQUE ("code")')
    op.execute('ALTER TABLE "marker" ADD CONSTRAINT "fk_marker_domaine_id" FOREIGN KEY ("domaine_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('CREATE INDEX "ix_marker_domaine_id" ON "marker" ("domaine_id")')
    op.execute("""
CREATE TABLE "marker_collective" (
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "marker_id" uuid NOT NULL,
  "set_at" timestamptz NOT NULL,
  "set_by" uuid,
  "due_at" timestamptz,
  "value" text,
  CONSTRAINT "pk_marker_collective" PRIMARY KEY ("comm_id", "boite_id", "marker_id")
)""")
    op.execute("""
CREATE TABLE "marker_personal" (
  "compte_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "marker_id" uuid NOT NULL,
  "set_at" timestamptz NOT NULL,
  "due_at" timestamptz,
  "value" text,
  CONSTRAINT "pk_marker_personal" PRIMARY KEY ("compte_id", "comm_id", "boite_id", "marker_id")
)""")
    for t, cols in (("marker_collective", ("comm_id", "boite_id", "marker_id", "set_by")),
                    ("marker_personal", ("compte_id", "comm_id", "boite_id", "marker_id"))):
        for c in cols:
            cible = {"comm_id": ("comm", "comm_id"), "boite_id": ("boite", "boite_id"),
                     "marker_id": ("marker", "marker_id"), "compte_id": ("compte", "compte_id"),
                     "set_by": ("compte", "compte_id")}[c]
            op.execute('ALTER TABLE "%s" ADD CONSTRAINT "fk_%s_%s" FOREIGN KEY ("%s") REFERENCES "%s" ("%s") DEFERRABLE INITIALLY IMMEDIATE'
                       % (t, t, c, c, cible[0], cible[1]))
    for idx in ('"ix_marker_collective_boite_id" ON "marker_collective" ("boite_id")',
                '"ix_marker_collective_marker_id" ON "marker_collective" ("marker_id")',
                '"ix_marker_collective_set_by" ON "marker_collective" ("set_by")',
                '"ix_marker_personal_comm_id" ON "marker_personal" ("comm_id")',
                '"ix_marker_personal_boite_id" ON "marker_personal" ("boite_id")',
                '"ix_marker_personal_marker_id" ON "marker_personal" ("marker_id")'):
        op.execute("CREATE INDEX " + idx)
    # « qu'est-ce qui se réveille maintenant ? » doit être un parcours d'index, pas un balayage :
    # c'est la seule raison pour laquelle la date est une COLONNE et non une clé du json.
    op.execute('CREATE INDEX "ix_marker_personal_due_at" ON "marker_personal" ("due_at") WHERE "due_at" IS NOT NULL')
    op.execute('CREATE INDEX "ix_marker_collective_due_at" ON "marker_collective" ("due_at") WHERE "due_at" IS NOT NULL')
    for m in MARQUEURS_INTEGRES:
        op.execute("""INSERT INTO "marker" ("marker_id", "code", "libelle", "scope", "value_type",
                                            "actif", "integre")
                      VALUES ('%(marker_id)s', '%(code)s', '%(libelle)s', '%(scope)s',
                              '%(value_type)s', true, true)
                      ON CONFLICT ("code") DO NOTHING""" % m)

    # ── 3. l'accès porte la relève et ses options (D177) ────────────────────────────────────────
    op.execute('ALTER TABLE "acces" ADD COLUMN "stands_in_for" uuid')
    op.execute('ALTER TABLE "acces" ADD COLUMN "options" jsonb')
    op.execute('ALTER TABLE "acces" ADD CONSTRAINT "fk_acces_stands_in_for" FOREIGN KEY ("stands_in_for") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE')
    op.execute('CREATE INDEX "ix_acces_stands_in_for" ON "acces" ("stands_in_for")')

    # ── 4. le workflow : anglais (D181), collectif, signé ──────────────────────────────────────
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT IF EXISTS "ck_rattachement_statut"')
    op.execute('ALTER TABLE "rattachement" RENAME COLUMN "statut" TO "status"')
    op.execute("""UPDATE "rattachement" SET "status" = CASE "status"
                    WHEN 'nouveau' THEN 'new' WHEN 'a_faire' THEN 'todo' WHEN 'en_cours' THEN 'doing'
                    WHEN 'attente' THEN 'waiting' WHEN 'traite' THEN 'processed' ELSE "status" END""")
    op.execute("""ALTER TABLE "rattachement" ADD CONSTRAINT "ck_rattachement_status"
                  CHECK ("status" IN ('new', 'todo', 'doing', 'waiting', 'processed'))""")
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "status_at" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "status_by" uuid')

    # ── 5. la sortie : une valeur courante, quatre couples de dates ─────────────────────────────
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT IF EXISTS "ck_rattachement_motif_sortie"')
    op.execute('ALTER TABLE "rattachement" RENAME COLUMN "motif_sortie" TO "exit_reason"')
    op.execute("""UPDATE "rattachement" SET "exit_reason" = CASE "exit_reason"
                    WHEN 'traite' THEN 'processed' WHEN 'archive' THEN 'archived'
                    WHEN 'supprime' THEN 'deleted' ELSE "exit_reason" END""")
    # `supprime_par` existait : c'était le même besoin — qui a fait ça — traité UNE fois, pour un
    # seul cas. Il devient `deleted_by`, et ses trois frères apparaissent.
    op.execute('ALTER TABLE "rattachement" RENAME COLUMN "supprime_par" TO "deleted_by"')
    op.execute('ALTER TABLE "rattachement" RENAME CONSTRAINT "fk_rattachement_supprime_par" TO "fk_rattachement_deleted_by"')
    op.execute('ALTER INDEX "ix_rattachement_supprime_par" RENAME TO "ix_rattachement_deleted_by"')
    # DÉROULÉ À DESSEIN : une boucle `% c` produirait le même schéma, mais le contrôle de fraîcheur
    # (tests/test_migrations.py) LIT ce fichier — il ne voit pas ce qu'une boucle engendre, et il
    # annonçait ces colonnes comme « sans migration ». Écrire les noms les rend cherchables, par le
    # test comme par qui relira.
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "processed_at" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "processed_by" uuid')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "archived_at" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "archived_by" uuid')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "deleted_at" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "junk_at" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "junk_by" uuid')
    for c in ("status_by", "processed_by", "archived_by", "junk_by"):
        op.execute('ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_%s" FOREIGN KEY ("%s") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE' % (c, c))
        op.execute('CREATE INDEX "ix_rattachement_%s" ON "rattachement" ("%s")' % (c, c))
    # la date de sortie unique se range dans la case de l'état où elle a été posée
    op.execute("""UPDATE "rattachement" SET
                    "processed_at" = CASE WHEN "exit_reason" = 'processed' THEN "sorti_le" END,
                    "archived_at"  = CASE WHEN "exit_reason" = 'archived'  THEN "sorti_le" END,
                    "deleted_at"   = CASE WHEN "exit_reason" = 'deleted'   THEN "sorti_le" END
                  WHERE "sorti_le" IS NOT NULL""")
    # Un message traité PUIS archivé avant cette migration a perdu sa date de traitement : l'ancien
    # modèle n'avait qu'une case. On ne l'invente pas — mais un statut « traité » resté sur la ligne
    # la dit, et vaut mieux que rien. Sans cela, l'archivage automatique (D014) n'aurait aucune clé
    # sur l'existant, et ce serait un trou permanent, pas un trou d'un jour.
    op.execute("""UPDATE "rattachement" SET "processed_at" = "archived_at"
                   WHERE "exit_reason" = 'archived' AND "status" = 'processed' AND "processed_at" IS NULL""")

    # LES DOSSIERS SPÉCIAUX DEVIENNENT DES VALEURS (D051 réalisée). Corbeille et Indésirables
    # étaient des dossiers, Traités et Archivés une colonne : deux mécaniques pour une seule idée.
    # La colonne devient la vérité pour les quatre. Le dossier reste le CONTENANT que sert l'IMAP,
    # tant que l'UID appartient au dossier (Q024/RM3321) — c'est le ticket des cinq boîtes aux
    # lettres qui tranchera à qui l'UID appartient, et lui seul peut supprimer ces dossiers.
    op.execute("""
UPDATE "rattachement" r SET "exit_reason" = 'deleted',
       "deleted_at" = COALESCE(r."deleted_at", c."date_ingestion", now())
  FROM "dossier" d, "comm" c
 WHERE d."dossier_id" = r."dossier_id" AND c."comm_id" = r."comm_id"
   AND upper(split_part(COALESCE(d."alias_imap", d."nom"), '/', -1))
       IN ('TRASH', 'DELETED ITEMS', 'CORBEILLE')
   AND r."exit_reason" IS NULL""")
    op.execute("""
UPDATE "rattachement" r SET "exit_reason" = 'junk',
       "junk_at" = COALESCE(r."junk_at", c."date_ingestion", now())
  FROM "dossier" d, "comm" c
 WHERE d."dossier_id" = r."dossier_id" AND c."comm_id" = r."comm_id"
   AND upper(split_part(COALESCE(d."alias_imap", d."nom"), '/', -1))
       IN ('JUNK', 'SPAM', 'INDÉSIRABLES', 'INDESIRABLES')
   AND r."exit_reason" IS NULL""")
    op.execute("""ALTER TABLE "rattachement" ADD CONSTRAINT "ck_rattachement_exit_reason"
                  CHECK ("exit_reason" IN ('processed', 'archived', 'deleted', 'junk'))""")
    op.execute('ALTER TABLE "rattachement" DROP COLUMN "sorti_le"')

    # ── 6. la reprise des faits de lecture et du drapeau ───────────────────────────────────────
    # Une ligne dès que quelqu'un a TOUCHÉ le message : ouvert, ou seulement marqué d'un drapeau.
    # C'est pour cela qu'`opened_at` est nullable — poser un drapeau n'est pas lire.
    op.execute("""
INSERT INTO "read_state" ("compte_id", "comm_id", "boite_id", "opened_at", "last_seen_at", "open_count", "flagged")
SELECT COALESCE(r."compte_id", seul."compte_id"), r."comm_id", r."boite_id",
       r."lu_le", r."lu_le", CASE WHEN r."lu_le" IS NULL THEN 0 ELSE 1 END, r."drapeau"
  FROM "rattachement" r
  LEFT JOIN (SELECT "boite_id", min("compte_id") AS "compte_id", count(*) AS n
               FROM "acces" WHERE "fin" IS NULL GROUP BY "boite_id") seul
         ON seul."boite_id" = r."boite_id" AND seul.n = 1
 WHERE (r."lu_le" IS NOT NULL OR r."drapeau")
   AND COALESCE(r."compte_id", seul."compte_id") IS NOT NULL
ON CONFLICT DO NOTHING""")

    # ── 7. la mise en sommeil devient un marqueur, et quitte le chemin chaud ────────────────────
    op.execute("""
INSERT INTO "marker_personal" ("compte_id", "comm_id", "boite_id", "marker_id", "set_at", "due_at")
SELECT COALESCE(r."compte_id", seul."compte_id"), r."comm_id", r."boite_id", '%s', now(), r."reveil_le"
  FROM "rattachement" r
  LEFT JOIN (SELECT "boite_id", min("compte_id") AS "compte_id", count(*) AS n
               FROM "acces" WHERE "fin" IS NULL GROUP BY "boite_id") seul
         ON seul."boite_id" = r."boite_id" AND seul.n = 1
 WHERE r."reveil_le" IS NOT NULL AND COALESCE(r."compte_id", seul."compte_id") IS NOT NULL
ON CONFLICT DO NOTHING""" % MARQUEUR_SOMMEIL)

    # ── 8. ce qui n'a pas pu être attribué : on le DIT, avant de jeter les colonnes ─────────────
    cnx = op.get_bind()
    orphelins = cnx.exec_driver_sql("""
SELECT count(*) FROM "rattachement" r
  LEFT JOIN (SELECT "boite_id", count(*) AS n FROM "acces" WHERE "fin" IS NULL GROUP BY "boite_id") a
         ON a."boite_id" = r."boite_id"
 WHERE (r."lu_le" IS NOT NULL OR r."drapeau" OR r."reveil_le" IS NOT NULL)
   AND r."compte_id" IS NULL AND COALESCE(a.n, 0) <> 1""").scalar()
    if orphelins:
        log.warning("%d lecture(s) d'une boîte à plusieurs membres n'ont pas pu être attribuées : "
                    "l'ancien lu_le ne disait pas QUI. Ces messages redeviennent non lus pour "
                    "chacun (D175 — on n'écrit pas un fait qu'on n'a pas observé).", orphelins)

    op.execute('ALTER TABLE "rattachement" DROP COLUMN "lu_le"')
    op.execute('ALTER TABLE "rattachement" DROP COLUMN "drapeau"')
    op.execute('ALTER TABLE "rattachement" DROP COLUMN "reveil_le"')


def downgrade():
    # Le retour rend les colonnes et repose ce qu'on sait reposer. Ce qui a été SÉPARÉ ne se
    # recolle pas exactement : plusieurs lectures personnelles retombent sur un seul `lu_le`, et
    # c'est la plus ancienne qu'on garde — celle qui est vraie pour la boîte.
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "lu_le" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "drapeau" boolean')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "reveil_le" timestamptz')
    op.execute('ALTER TABLE "rattachement" ADD COLUMN "sorti_le" timestamptz')
    op.execute('''
UPDATE "rattachement" r SET "lu_le" = x."opened_at", "drapeau" = x."flagged"
  FROM (SELECT "comm_id", "boite_id", min("opened_at") AS "opened_at", bool_or("flagged") AS "flagged"
          FROM "read_state" GROUP BY "comm_id", "boite_id") x
 WHERE x."comm_id" = r."comm_id" AND x."boite_id" = r."boite_id"''')
    op.execute('UPDATE "rattachement" SET "drapeau" = false WHERE "drapeau" IS NULL')
    op.execute('ALTER TABLE "rattachement" ALTER COLUMN "drapeau" SET NOT NULL')
    op.execute("""
UPDATE "rattachement" r SET "reveil_le" = m."due_at"
  FROM "marker_personal" m JOIN "marker" k ON k."marker_id" = m."marker_id"
 WHERE m."comm_id" = r."comm_id" AND m."boite_id" = r."boite_id" AND k."code" = 'snooze'""")
    op.execute("""UPDATE "rattachement" SET "sorti_le" =
                    COALESCE("processed_at", "archived_at", "deleted_at", "junk_at")""")
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT IF EXISTS "ck_rattachement_exit_reason"')
    op.execute("""UPDATE "rattachement" SET "exit_reason" = CASE "exit_reason"
                    WHEN 'processed' THEN 'traite' WHEN 'archived' THEN 'archive'
                    WHEN 'deleted' THEN 'supprime' WHEN 'junk' THEN 'supprime' ELSE "exit_reason" END""")
    op.execute('ALTER TABLE "rattachement" RENAME COLUMN "exit_reason" TO "motif_sortie"')
    op.execute("""ALTER TABLE "rattachement" ADD CONSTRAINT "ck_rattachement_motif_sortie"
                  CHECK ("motif_sortie" IN ('traite', 'archive', 'supprime'))""")
    for c in ("status_by", "processed_by", "archived_by", "junk_by"):
        op.execute('DROP INDEX IF EXISTS "ix_rattachement_%s"' % c)
        op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT IF EXISTS "fk_rattachement_%s"' % c)
    for c in ("processed_at", "archived_at", "deleted_at", "junk_at", "processed_by", "archived_by",
              "junk_by", "status_at", "status_by"):
        op.execute('ALTER TABLE "rattachement" DROP COLUMN IF EXISTS "%s"' % c)
    op.execute('ALTER INDEX "ix_rattachement_deleted_by" RENAME TO "ix_rattachement_supprime_par"')
    op.execute('ALTER TABLE "rattachement" RENAME CONSTRAINT "fk_rattachement_deleted_by" TO "fk_rattachement_supprime_par"')
    op.execute('ALTER TABLE "rattachement" RENAME COLUMN "deleted_by" TO "supprime_par"')
    op.execute('ALTER TABLE "rattachement" DROP CONSTRAINT IF EXISTS "ck_rattachement_status"')
    op.execute("""UPDATE "rattachement" SET "status" = CASE "status"
                    WHEN 'new' THEN 'nouveau' WHEN 'todo' THEN 'a_faire' WHEN 'doing' THEN 'en_cours'
                    WHEN 'waiting' THEN 'attente' WHEN 'processed' THEN 'traite' ELSE "status" END""")
    op.execute('ALTER TABLE "rattachement" RENAME COLUMN "status" TO "statut"')
    op.execute("""ALTER TABLE "rattachement" ADD CONSTRAINT "ck_rattachement_statut"
                  CHECK ("statut" IN ('nouveau', 'a_faire', 'en_cours', 'attente', 'traite'))""")
    op.execute('DROP INDEX IF EXISTS "ix_acces_stands_in_for"')
    op.execute('ALTER TABLE "acces" DROP CONSTRAINT IF EXISTS "fk_acces_stands_in_for"')
    op.execute('ALTER TABLE "acces" DROP COLUMN "stands_in_for"')
    op.execute('ALTER TABLE "acces" DROP COLUMN "options"')
    for t in ("marker_personal", "marker_collective", "marker", "read_state"):
        op.execute('DROP TABLE IF EXISTS "%s"' % t)
