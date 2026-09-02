/* INDEX DU CDC — FICHIER GÉNÉRÉ, ne pas éditer à la main.
   Produit par outils/gen-cdc-index.py depuis le CDC réel (RM2881). Le retaper
   garantirait qu'il diverge ; le générer garantit que la page « CDC » du POC dit
   ce que dit le registre, et rien d'autre.

   Généré le 2026-09-02 — 120 décisions, 45 questions, 17 chapitres. */
(function (ABX) {
  "use strict";
  ABX.CDC = {
  "genere": "2026-09-02",
  "ticket": "RM2881",
  "depot": "iprospective/tools/atombox-webmail-core",
  "chapitres": [
    {
      "n": "00",
      "fichier": "cdc-rm2881-00-sommaire.md",
      "titre": "CDC AtomBox"
    },
    {
      "n": "01",
      "fichier": "cdc-rm2881-01-perimetre.md",
      "titre": "01"
    },
    {
      "n": "02",
      "fichier": "cdc-rm2881-02-stockage.md",
      "titre": "02"
    },
    {
      "n": "03",
      "fichier": "cdc-rm2881-03-modele-donnees.md",
      "titre": "03"
    },
    {
      "n": "04",
      "fichier": "cdc-rm2881-04-archivage.md",
      "titre": "04"
    },
    {
      "n": "05",
      "fichier": "cdc-rm2881-05-api.md",
      "titre": "05"
    },
    {
      "n": "06",
      "fichier": "cdc-rm2881-06-flux-mail.md",
      "titre": "06"
    },
    {
      "n": "07",
      "fichier": "cdc-rm2881-07-integrations-cibles.md",
      "titre": "07"
    },
    {
      "n": "08",
      "fichier": "cdc-rm2881-08-dimensionnement.md",
      "titre": "08"
    },
    {
      "n": "09",
      "fichier": "cdc-rm2881-09-comptes-boites-acces.md",
      "titre": "09"
    },
    {
      "n": "10",
      "fichier": "cdc-rm2881-10-phasage.md",
      "titre": "10"
    },
    {
      "n": "11",
      "fichier": "cdc-rm2881-11-jeu-essai.md",
      "titre": "11"
    },
    {
      "n": "12",
      "fichier": "cdc-rm2881-12-navigation.md",
      "titre": "12"
    },
    {
      "n": "13",
      "fichier": "cdc-rm2881-13-emission-delivrabilite.md",
      "titre": "13"
    },
    {
      "n": "90",
      "fichier": "cdc-rm2881-90-decisions.md",
      "titre": "Registre des décisions"
    },
    {
      "n": "91",
      "fichier": "cdc-rm2881-91-vrac.md",
      "titre": "Notes en vrac"
    },
    {
      "n": "99",
      "fichier": "cdc-rm2881-99-questions-ouvertes.md",
      "titre": "Questions ouvertes"
    }
  ],
  "decisions": [
    {
      "id": "D01",
      "objet": "Trois composants : moteur de stockage, API, webmail",
      "etat": "valide"
    },
    {
      "id": "D02",
      "objet": "Indexation sur tags paramétrables, en plus des champs classiques",
      "etat": "valide"
    },
    {
      "id": "D03",
      "objet": "L'API vise l'intégration à un ERP/CRM, typiquement Dolibarr",
      "etat": "valide"
    },
    {
      "id": "D04",
      "objet": "Outil collaboratif : le compte propriétaire est un critère d'index",
      "etat": "valide"
    },
    {
      "id": "D05",
      "objet": "Un fichier par email, compressé en zstd",
      "etat": "valide"
    },
    {
      "id": "D06",
      "objet": "Index en PostgreSQL",
      "etat": "valide"
    },
    {
      "id": "D07",
      "objet": "Le stockage brut ne sert qu'à la lecture",
      "etat": "valide"
    },
    {
      "id": "D08",
      "objet": "Le stockage ignore le ou les comptes propriétaires",
      "etat": "valide"
    },
    {
      "id": "D09",
      "objet": "Arborescence « façon Maildir », un dossier par correspondant",
      "etat": "amendee"
    },
    {
      "id": "D09b",
      "objet": "Tout est piloté par la base ; le stockage peut être en vrac",
      "etat": "valide"
    },
    {
      "id": "D10",
      "objet": "Déduplication du message dès la V1 (multi-destinataires = 1 exemplaire)",
      "etat": "valide"
    },
    {
      "id": "D11",
      "objet": "Détachement + dédoublonnage des pièces jointes",
      "etat": "valide"
    },
    {
      "id": "D12",
      "objet": "Messagerie interne hors SMTP ; message mixte : le MTA ne relaie pas les internes",
      "etat": "valide"
    },
    {
      "id": "D13",
      "objet": "Archivage : 3 zones, index différents, recherche par défaut sur les non traités",
      "etat": "autre"
    },
    {
      "id": "D14",
      "objet": "Clé d'archivage = date de traitement, pas date de réception",
      "etat": "valide"
    },
    {
      "id": "D15",
      "objet": "Distinguer archive-emplacement (geste) et zone froide (mécanique)",
      "etat": "valide"
    },
    {
      "id": "D16",
      "objet": "Tags sur les emails, index performant, regroupement par projet/client/fournisseur",
      "etat": "valide"
    },
    {
      "id": "D17",
      "objet": "Le tag porte sur le message (fait partagé), pour l'interopérabilité entre solutions",
      "etat": "valide"
    },
    {
      "id": "D18",
      "objet": "Catégories de tags (axes) porteuses d'ACL",
      "etat": "valide"
    },
    {
      "id": "D19",
      "objet": "Notion d'application connectée, porteuse de ses axes",
      "etat": "valide"
    },
    {
      "id": "D20",
      "objet": "Deux niveaux : type de connecteur (fonctionnement partagé) et instance",
      "etat": "valide"
    },
    {
      "id": "D21",
      "objet": "Connecteurs livrés pour les applications connues (« plugins » / « conf »)",
      "etat": "valide"
    },
    {
      "id": "D22",
      "objet": "Base de données performante : rapide et légère (≠ « moins de tables »)",
      "etat": "valide"
    },
    {
      "id": "D23",
      "objet": "Audit de dimensionnement sur 100 boîtes × 50 k emails",
      "etat": "valide"
    },
    {
      "id": "D24",
      "objet": "PJ extraites et dédupliquées rapidement + recompression proposée si utile",
      "etat": "valide"
    },
    {
      "id": "D25",
      "objet": "Extraction réversible : message reconstructible à l'octet, DKIM vérifiable",
      "etat": "valide"
    },
    {
      "id": "D26",
      "objet": "Verdicts DKIM/SPF calculés à l'ingestion et stockés en base",
      "etat": "valide"
    },
    {
      "id": "D27",
      "objet": "En-têtes en champ texte + booléen d'alignement + note SpamAssassin",
      "etat": "valide"
    },
    {
      "id": "D28",
      "objet": "Conserver la divergence de verdicts entre deux livraisons",
      "etat": "valide"
    },
    {
      "id": "D29",
      "objet": "Modèle du message consolidé : C09 validée + destinataires, snippet, exploitation",
      "etat": "valide"
    },
    {
      "id": "D30",
      "objet": "sorti_le + motif_sortie retenus — on peut archiver sans traiter",
      "etat": "valide"
    },
    {
      "id": "D31",
      "objet": "Extrait texte brut du message, indexé plein texte",
      "etat": "valide"
    },
    {
      "id": "D32",
      "objet": "PJ en many-to-many : taille et type détecté sur le blob, nom et type déclaré sur la liaison",
      "etat": "valide"
    },
    {
      "id": "D33",
      "objet": "snippet = extrait nettoyé, pas un résumé ni des mots-clés",
      "etat": "valide"
    },
    {
      "id": "D34",
      "objet": "Plein texte intégral, index chaud sur l'actif, archives sur disque lent",
      "etat": "valide"
    },
    {
      "id": "D35",
      "objet": "Le correspondant est une identité à plusieurs adresses",
      "etat": "valide"
    },
    {
      "id": "D36",
      "objet": "Portée de lecture = le rattachement",
      "etat": "valide"
    },
    {
      "id": "D37",
      "objet": "Portée d'une application = N boîtes / domaines rattachés à un identifiant d'API",
      "etat": "valide"
    },
    {
      "id": "D38",
      "objet": "Compte de domaine et compte admin tracé",
      "etat": "valide"
    },
    {
      "id": "D39",
      "objet": "Un alias (contact@, orders@) a sa propre boîte",
      "etat": "valide"
    },
    {
      "id": "D40",
      "objet": "Modèle interne propre + vues SQL compatibles PostfixAdmin",
      "etat": "autre"
    },
    {
      "id": "D41",
      "objet": "Timestamp de lecture sur le rattachement (pas un booléen)",
      "etat": "valide"
    },
    {
      "id": "D42",
      "objet": "AtomBox plus qu'un archiveur : relève IMAP en V1, LMTP en cible",
      "etat": "valide"
    },
    {
      "id": "D43",
      "objet": "uid IMAP par rattachement, uid_validity/uid_next par boîte",
      "etat": "valide"
    },
    {
      "id": "D44",
      "objet": "LMTP et relève IMAP : trajectoire d'ingestion",
      "etat": "valide"
    },
    {
      "id": "D45",
      "objet": "Le volet livraison (LMTP, double livraison, module Dovecot) passe en V2",
      "etat": "valide"
    },
    {
      "id": "D46",
      "objet": "Démon d'ingestion IMAP en V1, sur tous les comptes administrés",
      "etat": "valide"
    },
    {
      "id": "D47",
      "objet": "Dossiers de boîte : défauts protégés + alias de dossier",
      "etat": "valide"
    },
    {
      "id": "D48",
      "objet": "matnat : démon temps réel en remplacement d'imapsync",
      "etat": "valide"
    },
    {
      "id": "D49",
      "objet": "Pilote sur iprospective.eu, domaine inutilisé",
      "etat": "valide"
    },
    {
      "id": "D50",
      "objet": "iprospective.fr en lecture seule IMAP, sans toucher au LMTP",
      "etat": "valide"
    },
    {
      "id": "D51",
      "objet": "Dossiers spéciaux = vues ; dossiers utilisateur = vraies entités",
      "etat": "valide"
    },
    {
      "id": "D52",
      "objet": "Pilote en deux étapes : .eu pour cadrer, puis .fr en recette",
      "etat": "valide"
    },
    {
      "id": "D53",
      "objet": "Jeu d'essai du pilote : alias, boîtes perso et communes, 17 cas",
      "etat": "valide"
    },
    {
      "id": "D54",
      "objet": "Pas de copie : activite + journal tracent le travail d'un compte",
      "etat": "valide"
    },
    {
      "id": "D55",
      "objet": "Indexation des fils de discussion",
      "etat": "valide"
    },
    {
      "id": "D56",
      "objet": "Journal d'actions partitionné : < 1 an / 1-5 ans / au-delà",
      "etat": "valide"
    },
    {
      "id": "D57",
      "objet": "ACL par email, modifiable et révocable — distincte de la trace",
      "etat": "valide"
    },
    {
      "id": "D58",
      "objet": "Partager = accorder un accès ; transfert interne par référence",
      "etat": "valide"
    },
    {
      "id": "D59",
      "objet": "Les lectures ne sont pas purgées",
      "etat": "valide"
    },
    {
      "id": "D60",
      "objet": "Accès partagés indépendants ; le *un-share* est un geste de haut niveau, rare",
      "etat": "valide"
    },
    {
      "id": "D61",
      "objet": "Un compte est une identité interne (mathieu.m, fred, …)",
      "etat": "valide"
    },
    {
      "id": "D62",
      "objet": "Mono-organisation, mais structuré pour basculer en multi",
      "etat": "valide"
    },
    {
      "id": "D63",
      "objet": "Auth par token (SSO possible, credentials → token temporaire)",
      "etat": "valide"
    },
    {
      "id": "D64",
      "objet": "Principe d'identité : ce que l'expéditeur a envoyé",
      "etat": "valide"
    },
    {
      "id": "D65",
      "objet": "Identité ≠ déduplication du contenu : blob_corps partagé comme les PJ",
      "etat": "autre"
    },
    {
      "id": "D66",
      "objet": "Messages encapsulés (message/rfc822) traités comme des messages, donc dédupliqués",
      "etat": "valide"
    },
    {
      "id": "D67",
      "objet": "Le lien vers la source est une relation en base, jamais un marqueur dans le message",
      "etat": "valide"
    },
    {
      "id": "D68",
      "objet": "AtomBox administre domaines, boîtes et alias — mais pas au pilote",
      "etat": "valide"
    },
    {
      "id": "D69",
      "objet": "PJ décodées (−33 %), compression conditionnelle, recompression assumée",
      "etat": "valide"
    },
    {
      "id": "D70",
      "objet": "Recompression sur proposition ou à la demande — jamais automatique",
      "etat": "valide"
    },
    {
      "id": "D71",
      "objet": "File de quarantaine spam globale, libérable par un rôle seulement",
      "etat": "valide"
    },
    {
      "id": "D72",
      "objet": "Rôles administrateurs par utilisateur",
      "etat": "valide"
    },
    {
      "id": "D73",
      "objet": "Système de plugins à hooks",
      "etat": "valide"
    },
    {
      "id": "D74",
      "objet": "Filtres AtomBox remplaçant Sieve — en V1",
      "etat": "valide"
    },
    {
      "id": "D75",
      "objet": "Dossiers virtuels = filtres sauvegardés (les tags n'en sont qu'un critère)",
      "etat": "valide"
    },
    {
      "id": "D76",
      "objet": "Les cas de navigation se ramènent à un axe + ses valeurs (six familles)",
      "etat": "valide"
    },
    {
      "id": "D77",
      "objet": "L'arborescence des dossiers virtuels est engendrée, jamais créée à la main",
      "etat": "valide"
    },
    {
      "id": "D78",
      "objet": "Compteurs par requête groupée, matérialisation seulement si mesurée",
      "etat": "valide"
    },
    {
      "id": "D79",
      "objet": "Premier POC = interface du webmail, pour en déduire le dessous",
      "etat": "valide"
    },
    {
      "id": "D80",
      "objet": "POC statique, sur fixtures — mais à la bonne cardinalité",
      "etat": "valide"
    },
    {
      "id": "D81",
      "objet": "La liaison PJ porte ordre, transfer_encoding, disposition, parametres",
      "etat": "propose"
    },
    {
      "id": "D82",
      "objet": "piece_jointe porte blob_origine + recompresse_le",
      "etat": "propose"
    },
    {
      "id": "D83",
      "objet": "Index (pj_id, message_id) : la déduplication se parcourt dans les deux sens",
      "etat": "propose"
    },
    {
      "id": "D84",
      "objet": "Le tag porte la référence externe de l'application",
      "etat": "propose"
    },
    {
      "id": "D85",
      "objet": "Table correspondant_externe : le pont identité ↔ tiers de chaque application",
      "etat": "propose"
    },
    {
      "id": "D86",
      "objet": "Table evenement_sortant : file rejouable vers les applications connectées",
      "etat": "propose"
    },
    {
      "id": "D87",
      "objet": "La déduplication impose un ramasse-miettes : rien ne s'efface en cascade",
      "etat": "propose"
    },
    {
      "id": "D88",
      "objet": "Le rattachement conserve le dossier d'origine et la date de déplacement",
      "etat": "propose"
    },
    {
      "id": "D89",
      "objet": "Un brouillon est un message marqué, pas une seconde table",
      "etat": "propose"
    },
    {
      "id": "D90",
      "objet": "Le sens (reçu / envoyé) est une colonne du rattachement, jamais une déduction",
      "etat": "propose"
    },
    {
      "id": "D91",
      "objet": "L'apprentissage anti-spam est par utilisateur et bidirectionnel",
      "etat": "propose"
    },
    {
      "id": "D92",
      "objet": "AtomBox est une suite collaborative centrée sur la messagerie, pas seulement un webmail",
      "etat": "valide"
    },
    {
      "id": "D93",
      "objet": "Statut de traitement ordonné sur le rattachement — surtout pas un tag",
      "etat": "propose"
    },
    {
      "id": "D94",
      "objet": "Tâches, contacts, fichiers, calendrier : des capacités enfichables (natif ou connecteur)",
      "etat": "valide"
    },
    {
      "id": "D95",
      "objet": "Le natif est le produit vendu seul ; V1 avec des outils légers",
      "etat": "amendee"
    },
    {
      "id": "D95b",
      "objet": "Les composants internes (contacts, tâches, cloud, CRM) sont une cible de V3",
      "etat": "valide"
    },
    {
      "id": "D97",
      "objet": "Les canaux non-mail (SMS, WhatsApp, téléphonie) sont une cible de V4",
      "etat": "valide"
    },
    {
      "id": "D98",
      "objet": "Trois précautions de schéma dès la V1 pour ne pas s'interdire la V4",
      "etat": "propose"
    },
    {
      "id": "D99",
      "objet": "Cycle de vie de l'émission : une ligne d'envoi par destinataire, envoi programmé, DSN corrélé",
      "etat": "valide"
    },
    {
      "id": "D100",
      "objet": "Retours DMARC (rapports agrégés et forensiques) ingérés et exploités pour la délivrabilité",
      "etat": "valide"
    },
    {
      "id": "D101",
      "objet": "Note interne attachée au message, invisible du correspondant",
      "etat": "valide"
    },
    {
      "id": "D102",
      "objet": "Identité d'expédition : nom affiché, signature, réponses types — distincte de la boîte",
      "etat": "valide"
    },
    {
      "id": "D103",
      "objet": "reveil_le et echeance_le sur le rattachement : reporter, relancer, alerter",
      "etat": "valide"
    },
    {
      "id": "D104",
      "objet": "Rétention et gel par type de contenu et par boîte ; le gel prime sur toute purge",
      "etat": "valide"
    },
    {
      "id": "D105",
      "objet": "Affichage sûr : HTML assaini, images externes bloquées, bannière expéditeur externe, aucun MDN",
      "etat": "valide"
    },
    {
      "id": "D106",
      "objet": "Paramétrage en cascade instance → domaine → compte → boîte, surchargeable et verrouillable",
      "etat": "valide"
    },
    {
      "id": "D107",
      "objet": "Import d'historique (IMAP, mbox, PST) : une fonction de V1, pas un script d'exploitation",
      "etat": "valide"
    },
    {
      "id": "D108",
      "objet": "SDK et composants embarquables : l'ERP affiche AtomBox, il ne fait pas que l'appeler",
      "etat": "valide"
    },
    {
      "id": "D109",
      "objet": "Complétion des destinataires depuis l'historique — le carnet gratuit de la V1",
      "etat": "valide"
    },
    {
      "id": "D110",
      "objet": "Impression et export PDF d'un message ou d'un fil",
      "etat": "valide"
    },
    {
      "id": "D111",
      "objet": "Pièce jointe par lien : dépôt chez un fournisseur de fichiers, lien de téléchargement",
      "etat": "valide"
    },
    {
      "id": "D112",
      "objet": "Mobile : l'interface responsive d'abord, l'accès IMAP en repli assumé",
      "etat": "valide"
    },
    {
      "id": "D113",
      "objet": "Absence et réponse automatique, avec renvoi sur un collègue — porté par le moteur de filtres",
      "etat": "valide"
    },
    {
      "id": "D114",
      "objet": "L'émission passe par le relais du client en V1 ; le sort des envois vient des DSN",
      "etat": "valide"
    },
    {
      "id": "D115",
      "objet": "Les rapports DMARC arrivent dans une boîte de collecte ingérée comme les autres, dépouillée par une tâche interne",
      "etat": "valide"
    },
    {
      "id": "D116",
      "objet": "Boîte partagée : le From est celui de la boîte, avec un « au nom de » optionnel",
      "etat": "valide"
    },
    {
      "id": "D117",
      "objet": "Est verrouillable ce qui protège l'entreprise ; jamais le confort du poste de travail",
      "etat": "valide"
    },
    {
      "id": "D118",
      "objet": "Supprimer, c'est détacher ; le message orphelin tombe en déchetterie, restaurable",
      "etat": "valide"
    },
    {
      "id": "D25",
      "objet": "Extraction réversible (exigence)",
      "etat": "autre"
    }
  ],
  "questions": [
    {
      "id": "Q01",
      "objet": "Critère d'identité pour la déduplication",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q02",
      "objet": "Correspondant : adresse ou identité ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q03",
      "objet": "Portée de lecture entre comptes",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q20",
      "objet": "Portée des applications",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q21",
      "objet": "Accès d'administration",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q22",
      "objet": "Que voit un ancien membre après révocation ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q27",
      "objet": "La trace donne-t-elle un droit de lecture ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q28",
      "objet": "Rétention des traces de lecture",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q29",
      "objet": "Partage transitif",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q30",
      "objet": "Que devient un transfert dont l'original a été purgé ?",
      "bloque": "D58, RGPD",
      "urgence": "moyenne"
    },
    {
      "id": "Q23",
      "objet": "Source de vérité des domaines/alias ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q26",
      "objet": "Depuis quelle identité répond-on à un message de boîte commune ?",
      "bloque": "fils, révocation, suivi d'équipe",
      "urgence": "haute"
    },
    {
      "id": "Q24",
      "objet": "Quel accès IMAP à terme : aucun, module Dovecot, ou IMAP minimal ?",
      "bloque": "adoption, clients existants",
      "urgence": "haute"
    },
    {
      "id": "Q25",
      "objet": "Dossiers arbitraires : dossiers ou tags ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q04",
      "objet": "Plein texte : périmètre ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q05",
      "objet": "Gouvernance des axes : qui les crée, qui les nomme ?",
      "bloque": "interopérabilité (D17)",
      "urgence": "haute"
    },
    {
      "id": "Q06",
      "objet": "Granularité des partitions, seuil d'archivage, index abandonnés",
      "bloque": "DDL de l'archivage",
      "urgence": "basse"
    },
    {
      "id": "Q07",
      "objet": "Style d'API (REST vs point d'entrée unique)",
      "bloque": "surface d'API",
      "urgence": "haute"
    },
    {
      "id": "Q08",
      "objet": "L'API porte-t-elle l'envoi, ou seulement la consultation ?",
      "bloque": "surface d'API",
      "urgence": "haute"
    },
    {
      "id": "Q09",
      "objet": "Un email sorti de la file peut-il y revenir (rouvert, désarchivé) ?",
      "bloque": "partitionnement",
      "urgence": "basse"
    },
    {
      "id": "Q10",
      "objet": "Archiver sans traiter ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q11",
      "objet": "Quel périmètre d'intégration en V1 ?",
      "bloque": "surface d'API, calendrier",
      "urgence": "moyenne"
    },
    {
      "id": "Q12",
      "objet": "Tag sur message ou rattachement ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q13",
      "objet": "Les tags respectent-ils la portée de lecture ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q14",
      "objet": "Mono ou multi-organisation ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q15",
      "objet": "Le nom du produit",
      "bloque": "image, communication, dépôt",
      "urgence": "basse"
    },
    {
      "id": "Q18",
      "objet": "Types d'identité",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q19",
      "objet": "Le compte est-il une identité ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q16",
      "objet": "Extraction des PJ réversible ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q17",
      "objet": "Verdicts divergents",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q31",
      "objet": "Le contexte métier est-il appelé à chaque affichage, ou mis en cache ?",
      "bloque": "surface d'API, ergonomie",
      "urgence": "haute"
    },
    {
      "id": "Q32",
      "objet": "Recompresse-t-on un blob dont un porteur est encore revérifiable ?",
      "bloque": "D70, D82",
      "urgence": "moyenne"
    },
    {
      "id": "Q33",
      "objet": "L'hypothèse de 100 ko par message tient-elle sur un corpus réel ?",
      "bloque": "dimensionnement (ch. 08)",
      "urgence": "moyenne"
    },
    {
      "id": "Q34",
      "objet": "Peut-on retirer à la main un tag posé par un connecteur ?",
      "bloque": "D17, D19, D21",
      "urgence": "moyenne"
    },
    {
      "id": "Q35",
      "objet": "Le statut de traitement est-il par compte ou par boîte ?",
      "bloque": "D93, boîtes communes",
      "urgence": "haute"
    },
    {
      "id": "Q36",
      "objet": "Les états du workflow sont-ils figés ou paramétrables ?",
      "bloque": "D93, interface",
      "urgence": "moyenne"
    },
    {
      "id": "Q37",
      "objet": "Périmètre fonctionnel de la suite en V1",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q38",
      "objet": "Sépare-t-on message et message_email dès la V1 ?",
      "bloque": "D98, chemin le plus chaud",
      "urgence": "haute"
    },
    {
      "id": "Q39",
      "objet": "Périmètre fonctionnel des composants V3, CRM compris",
      "bloque": "chiffrage V3",
      "urgence": "basse"
    },
    {
      "id": "Q40",
      "objet": "Qui émet réellement : relais du client ou file de sortie ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q41",
      "objet": "D'où viennent les rapports DMARC ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q42",
      "objet": "From d'une boîte partagée",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q43",
      "objet": "Jusqu'où verrouiller un réglage ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q44",
      "objet": "La purge efface-t-elle l'octet ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q45",
      "objet": "Que voit un administrateur dans la déchetterie : le contenu, ou les métadonnées ?",
      "bloque": "D118, D54",
      "urgence": "haute"
    }
  ]
};
})(window.ABX = window.ABX || {});
