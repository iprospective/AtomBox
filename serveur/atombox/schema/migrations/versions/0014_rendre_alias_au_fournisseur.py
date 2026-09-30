"""`alias_imap` appartient au FOURNISSEUR — le renommer a fait naître un dossier fantôme (D043).

Revision ID: 0014
Revises: 0013

CE QUI S'EST PASSÉ, une heure après la mise en service. La boîte avait, chez son fournisseur, un
dossier « Archives ». La migration 0012 l'a ADOPTÉ comme boîte d'état — c'était juste — mais elle a
aussi réécrit son `alias_imap` en « Archive », pour que ce soit le nom servi en IMAP. Or

    `alias_imap` est le nom du dossier CHEZ LE FOURNISSEUR (D043, D140b),

et c'est par lui que la relève retrouve ses dossiers. Ne trouvant plus « Archives », le démon
d'ingestion a fait ce qu'il doit faire : il a créé le dossier manquant. Résultat, deux dossiers
« Archives » dans la même boîte — l'un qui est la boîte d'état, l'autre vide — et l'utilisateur
devant deux dossiers pour une seule idée.

LA CONFUSION DE FOND, et elle valait d'être nommée : j'ai pris un champ pour deux choses. Le nom
CHEZ LE FOURNISSEUR et le nom QU'ON SERT sont indépendants — le premier est une donnée qu'on
reçoit, le second un choix qu'on fait. Depuis ce correctif, le nom servi est CANONIQUE et déduit de
l'état (`services/mailbox.py :: nom_servi`) : `Processed`, `Archive`, `Trash`, `Junk`, les mêmes
d'une boîte à l'autre, en ASCII, et indépendants de tout fournisseur.

CE QUE CETTE MIGRATION RÉPARE :

  1. l'alias du fournisseur est RENDU à la boîte d'état qui l'avait perdu — le fantôme le porte,
     c'est lui qui nous dit le vrai nom ;
  2. les rattachements du fantôme (il n'en avait aucun ici, mais ça ne se suppose pas) rejoignent
     la boîte d'état, avec un UID pris dans celle-ci ;
  3. le fantôme disparaît.
"""
from alembic import op
from atombox.journal import journal
from atombox.services.mailbox import ETATS

log = journal("schema")

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    cnx = op.get_bind()
    repares, deplaces = 0, 0
    for etat, (_nom, servi, _special, alias) in ETATS.items():
        liste = ", ".join("'%s'" % a.replace("'", "''") for a in alias)
        # LE FANTÔME EST LA SOURCE DE VÉRITÉ pour le nom du fournisseur : c'est le démon qui l'a
        # créé, en recopiant ce que le serveur distant lui a annoncé.
        fantomes = cnx.exec_driver_sql("""
SELECT f."dossier_id"::text, f."boite_id"::text, f."alias_imap", e."dossier_id"::text
  FROM "dossier" f
  JOIN "dossier" e ON e."boite_id" = f."boite_id" AND e."exit_reason" = '%s'
 WHERE f."exit_reason" IS NULL
   AND upper(split_part(COALESCE(f."alias_imap", f."nom"), '/', -1)) IN (%s)
""" % (etat, liste)).fetchall()
        for fantome_id, boite_id, alias_vrai, etat_id in fantomes:
            # 1. rendre l'alias du fournisseur à la boîte d'état. On efface d'abord celui du
            #    fantôme : `alias_imap` est unique par boîte, et les deux le porteraient un instant.
            op.execute("""UPDATE "dossier" SET "alias_imap" = NULL WHERE "dossier_id" = '%s'""" % fantome_id)
            op.execute("""UPDATE "dossier" SET "alias_imap" = '%s' WHERE "dossier_id" = '%s'"""
                       % (alias_vrai.replace("'", "''"), etat_id))
            # 2. les rattachements du fantôme rejoignent la boîte d'état, avec un UID de CELLE-CI
            op.execute("""
WITH deja AS (SELECT COALESCE(max("uid_servi"), 0) AS maxi FROM "rattachement" WHERE "dossier_id" = '%(vers)s'),
     bouge AS (SELECT r."comm_id", r."boite_id",
                      deja.maxi + row_number() OVER (ORDER BY c."date_recue", r."comm_id") AS n
                 FROM "rattachement" r JOIN "comm" c ON c."comm_id" = r."comm_id", deja
                WHERE r."dossier_id" = '%(depuis)s')
UPDATE "rattachement" r SET "dossier_id" = '%(vers)s', "uid_servi" = bouge.n, "exit_reason" = '%(etat)s'
  FROM bouge WHERE bouge."comm_id" = r."comm_id" AND bouge."boite_id" = r."boite_id"
""" % {"vers": etat_id, "depuis": fantome_id, "etat": etat})
            n = cnx.exec_driver_sql("""SELECT count(*) FROM "rattachement" WHERE "dossier_id" = '%s'"""
                                    % fantome_id).scalar()
            if n:
                log.warning("le dossier fantôme %s garde %d rattachement(s) — non supprimé", fantome_id, n)
                continue
            op.execute("""DELETE FROM "dossier" WHERE "dossier_id" = '%s'""" % fantome_id)
            repares += 1
        # le compteur de la boîte d'état suit ce qu'elle contient désormais
        op.execute("""
UPDATE "dossier" d SET "uid_servi_suivant" = GREATEST(COALESCE(d."uid_servi_suivant", 1),
    COALESCE((SELECT max(r."uid_servi") FROM "rattachement" r WHERE r."dossier_id" = d."dossier_id"), 0) + 1)
 WHERE d."exit_reason" = '%s'""" % etat)

    if repares:
        log.info("%d dossier(s) fantôme(s) absorbé(s) ; l'alias du fournisseur est rendu (D043)", repares)
    else:
        log.info("aucun dossier fantôme — l'alias du fournisseur n'avait pas été perdu ici")

    reste = cnx.exec_driver_sql("""
SELECT count(*) FROM (SELECT "boite_id", upper(COALESCE("alias_imap", "nom")) a, count(*)
                        FROM "dossier" GROUP BY 1, 2 HAVING count(*) > 1) x""").scalar()
    if reste:
        log.warning("%d couple(s) (boîte, alias) en double subsistent — à regarder à la main", reste)


def downgrade():
    # Rien à défaire : cette migration REND une donnée que 0012 avait écrasée, et absorbe un dossier
    # créé par erreur. Recréer le fantôme n'aurait aucun sens, et remettre l'alias faux ferait
    # renaître le défaut au prochain passage du démon.
    log.info("0014 ne se défait pas : elle a rendu l'alias du fournisseur, il n'y a rien à reprendre")
