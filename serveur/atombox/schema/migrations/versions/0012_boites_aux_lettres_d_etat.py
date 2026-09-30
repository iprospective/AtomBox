"""D183 — les quatre boîtes aux lettres d'état sont des LIGNES de `dossier`, servies en IMAP.

Revision ID: 0012
Revises: 0011

POURQUOI DES LIGNES ET NON DES VUES, et pourquoi ce n'était pas un choix :

    RFC 3501 § 2.3.1.1 — « Unique identifiers are assigned in a strictly ascending fashion in the
    mailbox; as each message is added to the mailbox it is assigned a higher UID than the
    message(s) which were added previously. »

Avec un compteur unique par boîte, un message reçu il y a six mois (UID 12) qu'on traite aujourd'hui
entrerait dans `Traités` — qui contient déjà 400 à 900 — avec l'UID 12. Un client qui synchronise par
incrément demande `UID FETCH 901:*` : il ne verrait JAMAIS ce message. Chaque boîte aux lettres a
donc son compteur, et `dossier` est la table qui les porte déjà (RM3321).

CE QUE CETTE MIGRATION FAIT, dans l'ordre :

  1. deux colonnes sur `dossier` : `exit_reason` (cette ligne EST la boîte de cet état) et
     `special_use` (l'attribut RFC 6154 que `LIST` annonce) ;
  2. les dossiers existants sont étiquetés : Corbeille → deleted/\\Trash, Indésirables → junk/\\Junk,
     Sent → \\Sent, Drafts → \\Drafts ;
  3. `Processed` et `Archive` sont CRÉÉS pour chaque boîte — ils n'existaient nulle part ;
  4. les rattachements déjà sortis de la file y sont DÉPLACÉS, avec un UID neuf pris dans la boîte
     d'arrivée, et leur dossier d'origine mémorisé (D088) quand c'était un dossier utilisateur.

L'ÉTAPE 4 EST CELLE QUI DEMANDE DE L'ATTENTION. Un UID neuf, et pas l'ancien : c'est la sémantique
IMAP (l'UID appartient à la boîte aux lettres), et c'est aussi la seule façon de garder l'ordre
croissant. Les clients déjà synchronisés verront ces messages quitter INBOX et arriver dans les
nouvelles boîtes — ce qui est exactement ce qui se passe.
"""
from alembic import op
from atombox.journal import journal

log = journal("schema")

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# LES QUATRE BOÎTES D'ÉTAT viennent de `services/mailbox.py` : c'est la même table que le service
# lit pour poser celles qui manquent à une boîte neuve. Deux listes auraient divergé au premier
# alias ajouté — et un alias oublié crée une SECONDE « Archive » à côté de celle du fournisseur.
from atombox.services.mailbox import ETATS

# Ces deux-là n'ont pas d'état à porter : ce sont des dossiers ordinaires, mais leur attribut
# SPECIAL-USE permet au client de savoir où sont les envoyés et les brouillons (RFC 6154).
SPECIAL_SEULS = {"\\Sent": ("SENT", "SENT ITEMS", "ENVOYÉS", "ENVOYES"),
                 "\\Drafts": ("DRAFTS", "BROUILLONS")}


def _en_sql(valeurs):
    return ", ".join("'%s'" % v.replace("'", "''") for v in valeurs)


def upgrade():
    op.execute('ALTER TABLE "dossier" ADD COLUMN "exit_reason" text')
    op.execute('ALTER TABLE "dossier" ADD COLUMN "special_use" text')
    op.execute("""ALTER TABLE "dossier" ADD CONSTRAINT "ck_dossier_exit_reason"
                  CHECK ("exit_reason" IN ('processed', 'archived', 'deleted', 'junk'))""")
    # UNE boîte d'état par boîte aux lettres et par valeur : deux « Corbeille » dans la même boîte
    # rendraient le déplacement non déterministe, et le client verrait ses messages alterner.
    op.execute("""CREATE UNIQUE INDEX "uq_dossier_exit_reason" ON "dossier" ("boite_id", "exit_reason")
                  WHERE "exit_reason" IS NOT NULL""")

    # ── 2. ADOPTER les dossiers du fournisseur qui portent déjà ces états ──────────────────────
    # Sans cette étape, une boîte relevée chez un fournisseur se retrouvait avec SON « Archives » et
    # NOTRE « Archive » côte à côte : deux boîtes pour une idée, et l'utilisateur ne sait pas
    # laquelle regarder. Le `LIMIT 1` protège du cas où deux alias du même état coexistent
    # (« Junk » et « Spam ») : l'index unique n'en accepte qu'un, et on prend le premier.
    for etat, (_nom, servi, special, alias) in ETATS.items():
        op.execute("""UPDATE "dossier" SET "exit_reason" = '%s', "special_use" = %s,
                             "alias_imap" = '%s', "protege" = true
                       WHERE "dossier_id" IN (
                         SELECT DISTINCT ON ("boite_id") "dossier_id" FROM "dossier"
                          WHERE upper(split_part(COALESCE("alias_imap", "nom"), '/', -1)) IN (%s)
                            AND "exit_reason" IS NULL
                          ORDER BY "boite_id", "ordre" NULLS LAST, "nom")"""
                   % (etat, ("'%s'" % special) if special else "NULL", servi, _en_sql(alias)))
    for special, alias in SPECIAL_SEULS.items():
        op.execute("""UPDATE "dossier" SET "special_use" = '%s'
                       WHERE upper(split_part(COALESCE("alias_imap", "nom"), '/', -1)) IN (%s)
                         AND "special_use" IS NULL""" % (special, _en_sql(alias)))

    # ── 3. créer ce qui manque, pour CHAQUE boîte ──────────────────────────────────────────────
    # uuid v7 engendré en SQL : la migration ne peut pas appeler notre uuid7(), et un v4 perdrait
    # l'ordre temporel que D145 attend de tout identifiant. Disposition de la v7 : 48 bits
    # d'horloge en millisecondes, le chiffre de version `7`, le variant `8`, le reste au hasard —
    # et le découpage 8-4-4-4-12 écrit à la main, parce qu'un uuid mal groupé passe ou ne passe pas
    # selon la tolérance de l'analyseur, et qu'on ne construit pas une clé sur une tolérance.
    for etat, (nom, servi, special, _alias) in ETATS.items():
        op.execute("""
INSERT INTO "dossier" ("dossier_id", "boite_id", "nom", "alias_imap", "protege", "exit_reason",
                       "special_use", "uid_validity_servie", "uid_servi_suivant")
SELECT (substr(x.ms, 1, 8) || '-' || substr(x.ms, 9, 4)
        || '-7' || substr(x.alea, 1, 3)
        || '-8' || substr(x.alea, 4, 3)
        || '-' || substr(x.alea, 7, 12))::uuid,
       b."boite_id", '%(nom)s', '%(servi)s', true, '%(etat)s', %(special)s,
       EXTRACT(EPOCH FROM now())::bigint, 1
  FROM "boite" b
  CROSS JOIN LATERAL (
    SELECT lpad(to_hex((EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint), 12, '0') AS ms,
           md5(random()::text || b."boite_id"::text || '%(etat)s') AS alea) x
 WHERE NOT EXISTS (SELECT 1 FROM "dossier" d
                    WHERE d."boite_id" = b."boite_id" AND d."exit_reason" = '%(etat)s')
""" % {"nom": nom, "servi": servi, "etat": etat,
       "special": ("'%s'" % special) if special else "NULL"})

    # ── 4. déplacer les messages déjà sortis de la file ────────────────────────────────────────
    # `dossier_origine_id` d'abord, et seulement s'il est vide : un message rangé dans « Devis 2026 »
    # doit pouvoir y revenir (D088). L'écraser ici, c'est le déclasser pour de bon.
    op.execute("""
UPDATE "rattachement" r SET "dossier_origine_id" = r."dossier_id"
  FROM "dossier" d
 WHERE d."dossier_id" = r."dossier_id" AND r."exit_reason" IS NOT NULL
   AND r."dossier_origine_id" IS NULL AND d."exit_reason" IS DISTINCT FROM r."exit_reason"
""")
    # puis l'affectation, avec un UID NEUF dans la boîte d'arrivée, attribué dans l'ordre d'arrivée.
    #
    # `deja.maxi` N'EST PAS UNE PRÉCAUTION, C'EST LA CORRECTION D'UN DÉFAUT : `Corbeille` et
    # `Indésirables` EXISTENT déjà et contiennent déjà des messages, donc des UID. Repartir de 1
    # heurtait `uq_rattachement_uid_servi` dès la première vraie base — et un UID réutilisé ferait
    # lire au client un message pour un autre. Les UID neufs commencent APRÈS le plus grand présent,
    # et ne le réutilisent jamais (Q024).
    op.execute("""
WITH deja AS (
  SELECT d."dossier_id", COALESCE(max(r."uid_servi"), 0) AS maxi
    FROM "dossier" d LEFT JOIN "rattachement" r ON r."dossier_id" = d."dossier_id"
   WHERE d."exit_reason" IS NOT NULL
   GROUP BY d."dossier_id"
), cible AS (
  SELECT r."comm_id", r."boite_id", d."dossier_id" AS "vers",
         deja.maxi + row_number() OVER (PARTITION BY d."dossier_id"
                                        ORDER BY c."date_recue", r."comm_id") AS n
    FROM "rattachement" r
    JOIN "comm" c ON c."comm_id" = r."comm_id"
    JOIN "dossier" d ON d."boite_id" = r."boite_id" AND d."exit_reason" = r."exit_reason"
    JOIN deja ON deja."dossier_id" = d."dossier_id"
   WHERE r."exit_reason" IS NOT NULL AND r."dossier_id" IS DISTINCT FROM d."dossier_id"
)
UPDATE "rattachement" r SET "dossier_id" = cible."vers", "uid_servi" = cible.n
  FROM cible WHERE cible."comm_id" = r."comm_id" AND cible."boite_id" = r."boite_id"
""")
    op.execute("""
UPDATE "dossier" d SET "uid_servi_suivant" =
  COALESCE((SELECT max(r."uid_servi") FROM "rattachement" r WHERE r."dossier_id" = d."dossier_id"), 0) + 1
 WHERE d."exit_reason" IS NOT NULL
""")

    # ── 5. UN MESSAGE SANS UID EST INVISIBLE EN IMAP ───────────────────────────────────────────
    # La vue ne sert que les rattachements qui portent un `uid_servi` : sans lui, le message existe
    # en base, s'affiche dans le webmail, et n'apparaît chez aucun client. La migration 0010 en a
    # donné un à tout l'existant, mais une ligne créée depuis par un chemin qui l'oublie resterait
    # muette pour toujours. On répare, une fois, pour toutes les boîtes aux lettres.
    op.execute("""
WITH manquants AS (
  SELECT r."comm_id", r."boite_id", r."dossier_id",
         COALESCE((SELECT max(r2."uid_servi") FROM "rattachement" r2
                    WHERE r2."dossier_id" = r."dossier_id"), 0)
         + row_number() OVER (PARTITION BY r."dossier_id" ORDER BY c."date_recue", r."comm_id") AS n
    FROM "rattachement" r JOIN "comm" c ON c."comm_id" = r."comm_id"
   WHERE r."uid_servi" IS NULL AND r."dossier_id" IS NOT NULL
)
UPDATE "rattachement" r SET "uid_servi" = manquants.n
  FROM manquants
 WHERE manquants."comm_id" = r."comm_id" AND manquants."boite_id" = r."boite_id"
""")
    op.execute("""
UPDATE "dossier" d SET "uid_servi_suivant" = GREATEST(
    COALESCE(d."uid_servi_suivant", 1),
    COALESCE((SELECT max(r."uid_servi") FROM "rattachement" r WHERE r."dossier_id" = d."dossier_id"), 0) + 1)
""")

    cnx = op.get_bind()
    muets = cnx.exec_driver_sql("""SELECT count(*) FROM "rattachement"
                                    WHERE "uid_servi" IS NULL AND "dossier_id" IS NOT NULL""").scalar()
    if muets:
        log.warning("%d rattachement(s) sans uid_servi : ils n'apparaîtront chez aucun client IMAP", muets)
    incoherents = cnx.exec_driver_sql("""
SELECT count(*) FROM "rattachement" r LEFT JOIN "dossier" d ON d."dossier_id" = r."dossier_id"
 WHERE r."exit_reason" IS DISTINCT FROM d."exit_reason" """).scalar()
    if incoherents:
        log.warning("%d rattachement(s) dont l'état et la boîte aux lettres ne concordent pas — "
                    "l'invariant de D183 est violé, un test devrait le voir", incoherents)
    else:
        log.info("boîtes aux lettres d'état en place ; état et contenant concordent (D183)")


def downgrade():
    # Les messages reviennent dans leur dossier d'origine, ou dans l'INBOX à défaut : ils ne peuvent
    # pas rester dans un dossier qu'on supprime. Leur `exit_reason` ne bouge pas — c'est la vérité,
    # et elle survivait très bien sans ces boîtes (migration 0011).
    # UN UID NEUF DANS LA BOÎTE D'ARRIVÉE, ici aussi. Le retour déplace des messages vers l'INBOX
    # ou leur dossier d'origine, qui contiennent déjà des UID : réutiliser les leurs heurte
    # `uq_rattachement_uid_servi`. Le défaut s'est produit au premier essai du retour, sur des
    # données réelles — un aller qui marche ne dit rien du retour.
    op.execute("""
WITH vers AS (
  SELECT r."comm_id", r."boite_id",
         COALESCE(r."dossier_origine_id", (
           SELECT d2."dossier_id" FROM "dossier" d2
            WHERE d2."boite_id" = r."boite_id"
              AND upper(COALESCE(d2."alias_imap", d2."nom")) = 'INBOX' LIMIT 1)) AS "cible"
    FROM "rattachement" r JOIN "dossier" d ON d."dossier_id" = r."dossier_id"
   WHERE d."exit_reason" IN ('processed', 'archived')
), deja AS (
  SELECT v."cible", COALESCE(max(r."uid_servi"), 0) AS maxi
    FROM vers v LEFT JOIN "rattachement" r ON r."dossier_id" = v."cible"
   GROUP BY v."cible"
), numerote AS (
  SELECT v."comm_id", v."boite_id", v."cible",
         deja.maxi + row_number() OVER (PARTITION BY v."cible" ORDER BY v."comm_id") AS n
    FROM vers v JOIN deja ON deja."cible" = v."cible"
)
UPDATE "rattachement" r SET "dossier_id" = numerote."cible", "uid_servi" = numerote.n
  FROM numerote
 WHERE numerote."comm_id" = r."comm_id" AND numerote."boite_id" = r."boite_id"
""")
    op.execute("""
UPDATE "dossier" d SET "uid_servi_suivant" =
  COALESCE((SELECT max(r."uid_servi") FROM "rattachement" r WHERE r."dossier_id" = d."dossier_id"), 0) + 1
 WHERE EXISTS (SELECT 1 FROM "rattachement" r WHERE r."dossier_id" = d."dossier_id")
""")
    op.execute("""DELETE FROM "dossier" WHERE "exit_reason" IN ('processed', 'archived')
                   AND NOT EXISTS (SELECT 1 FROM "rattachement" r WHERE r."dossier_id" = "dossier"."dossier_id")""")
    op.execute('DROP INDEX IF EXISTS "uq_dossier_exit_reason"')
    op.execute('ALTER TABLE "dossier" DROP CONSTRAINT IF EXISTS "ck_dossier_exit_reason"')
    op.execute('ALTER TABLE "dossier" DROP COLUMN "exit_reason"')
    op.execute('ALTER TABLE "dossier" DROP COLUMN "special_use"')
