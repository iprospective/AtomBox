/* INDEX DU CDC — FICHIER GÉNÉRÉ, ne pas éditer à la main.
   Produit par outils/gen-cdc-index.py depuis le CDC réel (RM2881). Le retaper
   garantirait qu'il diverge ; le générer garantit que la page « CDC » du POC dit
   ce que dit le registre, et rien d'autre.

   Généré le 2026-09-03 — 142 décisions, 55 questions, 20 chapitres. */
(function (ABX) {
  "use strict";
  ABX.CDC = {
  "genere": "2026-09-03",
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
      "n": "14",
      "fichier": "cdc-rm2881-14-sieve-existant.md",
      "titre": "14"
    },
    {
      "n": "15",
      "fichier": "cdc-rm2881-15-audit-performance.md",
      "titre": "15"
    },
    {
      "n": "16",
      "fichier": "cdc-rm2881-16-dictionnaire.md",
      "titre": "16"
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
      "id": "D96",
      "objet": "Le renommage d'une pièce jointe porte sur la liaison, jamais sur le blob",
      "etat": "propose"
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
      "id": "D119",
      "objet": "Savoir sans émettre : retour d'enveloppe unique (VERP), journal du MTA, NOTIFY",
      "etat": "propose"
    },
    {
      "id": "D120",
      "objet": "Tout renvoi réécrit l'enveloppe (SRS), sans quoi il casse SPF",
      "etat": "propose"
    },
    {
      "id": "D121",
      "objet": "Déchetterie : métadonnées seules, restauration vers l'origine, 30 jours réglables",
      "etat": "valide"
    },
    {
      "id": "D122",
      "objet": "Groupes de discussion internes par service — du chat, pas du courrier",
      "etat": "valide"
    },
    {
      "id": "D123",
      "objet": "Le message de groupe vit en base, jamais dans le magasin d'octets",
      "etat": "valide"
    },
    {
      "id": "D124",
      "objet": "Le groupe est une boîte ; un seul rattachement, et une position de lecture par membre",
      "etat": "propose"
    },
    {
      "id": "D125",
      "objet": "Le chat rend le temps réel obligatoire — et Q38 devient un prérequis",
      "etat": "propose"
    },
    {
      "id": "D126",
      "objet": "Le nom affiché n'est pas une identité : From/To normalisés sur le carnet",
      "etat": "valide"
    },
    {
      "id": "D127",
      "objet": "Moteur d'analyse par indices : score *et* détail des règles, stockés et explicables",
      "etat": "valide"
    },
    {
      "id": "D128",
      "objet": "Catalogue des règles anti-usurpation, par famille et par force de signal",
      "etat": "valide"
    },
    {
      "id": "D129",
      "objet": "La règle que seul AtomBox peut poser : la cohérence avec le contexte métier",
      "etat": "propose"
    },
    {
      "id": "D130",
      "objet": "La nature du message (humain / liste / notification / service) remplace le booléen origine_automatique",
      "etat": "valide"
    },
    {
      "id": "D131",
      "objet": "Répondre à un noreply@ : avertir, réorienter, refuser seulement sur preuve",
      "etat": "valide"
    },
    {
      "id": "D132",
      "objet": "Désabonnement en un clic (List-Unsubscribe), jamais automatique",
      "etat": "propose"
    },
    {
      "id": "D133",
      "objet": "Un dossier par liste, dérivé du List-Id — le premier axe qu'aucune application ne déclare",
      "etat": "valide"
    },
    {
      "id": "D134",
      "objet": "Le courrier personnel est protégé : un dossier personnel par défaut, hors accès administrateur",
      "etat": "valide"
    },
    {
      "id": "D135",
      "objet": "L'ordre des dossiers appartient à l'utilisateur — un réglage, jamais un préfixe dans le nom",
      "etat": "valide"
    },
    {
      "id": "D136",
      "objet": "domaine devient une table, et l'adresse est éclatée en local + domaine_id",
      "etat": "valide"
    },
    {
      "id": "D137",
      "objet": "Trois natures de confiance — vérifiée, validée, calculée — sur l'adresse et sur le domaine",
      "etat": "valide"
    },
    {
      "id": "D138",
      "objet": "Le pivot comm : un tronc polymorphe partitionné par canal, dès la V1",
      "etat": "valide"
    },
    {
      "id": "D139",
      "objet": "Trois motifs, trois gestes : on refuse sur un fait, on met en quarantaine sur une présomption, on alerte sur un indice",
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
      "objet": "L'hypothèse de 100 ko par message",
      "bloque": "—",
      "urgence": "autre"
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
      "objet": "Séparer message et message_email dès la V1 ?",
      "bloque": "—",
      "urgence": "tranchee"
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
      "objet": "Ce qu'un administrateur voit de la déchetterie",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q46",
      "objet": "Les groupes internes sont-ils V1 ou V2 ? Ils ne dépendent pas de LMTP",
      "bloque": "D122, phasage",
      "urgence": "haute"
    },
    {
      "id": "Q47",
      "objet": "Un message de groupe est-il modifiable / supprimable par son auteur ?",
      "bloque": "D122, D54",
      "urgence": "moyenne"
    },
    {
      "id": "Q48",
      "objet": "Un nouveau membre voit-il l'historique du groupe ?",
      "bloque": "D124, acces",
      "urgence": "moyenne"
    },
    {
      "id": "Q49",
      "objet": "Alerter, mettre en quarantaine, ou refuser ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q55",
      "objet": "Quels poids et seuils numériques pour le score de D128 ?",
      "bloque": "D139, calibrage",
      "urgence": "moyenne"
    },
    {
      "id": "Q50",
      "objet": "Une newsletter part-elle dans un dossier engendré ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q54",
      "objet": "Le défi anti-robot est-il au périmètre ?",
      "bloque": "D137",
      "urgence": "autre"
    },
    {
      "id": "Q52",
      "objet": "Que devient une branche engendrée dont la source se tarit (liste éteinte, désabonnement) ?",
      "bloque": "D133, D77",
      "urgence": "moyenne"
    },
    {
      "id": "Q53",
      "objet": "Où va le courrier personnel ?",
      "bloque": "—",
      "urgence": "tranchee"
    },
    {
      "id": "Q51",
      "objet": "Le POST de désabonnement sortant est-il acceptable, et sous quelles restrictions ?",
      "bloque": "D132, sécurité serveur",
      "urgence": "haute"
    }
  ],
  "conseils": [
    {
      "id": "C02",
      "objet": "Amputer l'enveloppe SMTP, pas les en-têtes To/Cc",
      "etat": "🕐"
    },
    {
      "id": "C03",
      "objet": "Index partiel pour les non traités",
      "etat": "🕐"
    },
    {
      "id": "C04",
      "objet": "message non partitionnée / rattachement partitionnée",
      "etat": "🕐"
    },
    {
      "id": "C05",
      "objet": "La réponse d'API dit sa portée",
      "etat": "🕐"
    },
    {
      "id": "C06",
      "objet": "Fenêtre temporelle par défaut sur toute recherche",
      "etat": "🕐"
    },
    {
      "id": "C07",
      "objet": "Créer une knowledge/dolibarr/ si l'intégration devient un axe",
      "etat": "🕐"
    },
    {
      "id": "C08",
      "objet": "La V2 (PJ) est le vrai levier de volumétrie, pas le partitionnement",
      "etat": "✅ confirmé par D23"
    },
    {
      "id": "C09",
      "objet": "Champs et tables conseillés pour un email (revue complète)",
      "etat": "✅ validée → D29"
    },
    {
      "id": "C1 ★",
      "objet": "Texte du lien ≠ destination réelle (https://banque.fr pointant ailleurs)",
      "etat": "traqueurs de campagnes marketing — fréquents"
    },
    {
      "id": "C2 ★",
      "objet": "Lien vers un domaine sosie (A8 appliqué aux URL)",
      "etat": "faibles"
    },
    {
      "id": "C3 ★",
      "objet": "Pièce jointe exécutable ou à macros (.exe, .scr, .js, .lnk, .iso, .docm)",
      "etat": "rares en PME"
    },
    {
      "id": "C4 ★",
      "objet": "Archive protégée par un mot de passe donné dans le corps",
      "etat": "quasi nuls — c'est une technique d'évasion antivirus, jamais un usage honnête"
    },
    {
      "id": "C5",
      "objet": "Formulaire ou champ de saisie dans le HTML",
      "etat": "jamais légitime dans un mail"
    },
    {
      "id": "C6",
      "objet": "Motifs de fraude au virement : urgence + confidentialité + demande de paiement",
      "etat": "élevés — à réserver à l'alerte douce, jamais au blocage"
    }
  ],
  "dict": {
    "entites": [
      {
        "id": "comm",
        "nom": "comm",
        "domaine": "communication",
        "etat": "✅",
        "role": "Le TRONC polymorphe : une communication datée, avec un sens et des participants, quel que soit son canal. Porte uniquement ce qui est lu pour afficher une liste ; tout le reste descend dans la table fille du canal. Remplace la table « message » du CDC initial.\n",
        "partition": "BY LIST (type), puis par période de sortie de file (D13)",
        "decisions": [
          "D138",
          "D98",
          "D13",
          "D22",
          "D130"
        ],
        "notes": "Les satellites (rattachement, participant, comm_tag, comm_piece_jointe, analyse, note) pointent le tronc."
      },
      {
        "id": "comm_email",
        "nom": "comm_email",
        "domaine": "communication",
        "etat": "✅",
        "role": "La fille « email » du tronc : en-têtes, identifiants de fil, verdicts d'authentification, référence du blob, empreinte, structure MIME, coordonnées IMAP et MTA. Lue à l'ouverture d'un message, jamais pour une liste.\n",
        "jalon": 1,
        "decisions": [
          "D138",
          "D26",
          "D27",
          "D43",
          "D64",
          "D119"
        ]
      },
      {
        "id": "comm_interne",
        "nom": "comm_interne",
        "domaine": "interne",
        "etat": "✅",
        "role": "Fille « message interne » (note ou message direct entre comptes), hors SMTP, en base.",
        "jalon": 2,
        "decisions": [
          "D12",
          "D123",
          "D138"
        ]
      },
      {
        "id": "comm_groupe",
        "nom": "comm_groupe",
        "domaine": "interne",
        "etat": "✅",
        "role": "Fille « message de groupe » : chat de service, stocké en base, jamais vers l'extérieur.",
        "jalon": 2,
        "decisions": [
          "D122",
          "D123",
          "D124",
          "D138"
        ],
        "notes": "Partition dédiée : 5,5 M de lignes attendues sur cinq ans (D123), à tenir hors du chemin email."
      },
      {
        "id": "participant",
        "nom": "participant",
        "domaine": "communication",
        "etat": "✅",
        "role": "Une adresse impliquée dans une communication, avec son rôle (from/to/cc/bcc/reply-to), son NOM AFFICHÉ tel que déclaré dans ce message, et son ordre. Le nom affiché appartient au message, pas au correspondant : il varie d'un message à l'autre.\n",
        "decisions": [
          "D35",
          "D126"
        ],
        "conseils": [
          "C09"
        ],
        "notes": "Référence l'ADRESSE, jamais l'identité : une fusion d'identités ne réécrit pas les participants."
      },
      {
        "id": "piece_jointe",
        "nom": "piece_jointe",
        "domaine": "stockage",
        "etat": "✅",
        "role": "Une pièce jointe dédupliquée : nom, type déclaré, taille, blob. Le nom appartient au message (liaison), le contenu au blob.",
        "decisions": [
          "D11",
          "D24",
          "D25"
        ]
      },
      {
        "id": "comm_piece_jointe",
        "nom": "comm_piece_jointe",
        "domaine": "stockage",
        "etat": "✅",
        "role": "La liaison message ↔ pièce jointe, qui conserve ordre, encodage de transfert, disposition, content-id et paramètres de partie : sans eux le message se reconstruit mais DKIM ne se revérifie plus.\n",
        "decisions": [
          "D24",
          "D25",
          "D26"
        ]
      },
      {
        "id": "blob",
        "nom": "blob",
        "domaine": "stockage",
        "etat": "✅",
        "role": "Un contenu binaire adressé par empreinte, compressé zstd, hors base. Compteur de références pour le ramasse-miettes ; un blob n'est jamais effacé tant qu'un porteur existe.\n",
        "decisions": [
          "D05",
          "D07",
          "D10",
          "D64",
          "D69",
          "D70",
          "D87"
        ]
      },
      {
        "id": "correspondant",
        "nom": "correspondant",
        "domaine": "identite",
        "etat": "✅",
        "role": "Une IDENTITÉ — personne, boîte fonctionnelle, automate, compte interne — qui peut porter plusieurs adresses. C'est une interprétation révisable ; l'adresse est le fait.\n",
        "decisions": [
          "D35",
          "D61",
          "D126"
        ]
      },
      {
        "id": "adresse",
        "nom": "adresse",
        "domaine": "identite",
        "etat": "✅",
        "role": "Une adresse email = partie locale + référence au domaine. Porte l'adresse complète dénormalisée, la forme normalisée qui porte l'unicité, le lien DATÉ vers l'identité, et les trois natures de confiance (vérifiée, validée, calculée).\n",
        "decisions": [
          "D35",
          "D136",
          "D137",
          "D131"
        ]
      },
      {
        "id": "domaine",
        "nom": "domaine",
        "domaine": "identite",
        "etat": "✅",
        "role": "Un domaine DNS, avec son domaine organisationnel parent (Public Suffix List). Porte ce qui appartient au domaine et non à l'adresse : politique DMARC publiée, « hébergé par nous », sosie d'un domaine connu, plateforme de routage, fiabilité.\n",
        "decisions": [
          "D136",
          "D137",
          "D128"
        ]
      },
      {
        "id": "identite",
        "nom": "identite",
        "domaine": "identite",
        "etat": "✅",
        "role": "Ce SOUS QUOI un compte écrit depuis une boîte : nom affiché, adresse, Reply-To, signature. « Au nom de » optionnel sur boîte partagée.",
        "decisions": [
          "D102",
          "D116"
        ]
      },
      {
        "id": "compte",
        "nom": "compte",
        "domaine": "portee",
        "etat": "✅",
        "role": "Une personne qui se connecte. Est une identité interne (D61). Porte ses préférences personnelles (ordre des dossiers, tris).",
        "decisions": [
          "D61",
          "D63",
          "D135"
        ]
      },
      {
        "id": "boite",
        "nom": "boite",
        "domaine": "portee",
        "etat": "✅",
        "role": "Une adresse de réception administrée : personnelle, partagée, alias (un alias est une vraie boîte), de collecte (dmarc-reports@), ou GROUPE de discussion (un groupe est une boîte). Porte le dossier « Personnel » créé par défaut.\n",
        "decisions": [
          "D38",
          "D39",
          "D115",
          "D124",
          "D134"
        ]
      },
      {
        "id": "rattachement",
        "nom": "rattachement",
        "domaine": "portee",
        "etat": "✅",
        "role": "LE lien entre une communication et une boîte/un compte : c'est ici que vivent les flags de lecture, le statut de traitement, la sortie de file, la suppression (détachement), le drapeau personnel. Sur le chemin le plus chaud ; porte correspondant_id dénormalisé.\n",
        "decisions": [
          "D36",
          "D41",
          "D14",
          "D15",
          "D30",
          "D93",
          "D118",
          "D134"
        ],
        "notes": "Un rattachement marqué supprimé n'est JAMAIS effacé (D118) : c'est ce qui rend la déchetterie lisible par domaine."
      },
      {
        "id": "acces",
        "nom": "acces",
        "domaine": "portee",
        "etat": "✅",
        "role": "Un droit d'un compte sur une boîte (ou une identité), DATÉ : début, fin, rôle, révocation tracée. La trace ne donne pas de droit de lecture.",
        "decisions": [
          "D54",
          "D57",
          "D60",
          "D72",
          "D124"
        ]
      },
      {
        "id": "lecture_groupe",
        "nom": "lecture_groupe",
        "domaine": "interne",
        "etat": "🟡",
        "role": "Position de lecture d'un compte dans un groupe : dernier message lu, vu le. Trente lignes au lieu de trente-trois millions de flags.",
        "decisions": [
          "D124"
        ]
      },
      {
        "id": "application",
        "nom": "application",
        "domaine": "classement",
        "etat": "✅",
        "role": "Une instance d'application connectée (type de connecteur + instance) : jeton, portée (boîtes/domaines), axes qu'elle déclare et alimente.",
        "decisions": [
          "D19",
          "D20",
          "D21",
          "D37",
          "D63"
        ]
      },
      {
        "id": "axe",
        "nom": "axe",
        "domaine": "classement",
        "etat": "✅",
        "role": "Une catégorie de tags, porteuse d'ACL, déclarée par une application — ou DÉRIVÉE du corpus (l'axe « abonnement », un dossier par List-Id, qu'aucune application ne déclare).\n",
        "decisions": [
          "D16",
          "D18",
          "D19",
          "D133",
          "D77"
        ]
      },
      {
        "id": "tag",
        "nom": "tag",
        "domaine": "classement",
        "etat": "✅",
        "role": "Une valeur d'un axe (client=1042, projet=RM2881). Séparée de la liaison pour que l'index reste en B-tree.",
        "decisions": [
          "D16",
          "D17"
        ]
      },
      {
        "id": "comm_tag",
        "nom": "comm_tag",
        "domaine": "classement",
        "etat": "✅",
        "role": "La liaison communication ↔ tag, avec sa SOURCE (quelle application ou quel filtre l'a posée) et la date de sortie dénormalisée pour l'index de liste.",
        "decisions": [
          "D17",
          "D19",
          "D74"
        ],
        "notes": "Q34 ouverte : peut-on retirer à la main un tag posé par un connecteur ?"
      },
      {
        "id": "dossier",
        "nom": "dossier",
        "domaine": "classement",
        "etat": "✅",
        "role": "Un dossier UTILISATEUR classique (un message dans un seul). Les spéciaux sont des vues calculées ; les virtuels sont des filtres sauvegardés.",
        "decisions": [
          "D51",
          "D75"
        ]
      },
      {
        "id": "filtre",
        "nom": "filtre",
        "domaine": "classement",
        "etat": "✅",
        "role": "Une règle du moteur : prédicat + action, ordre explicite, portée en cascade, rétroactive possible, compteur de déclenchements (une règle muette doit se voir). Porte aussi les absences (règle à fenêtre de dates) et les dossiers virtuels (prédicat sans action).\n",
        "decisions": [
          "D74",
          "D75",
          "D113",
          "D106"
        ]
      },
      {
        "id": "envoi",
        "nom": "envoi",
        "domaine": "emission",
        "etat": "✅",
        "role": "Un message émis : identité d'expédition, boîte, programmé pour, remis au relais le, queue_id du MTA, retour d'enveloppe VERP.",
        "decisions": [
          "D99",
          "D114",
          "D119",
          "D120"
        ]
      },
      {
        "id": "envoi_destinataire",
        "nom": "envoi_destinataire",
        "domaine": "emission",
        "etat": "✅",
        "role": "Une ligne PAR DESTINATAIRE d'un envoi : état (préparé, remis, accepté, différé, rejeté, livré), DSN corrélé, code et date.",
        "decisions": [
          "D99",
          "D119",
          "D131"
        ]
      },
      {
        "id": "dmarc_rapport",
        "nom": "dmarc_rapport",
        "domaine": "emission",
        "etat": "✅",
        "role": "Un rapport DMARC agrégé reçu (émetteur, report_id, période, domaine). Unicité (emetteur, report_id).",
        "decisions": [
          "D100",
          "D115"
        ]
      },
      {
        "id": "dmarc_ligne",
        "nom": "dmarc_ligne",
        "domaine": "emission",
        "etat": "✅",
        "role": "Une ligne d'un rapport : IP source, nombre, disposition, résultats SPF/DKIM, alignement.",
        "decisions": [
          "D100"
        ]
      },
      {
        "id": "analyse",
        "nom": "analyse",
        "domaine": "analyse",
        "etat": "✅",
        "role": "Un indice produit par le moteur sur une communication : règle, poids, détails, calculé le. Distingue ce qui est FIGÉ à l'ingestion (famille A) de ce qui est RECALCULABLE (familles B, C, D). Jamais un verdict : un score et son explication.\n",
        "decisions": [
          "D127",
          "D128",
          "D129",
          "D139"
        ]
      },
      {
        "id": "note",
        "nom": "note",
        "domaine": "exploitation",
        "etat": "✅",
        "role": "Une note interne d'équipe sur (communication, boîte), jamais transmise au correspondant.",
        "decisions": [
          "D101"
        ]
      },
      {
        "id": "parametre",
        "nom": "parametre",
        "domaine": "exploitation",
        "etat": "✅",
        "role": "Un réglage en cascade : (portée_type, portée_id, clé, valeur, verrouillé, modifié par, modifié le). Instance → domaine → compte → boîte ; nature collective, personnelle ou mixte.\n",
        "decisions": [
          "D106",
          "D117"
        ]
      },
      {
        "id": "journal",
        "nom": "journal",
        "domaine": "exploitation",
        "etat": "✅",
        "role": "Le journal d'activité : qui a lu, traité, partagé, validé, désabonné, déplacé vers le personnel. Jamais purgé. Sur le dossier personnel, trace le déplacement mais jamais le contenu.\n",
        "decisions": [
          "D54",
          "D56",
          "D59",
          "D134",
          "D132",
          "D137"
        ]
      }
    ],
    "champs": {
      "comm": [
        {
          "nom": "comm_id",
          "type": "id",
          "obligatoire": "oui",
          "role": "identifiant, attribué par partition (D138)"
        },
        {
          "nom": "type",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "type_comm",
          "role": "le canal — clé de partition, et de la clé étrangère composite vers la fille"
        },
        {
          "nom": "date_recue",
          "type": "horodatage",
          "obligatoire": "oui",
          "nature": "fait",
          "role": "date de réception ou d'émission réelle — c'est elle qui trie (C09 : trois dates)"
        },
        {
          "nom": "date_declaree",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "fait",
          "role": "la date que le message déclare — affichée, falsifiable, jamais triée"
        },
        {
          "nom": "date_ingestion",
          "type": "horodatage",
          "obligatoire": "oui",
          "nature": "fait",
          "role": "quand AtomBox l'a pris en charge"
        },
        {
          "nom": "sens",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "sens",
          "role": "entrant ou sortant"
        },
        {
          "nom": "sujet",
          "type": "court",
          "obligatoire": "non",
          "role": "sujet tel que reçu"
        },
        {
          "nom": "sujet_normalise",
          "type": "court",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "sans Re:/Fwd:/TR: en cascade — threading de secours"
        },
        {
          "nom": "thread_id",
          "type": "ref",
          "obligatoire": "non",
          "nature": "recalculable",
          "role": "fil matérialisé (D55) ; une fusion de fils repointe"
        },
        {
          "nom": "nature",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "nature",
          "nature": "figé",
          "role": "humain / liste / notification / service (D130) — décide de l'entrée en file"
        },
        {
          "nom": "from_adresse",
          "type": "court",
          "obligatoire": "oui",
          "nature": "dérivé",
          "role": "DÉNORMALISÉ (D22) : affiché sur chaque ligne de chaque liste"
        },
        {
          "nom": "from_nom",
          "type": "court",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "dénormalisé ; le nom du carnet si connu, sinon le nom déclaré (D126)"
        },
        {
          "nom": "taille",
          "type": "entier",
          "obligatoire": "oui",
          "role": "octets du message complet"
        },
        {
          "nom": "nb_pieces_jointes",
          "type": "entier",
          "obligatoire": "oui",
          "nature": "dérivé",
          "role": "dénormalisé : évite un COUNT par ligne"
        },
        {
          "nom": "langue",
          "type": "court",
          "obligatoire": "non",
          "nature": "figé",
          "role": "détectée à l'ingestion — choisit le dictionnaire plein texte (D34)"
        },
        {
          "nom": "est_chiffre",
          "type": "bool",
          "obligatoire": "oui",
          "nature": "figé",
          "role": "corps chiffré : l'indexeur ne tente pas d'extraire"
        },
        {
          "nom": "est_signe",
          "type": "bool",
          "obligatoire": "oui",
          "nature": "figé"
        },
        {
          "nom": "snippet",
          "type": "court",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "premières lignes en texte, pour la liste"
        }
      ],
      "comm_email": [
        {
          "nom": "comm_id",
          "type": "ref",
          "obligatoire": "oui",
          "role": "clé primaire partagée + CHECK (type = 'email')"
        },
        {
          "nom": "message_id",
          "type": "court",
          "obligatoire": "non",
          "nature": "fait",
          "role": "Message-ID reçu — absent ou aberrant = règle A6"
        },
        {
          "nom": "in_reply_to",
          "type": "court",
          "obligatoire": "non",
          "nature": "fait"
        },
        {
          "nom": "references",
          "type": "long",
          "obligatoire": "non",
          "nature": "fait",
          "role": "chaîne complète, pour le fil"
        },
        {
          "nom": "return_path",
          "type": "court",
          "obligatoire": "non",
          "nature": "fait",
          "role": "adresse d'enveloppe — ≠ From = règle A5"
        },
        {
          "nom": "list_id",
          "type": "court",
          "obligatoire": "non",
          "nature": "fait",
          "role": "clé de regroupement de la nature liste (D130) et de la branche Abonnements (D133)"
        },
        {
          "nom": "list_unsubscribe",
          "type": "court",
          "obligatoire": "non",
          "nature": "fait",
          "role": "URI de désabonnement (mailto: ou https:), D132"
        },
        {
          "nom": "headers",
          "type": "long",
          "obligatoire": "oui",
          "nature": "fait",
          "role": "en-têtes bruts, réversibilité (D25)"
        },
        {
          "nom": "verdict_spf",
          "type": "enum",
          "obligatoire": "non",
          "enum": "verdict",
          "nature": "figé",
          "role": "NULL en V1 (relève IMAP : IP perdue), jamais false par défaut"
        },
        {
          "nom": "verdict_dkim",
          "type": "enum",
          "obligatoire": "non",
          "enum": "verdict",
          "nature": "figé"
        },
        {
          "nom": "verdict_dmarc",
          "type": "enum",
          "obligatoire": "non",
          "enum": "verdict",
          "nature": "figé",
          "role": "alignement — le pivot de D137 et D139"
        },
        {
          "nom": "arc_valide",
          "type": "bool",
          "obligatoire": "non",
          "nature": "figé",
          "role": "ARC présent et valide (A9) — annule A1 sur les listes"
        },
        {
          "nom": "blob_ref",
          "type": "empreinte",
          "obligatoire": "oui",
          "role": "le corps, hors base (D05/D07)"
        },
        {
          "nom": "empreinte",
          "type": "empreinte",
          "obligatoire": "oui",
          "nature": "fait",
          "role": "identité du message pour la déduplication (D64)"
        },
        {
          "nom": "structure_mime",
          "type": "json",
          "obligatoire": "non",
          "nature": "fait",
          "role": "arbre des parties, pour reconstruire à l'octet (D25)"
        },
        {
          "nom": "uid",
          "type": "entier",
          "obligatoire": "non",
          "role": "IMAP, posé sans être utilisé en V1 (D43)"
        },
        {
          "nom": "uid_validity",
          "type": "entier",
          "obligatoire": "non",
          "role": "IMAP (D43)"
        },
        {
          "nom": "queue_id",
          "type": "court",
          "obligatoire": "non",
          "role": "identifiant de file du MTA, corrélation avec son journal (D119)"
        },
        {
          "nom": "reponse_possible",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "reponse_possible",
          "nature": "recalculable",
          "role": "oui / avertir / non — « non » s'apprend d'un DSN 5xx (D131)"
        }
      ],
      "rattachement": [
        {
          "nom": "comm_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "boite_id",
          "type": "ref",
          "obligatoire": "oui",
          "role": "la boîte qui a reçu ou émis — la portée EST le chemin d'accès (D36)"
        },
        {
          "nom": "compte_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "le compte pour un état personnel ; NULL = état de boîte (Q35)"
        },
        {
          "nom": "correspondant_id",
          "type": "ref",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "dénormalisé : le « dossier du correspondant » se lit sans jointure"
        },
        {
          "nom": "lu_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "fait",
          "role": "un FAIT daté, pas un état (D41)"
        },
        {
          "nom": "repondu_le",
          "type": "horodatage",
          "obligatoire": "non"
        },
        {
          "nom": "transfere_le",
          "type": "horodatage",
          "obligatoire": "non"
        },
        {
          "nom": "drapeau",
          "type": "bool",
          "obligatoire": "oui"
        },
        {
          "nom": "statut",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "statut",
          "role": "le workflow de traitement (D93) — pilote, ne classe pas"
        },
        {
          "nom": "sorti_le",
          "type": "horodatage",
          "obligatoire": "non",
          "role": "clé d'archivage = date de traitement (D14) ; NULL = dans la file"
        },
        {
          "nom": "motif_sortie",
          "type": "enum",
          "obligatoire": "condition",
          "enum": "motif_sortie",
          "role": "pourquoi il a quitté la file (D15, D30, D118)"
        },
        {
          "nom": "supprime_par",
          "type": "ref",
          "obligatoire": "condition",
          "role": "avec motif_sortie = supprime"
        },
        {
          "nom": "restaurable_jusqu_au",
          "type": "horodatage",
          "obligatoire": "condition",
          "role": "fin de la fenêtre déchetterie — 30 j réglable par domaine (D121)"
        },
        {
          "nom": "dossier_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "dossier utilisateur (D51)"
        },
        {
          "nom": "dossier_origine_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "pour restaurer là d'où il vient (D88)"
        },
        {
          "nom": "personnel",
          "type": "bool",
          "obligatoire": "oui",
          "role": "hors accès admin, hors rétention, hors legal hold, non partageable (D134) — à exclure de TOUTE requête transverse"
        },
        {
          "nom": "reveil_le",
          "type": "horodatage",
          "obligatoire": "non",
          "role": "revient en tête de file à cette date (D103)"
        },
        {
          "nom": "echeance_le",
          "type": "horodatage",
          "obligatoire": "non",
          "role": "date limite affichée (D103)"
        },
        {
          "nom": "gele",
          "type": "bool",
          "obligatoire": "oui",
          "role": "conservation sur litige : prime sur toute purge (D104)"
        }
      ],
      "adresse": [
        {
          "nom": "adresse_id",
          "type": "id",
          "obligatoire": "oui"
        },
        {
          "nom": "local",
          "type": "court",
          "obligatoire": "oui",
          "nature": "fait",
          "role": "partie locale telle que reçue"
        },
        {
          "nom": "local_cmp",
          "type": "court",
          "obligatoire": "oui",
          "nature": "dérivé",
          "role": "minuscules — porte l'UNICITÉ avec domaine_id (D136)"
        },
        {
          "nom": "local_base",
          "type": "court",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "sans sous-adressage (+tag) — rapprocher sans fusionner"
        },
        {
          "nom": "domaine_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "adresse_complete",
          "type": "court",
          "obligatoire": "oui",
          "nature": "dérivé",
          "role": "dénormalisée (D22) : affichée partout"
        },
        {
          "nom": "correspondant_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "l'identité — interprétation révisable (D35)"
        },
        {
          "nom": "lie_le",
          "type": "horodatage",
          "obligatoire": "condition",
          "role": "le lien vers l'identité est DATÉ : une adresse change de titulaire (D136)"
        },
        {
          "nom": "delie_le",
          "type": "horodatage",
          "obligatoire": "non"
        },
        {
          "nom": "verifie_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "fait",
          "role": "défi relevé par l'expéditeur — ⏸ mécanisme en réserve (Q54)"
        },
        {
          "nom": "verifie_methode",
          "type": "court",
          "obligatoire": "condition"
        },
        {
          "nom": "valide_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "fait",
          "role": "validation humaine chez nous (D137)"
        },
        {
          "nom": "valide_par",
          "type": "ref",
          "obligatoire": "condition",
          "role": "le compte — tracé au journal"
        },
        {
          "nom": "valide_portee",
          "type": "enum",
          "obligatoire": "condition",
          "enum": "portee",
          "role": "boîte par défaut, domaine, instance (D106)"
        },
        {
          "nom": "fiabilite",
          "type": "entier",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "score SIGNÉ, cache du moteur ; jamais saisi (D137)"
        },
        {
          "nom": "fiabilite_calculee_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "dérivé"
        }
      ],
      "domaine": [
        {
          "nom": "domaine_id",
          "type": "id",
          "obligatoire": "oui"
        },
        {
          "nom": "nom_ascii",
          "type": "court",
          "obligatoire": "oui",
          "nature": "fait",
          "role": "punycode, minuscules — porte l'unicité"
        },
        {
          "nom": "nom_unicode",
          "type": "court",
          "obligatoire": "oui",
          "nature": "dérivé",
          "role": "pour l'affichage"
        },
        {
          "nom": "parent_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "domaine organisationnel via Public Suffix List (D136) — alignement relaxed, A8"
        },
        {
          "nom": "heberge_par_nous",
          "type": "bool",
          "obligatoire": "oui",
          "role": "règle A2 : un message « de nous » venu d'Internet"
        },
        {
          "nom": "politique_dmarc",
          "type": "enum",
          "obligatoire": "non",
          "enum": "politique_dmarc",
          "nature": "recalculable",
          "role": "none / quarantine / reject, telle que publiée — le pivot de D139"
        },
        {
          "nom": "politique_lue_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "recalculable"
        },
        {
          "nom": "sosie_de",
          "type": "ref",
          "obligatoire": "non",
          "nature": "recalculable",
          "role": "règle A8 : distance ≤ 2, homoglyphes, punycode"
        },
        {
          "nom": "enregistre_le",
          "type": "date",
          "obligatoire": "non",
          "role": "règle B5, source externe optionnelle"
        },
        {
          "nom": "plateforme",
          "type": "court",
          "obligatoire": "non",
          "nature": "recalculable",
          "role": "routeur identifié (Brevo, Sarbacane…) — indice de nature liste"
        },
        {
          "nom": "valide_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "fait"
        },
        {
          "nom": "valide_par",
          "type": "ref",
          "obligatoire": "condition"
        },
        {
          "nom": "valide_portee",
          "type": "enum",
          "obligatoire": "condition",
          "enum": "portee"
        },
        {
          "nom": "fiabilite",
          "type": "entier",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "signée ; une adresse n'est jamais plus fiable que son domaine (D137)"
        }
      ],
      "correspondant": [
        {
          "nom": "correspondant_id",
          "type": "id",
          "obligatoire": "oui"
        },
        {
          "nom": "nom_canonique",
          "type": "court",
          "obligatoire": "oui",
          "role": "le nom du carnet (D126)"
        },
        {
          "nom": "type",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "type_correspondant",
          "role": "personne / boîte fonctionnelle / automate / compte interne (D61) — interdit certaines fusions"
        },
        {
          "nom": "cree_le",
          "type": "horodatage",
          "obligatoire": "oui"
        },
        {
          "nom": "organisation_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "posée pour le multi-organisation (D62), vaut une seule valeur en V1"
        }
      ],
      "participant": [
        {
          "nom": "comm_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "role",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "role_participant"
        },
        {
          "nom": "adresse_id",
          "type": "ref",
          "obligatoire": "oui",
          "role": "l'ADRESSE, jamais l'identité (D35)"
        },
        {
          "nom": "nom_affiche",
          "type": "court",
          "obligatoire": "non",
          "nature": "fait",
          "role": "tel que déclaré dans CE message — varie d'un message à l'autre"
        },
        {
          "nom": "ordre",
          "type": "entier",
          "obligatoire": "oui"
        }
      ],
      "envoi": [
        {
          "nom": "envoi_id",
          "type": "id",
          "obligatoire": "oui"
        },
        {
          "nom": "comm_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "identite_id",
          "type": "ref",
          "obligatoire": "oui",
          "role": "sous quoi on écrit (D102) — From = la boîte (D116)"
        },
        {
          "nom": "programme_pour",
          "type": "horodatage",
          "obligatoire": "non",
          "role": "envoi différé, annulable avant l'heure (D99)"
        },
        {
          "nom": "remis_le",
          "type": "horodatage",
          "obligatoire": "non",
          "role": "remise au relais du client (D114)"
        },
        {
          "nom": "queue_id",
          "type": "court",
          "obligatoire": "non",
          "role": "corrélation avec le journal du MTA (D119)"
        },
        {
          "nom": "retour_enveloppe",
          "type": "court",
          "obligatoire": "oui",
          "role": "adresse VERP unique — corrèle les DSN sans heuristique (D119)"
        }
      ],
      "envoi_destinataire": [
        {
          "nom": "envoi_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "adresse_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "etat",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "etat_envoi"
        },
        {
          "nom": "dsn_comm_id",
          "type": "ref",
          "obligatoire": "non",
          "role": "le message de service (nature service) qui porte le retour"
        },
        {
          "nom": "code",
          "type": "court",
          "obligatoire": "non",
          "role": "550 5.1.1 … — c'est lui qui fait passer reponse_possible à non (D131)"
        },
        {
          "nom": "mis_a_jour_le",
          "type": "horodatage",
          "obligatoire": "oui"
        }
      ],
      "analyse": [
        {
          "nom": "comm_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "regle",
          "type": "court",
          "obligatoire": "oui",
          "role": "A1…A11, B1…B5, C1…C6, D (D128)"
        },
        {
          "nom": "poids",
          "type": "entier",
          "obligatoire": "oui",
          "role": "poids explicite, modifiable (Q55)"
        },
        {
          "nom": "details",
          "type": "json",
          "obligatoire": "non",
          "role": "ce qui explique l'indice — jamais un IBAN en clair (D129)"
        },
        {
          "nom": "calcule_le",
          "type": "horodatage",
          "obligatoire": "oui"
        },
        {
          "nom": "fige",
          "type": "bool",
          "obligatoire": "oui",
          "role": "vrai pour la famille A (dépend de l'instant), faux pour B/C/D (D127)"
        }
      ],
      "parametre": [
        {
          "nom": "portee_type",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "portee"
        },
        {
          "nom": "portee_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "cle",
          "type": "court",
          "obligatoire": "oui"
        },
        {
          "nom": "valeur",
          "type": "json",
          "obligatoire": "oui"
        },
        {
          "nom": "verrouille",
          "type": "bool",
          "obligatoire": "oui",
          "role": "un niveau supérieur interdit la surcharge (D117) — jamais le poste de travail"
        },
        {
          "nom": "modifie_par",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "modifie_le",
          "type": "horodatage",
          "obligatoire": "oui"
        }
      ],
      "acces": [
        {
          "nom": "compte_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "boite_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "role",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "role_acces"
        },
        {
          "nom": "debut",
          "type": "horodatage",
          "obligatoire": "oui"
        },
        {
          "nom": "fin",
          "type": "horodatage",
          "obligatoire": "non",
          "role": "révocation : la trace reste, le droit tombe (D54)"
        },
        {
          "nom": "accorde_par",
          "type": "ref",
          "obligatoire": "oui"
        }
      ],
      "boite": [
        {
          "nom": "boite_id",
          "type": "id",
          "obligatoire": "oui"
        },
        {
          "nom": "adresse_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "domaine_id",
          "type": "ref",
          "obligatoire": "oui",
          "role": "la portée d'administration (D38)"
        },
        {
          "nom": "type",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "type_boite"
        },
        {
          "nom": "absence",
          "type": "json",
          "obligatoire": "non",
          "role": "réglage collectif : période, message, renvoi (D113) — porté par un filtre"
        }
      ],
      "comm_tag": [
        {
          "nom": "comm_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "tag_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "source",
          "type": "court",
          "obligatoire": "oui",
          "role": "l'application ou le filtre qui l'a posé (D19) — Q34"
        },
        {
          "nom": "pose_le",
          "type": "horodatage",
          "obligatoire": "oui"
        },
        {
          "nom": "sorti_le",
          "type": "horodatage",
          "obligatoire": "non",
          "nature": "dérivé",
          "role": "dénormalisé pour l'index de liste par tag (D16)"
        }
      ],
      "lecture_groupe": [
        {
          "nom": "compte_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "boite_id",
          "type": "ref",
          "obligatoire": "oui",
          "role": "le groupe est une boîte (D124)"
        },
        {
          "nom": "dernier_message_lu",
          "type": "ref",
          "obligatoire": "non"
        },
        {
          "nom": "vu_le",
          "type": "horodatage",
          "obligatoire": "non"
        }
      ],
      "journal": [
        {
          "nom": "journal_id",
          "type": "id",
          "obligatoire": "oui"
        },
        {
          "nom": "quand",
          "type": "horodatage",
          "obligatoire": "oui"
        },
        {
          "nom": "qui",
          "type": "ref",
          "obligatoire": "oui",
          "role": "compte ou application"
        },
        {
          "nom": "action",
          "type": "enum",
          "obligatoire": "oui",
          "enum": "action_journal"
        },
        {
          "nom": "cible_type",
          "type": "court",
          "obligatoire": "oui"
        },
        {
          "nom": "cible_id",
          "type": "ref",
          "obligatoire": "oui"
        },
        {
          "nom": "details",
          "type": "json",
          "obligatoire": "non",
          "role": "JAMAIS le contenu d'un message du dossier personnel (D134)"
        }
      ]
    },
    "relations": [
      {
        "de": "comm",
        "vers": "comm_email",
        "cardinalite": "1-0..1",
        "role": "la fille du canal email — clé composite (comm_id, type) + CHECK",
        "datee": "non",
        "decision": "D138"
      },
      {
        "de": "comm",
        "vers": "comm_interne",
        "cardinalite": "1-0..1",
        "role": "la fille du canal interne",
        "datee": "non",
        "decision": "D138"
      },
      {
        "de": "comm",
        "vers": "comm_groupe",
        "cardinalite": "1-0..1",
        "role": "la fille du canal groupe",
        "datee": "non",
        "decision": "D138"
      },
      {
        "de": "comm",
        "vers": "participant",
        "cardinalite": "1-n",
        "role": "les adresses du message par rôle",
        "datee": "non",
        "decision": "D35"
      },
      {
        "de": "participant",
        "vers": "adresse",
        "cardinalite": "n-1",
        "role": "le fait pointe l'adresse, jamais l'identité",
        "datee": "non",
        "decision": "D35"
      },
      {
        "de": "adresse",
        "vers": "domaine",
        "cardinalite": "n-1",
        "role": "local + domaine = adresse",
        "datee": "non",
        "decision": "D136"
      },
      {
        "de": "domaine",
        "vers": "domaine",
        "cardinalite": "n-1",
        "role": "parent = domaine organisationnel (PSL)",
        "datee": "non",
        "decision": "D136"
      },
      {
        "de": "adresse",
        "vers": "correspondant",
        "cardinalite": "n-1",
        "role": "l'identité, interprétation révisable",
        "datee": "oui",
        "decision": "D136"
      },
      {
        "de": "comm",
        "vers": "rattachement",
        "cardinalite": "1-n",
        "role": "un message, N boîtes/comptes — la déduplication (D10) vit ici",
        "datee": "non",
        "decision": "D36"
      },
      {
        "de": "rattachement",
        "vers": "boite",
        "cardinalite": "n-1",
        "role": "la portée est le chemin d'accès",
        "datee": "non",
        "decision": "D36"
      },
      {
        "de": "rattachement",
        "vers": "compte",
        "cardinalite": "n-0..1",
        "role": "état personnel (lu, statut) — Q35 tranche par compte ou par boîte",
        "datee": "non",
        "decision": "D41"
      },
      {
        "de": "rattachement",
        "vers": "dossier",
        "cardinalite": "n-0..1",
        "role": "dossier utilisateur classique",
        "datee": "non",
        "decision": "D51"
      },
      {
        "de": "compte",
        "vers": "acces",
        "cardinalite": "1-n",
        "role": "droits sur des boîtes",
        "datee": "oui",
        "decision": "D54"
      },
      {
        "de": "acces",
        "vers": "boite",
        "cardinalite": "n-1",
        "role": "",
        "datee": "oui",
        "decision": "D57"
      },
      {
        "de": "boite",
        "vers": "identite",
        "cardinalite": "1-n",
        "role": "sous quoi on écrit depuis cette boîte",
        "datee": "non",
        "decision": "D102"
      },
      {
        "de": "compte",
        "vers": "lecture_groupe",
        "cardinalite": "1-n",
        "role": "position de lecture par groupe",
        "datee": "non",
        "decision": "D124"
      },
      {
        "de": "lecture_groupe",
        "vers": "boite",
        "cardinalite": "n-1",
        "role": "le groupe est une boîte",
        "datee": "non",
        "decision": "D124"
      },
      {
        "de": "comm",
        "vers": "comm_tag",
        "cardinalite": "1-n",
        "role": "multi-classement : autant de tags qu'il en satisfait",
        "datee": "non",
        "decision": "D17"
      },
      {
        "de": "comm_tag",
        "vers": "tag",
        "cardinalite": "n-1",
        "role": "",
        "datee": "non",
        "decision": "D16"
      },
      {
        "de": "tag",
        "vers": "axe",
        "cardinalite": "n-1",
        "role": "une valeur appartient à un axe",
        "datee": "non",
        "decision": "D16"
      },
      {
        "de": "axe",
        "vers": "application",
        "cardinalite": "n-0..1",
        "role": "NULL pour un axe dérivé (abonnement)",
        "datee": "non",
        "decision": "D133"
      },
      {
        "de": "comm_tag",
        "vers": "application",
        "cardinalite": "n-0..1",
        "role": "la source du tag (ou un filtre)",
        "datee": "non",
        "decision": "D19"
      },
      {
        "de": "comm",
        "vers": "comm_piece_jointe",
        "cardinalite": "1-n",
        "role": "liaison ordonnée, avec l'encodage de partie",
        "datee": "non",
        "decision": "D24"
      },
      {
        "de": "comm_piece_jointe",
        "vers": "piece_jointe",
        "cardinalite": "n-1",
        "role": "",
        "datee": "non",
        "decision": "D11"
      },
      {
        "de": "piece_jointe",
        "vers": "blob",
        "cardinalite": "n-1",
        "role": "contenu dédupliqué par empreinte",
        "datee": "non",
        "decision": "D10"
      },
      {
        "de": "comm_email",
        "vers": "blob",
        "cardinalite": "n-1",
        "role": "le corps, hors base",
        "datee": "non",
        "decision": "D05"
      },
      {
        "de": "comm",
        "vers": "comm",
        "cardinalite": "n-0..1",
        "role": "référence : transfert sans copie, pointeur qui peut mourir (Q30)",
        "datee": "non",
        "decision": "D58"
      },
      {
        "de": "comm",
        "vers": "envoi",
        "cardinalite": "1-0..1",
        "role": "un message sortant a un envoi",
        "datee": "non",
        "decision": "D99"
      },
      {
        "de": "envoi",
        "vers": "envoi_destinataire",
        "cardinalite": "1-n",
        "role": "une ligne par destinataire",
        "datee": "non",
        "decision": "D99"
      },
      {
        "de": "envoi_destinataire",
        "vers": "comm",
        "cardinalite": "n-0..1",
        "role": "le DSN corrélé (nature service)",
        "datee": "non",
        "decision": "D119"
      },
      {
        "de": "envoi",
        "vers": "identite",
        "cardinalite": "n-1",
        "role": "",
        "datee": "non",
        "decision": "D102"
      },
      {
        "de": "dmarc_rapport",
        "vers": "dmarc_ligne",
        "cardinalite": "1-n",
        "role": "",
        "datee": "non",
        "decision": "D100"
      },
      {
        "de": "dmarc_rapport",
        "vers": "domaine",
        "cardinalite": "n-1",
        "role": "le domaine évalué (le nôtre)",
        "datee": "non",
        "decision": "D115"
      },
      {
        "de": "comm",
        "vers": "analyse",
        "cardinalite": "1-n",
        "role": "un indice par règle déclenchée",
        "datee": "non",
        "decision": "D127"
      },
      {
        "de": "comm",
        "vers": "note",
        "cardinalite": "1-n",
        "role": "note d'équipe, par boîte",
        "datee": "non",
        "decision": "D101"
      },
      {
        "de": "note",
        "vers": "boite",
        "cardinalite": "n-1",
        "role": "",
        "datee": "non",
        "decision": "D101"
      },
      {
        "de": "filtre",
        "vers": "boite",
        "cardinalite": "n-0..1",
        "role": "portée du filtre (cascade)",
        "datee": "non",
        "decision": "D106"
      },
      {
        "de": "comm",
        "vers": "comm",
        "cardinalite": "n-0..1",
        "role": "thread_id : le fil matérialisé",
        "datee": "non",
        "decision": "D55"
      }
    ],
    "enumerations": {
      "type_comm": {
        "role": "le canal d'une communication — clé de partition du tronc (D138)",
        "valeurs": [
          {
            "id": "email",
            "libelle": "E-mail",
            "jalon": 1,
            "fille": "comm_email"
          },
          {
            "id": "interne",
            "libelle": "Message interne",
            "jalon": 2,
            "fille": "comm_interne"
          },
          {
            "id": "groupe",
            "libelle": "Message de groupe",
            "jalon": 2,
            "fille": "comm_groupe"
          },
          {
            "id": "sms",
            "libelle": "SMS",
            "jalon": 4
          },
          {
            "id": "whatsapp",
            "libelle": "WhatsApp",
            "jalon": 4
          },
          {
            "id": "tel",
            "libelle": "Appel téléphonique",
            "jalon": 4,
            "note": "pas de corps : un événement daté avec participants et durée"
          }
        ]
      },
      "sens": {
        "role": "entrant ou sortant",
        "valeurs": [
          {
            "id": "in",
            "libelle": "Reçu"
          },
          {
            "id": "out",
            "libelle": "Émis"
          }
        ]
      },
      "nature": {
        "role": "ce que le message attend de nous (D130) — figée à l'ingestion",
        "valeurs": [
          {
            "id": "humain",
            "libelle": "Humain",
            "attend_action": "oui",
            "repondable": "oui",
            "entre_en_file": "oui"
          },
          {
            "id": "liste",
            "libelle": "Diffusion",
            "attend_action": "non",
            "repondable": "rare",
            "entre_en_file": "non",
            "note": "désabonnable (D132), engendre la branche Abonnements (D133)"
          },
          {
            "id": "notification",
            "libelle": "Notification",
            "attend_action": "souvent",
            "repondable": "non",
            "entre_en_file": "oui",
            "note": "une facture est une machine qui attend un paiement"
          },
          {
            "id": "service",
            "libelle": "Service",
            "attend_action": "non",
            "repondable": "jamais",
            "entre_en_file": "jamais",
            "note": "DSN, absence, ARF — se rattache à un envoi (D99)"
          }
        ]
      },
      "statut": {
        "role": "le workflow de traitement (D93) — PILOTE, ne classe pas ; ordonné, fermé, propre au compte",
        "valeurs": [
          {
            "id": "nouveau",
            "libelle": "Nouveau",
            "ordre": 0
          },
          {
            "id": "a_faire",
            "libelle": "À faire",
            "ordre": 1
          },
          {
            "id": "en_cours",
            "libelle": "En cours",
            "ordre": 2
          },
          {
            "id": "attente",
            "libelle": "En attente",
            "ordre": 3,
            "note": "relance attendue"
          },
          {
            "id": "traite",
            "libelle": "Traité",
            "ordre": 4,
            "sortie": "traite"
          }
        ],
        "questions": [
          "Q35",
          "Q36"
        ]
      },
      "motif_sortie": {
        "role": "pourquoi un rattachement a quitté la file (D15, D30, D118)",
        "valeurs": [
          {
            "id": "traite",
            "libelle": "Traité"
          },
          {
            "id": "archive",
            "libelle": "Archivé sans traiter",
            "note": "D30"
          },
          {
            "id": "supprime",
            "libelle": "Détaché",
            "note": "déchetterie = état calculé par domaine ; jamais effacé (D118)"
          }
        ]
      },
      "reponse_possible": {
        "role": "peut-on répondre à cette adresse (D131) — recalculable",
        "valeurs": [
          {
            "id": "oui",
            "libelle": "Oui"
          },
          {
            "id": "avertir",
            "libelle": "Avertir",
            "note": "déduit de la nature ou d'une convention de nommage — jamais bloquant"
          },
          {
            "id": "non",
            "libelle": "Refuser",
            "note": "sur PREUVE : Reply-To vide, ou DSN 5xx déjà reçu — daté, réévaluable"
          }
        ]
      },
      "verdict": {
        "role": "résultat d'une vérification d'authentification (D26, D27) — figé",
        "valeurs": [
          {
            "id": "pass",
            "libelle": "Pass"
          },
          {
            "id": "fail",
            "libelle": "Fail"
          },
          {
            "id": "none",
            "libelle": "Aucun"
          },
          {
            "id": null,
            "libelle": "Non vérifiable",
            "note": "V1 : la relève IMAP a perdu l'IP — jamais fail par défaut"
          }
        ]
      },
      "politique_dmarc": {
        "role": "ce que le domaine émetteur a publié — le pivot du geste (D139)",
        "valeurs": [
          {
            "id": "none",
            "libelle": "p=none",
            "geste_si_non_aligne": "alerter"
          },
          {
            "id": "quarantine",
            "libelle": "p=quarantine",
            "geste_si_non_aligne": "quarantaine"
          },
          {
            "id": "reject",
            "libelle": "p=reject",
            "geste_si_non_aligne": "refuser",
            "note": "V2 seulement — en V1 il est trop tard"
          }
        ]
      },
      "geste": {
        "role": "ce qu'AtomBox fait d'un message (D139) : on refuse sur un fait, quarantaine sur une présomption, alerte sur un indice",
        "valeurs": [
          {
            "id": "rien",
            "libelle": "Rien"
          },
          {
            "id": "alerter",
            "libelle": "Alerter",
            "note": "bannière graduée (D105)"
          },
          {
            "id": "quarantaine",
            "libelle": "Quarantaine",
            "note": "visible de son destinataire, libérable, enseigne (D71, D91)"
          },
          {
            "id": "refuser",
            "libelle": "Refuser",
            "note": "à la réception SMTP — p=reject non aligné, ou code malveillant ; JAMAIS sur un score"
          }
        ]
      },
      "portee": {
        "role": "la cascade de paramétrage (D106) — et la portée d'une validation (D137)",
        "valeurs": [
          {
            "id": "instance",
            "libelle": "Instance",
            "ordre": 0
          },
          {
            "id": "domaine",
            "libelle": "Domaine",
            "ordre": 1
          },
          {
            "id": "compte",
            "libelle": "Compte",
            "ordre": 2
          },
          {
            "id": "boite",
            "libelle": "Boîte",
            "ordre": 3
          }
        ]
      },
      "nature_parametre": {
        "role": "sur une boîte partagée, certains réglages sont collectifs (D106)",
        "valeurs": [
          {
            "id": "collectif",
            "libelle": "Collectif",
            "note": "absence, désabonnement, validation d'un expéditeur"
          },
          {
            "id": "personnel",
            "libelle": "Personnel",
            "note": "ordre des dossiers, tris, affichage"
          },
          {
            "id": "mixte",
            "libelle": "Mixte"
          }
        ]
      },
      "etat_envoi": {
        "role": "cycle de vie d'un envoi, par destinataire (D99)",
        "valeurs": [
          {
            "id": "prepare",
            "libelle": "Préparé"
          },
          {
            "id": "programme",
            "libelle": "Programmé",
            "note": "annulable avant l'heure"
          },
          {
            "id": "remis",
            "libelle": "Remis au relais"
          },
          {
            "id": "accepte",
            "libelle": "Accepté par le serveur distant"
          },
          {
            "id": "differe",
            "libelle": "Différé (4xx)"
          },
          {
            "id": "rejete",
            "libelle": "Rejeté (5xx)",
            "note": "fait passer reponse_possible à non (D131)"
          },
          {
            "id": "livre",
            "libelle": "Livré",
            "note": "NOTIFY=SUCCESS, opportuniste (D119)"
          }
        ]
      },
      "role_participant": {
        "role": "rôle d'une adresse dans un message",
        "valeurs": [
          {
            "id": "from"
          },
          {
            "id": "to"
          },
          {
            "id": "cc"
          },
          {
            "id": "bcc"
          },
          {
            "id": "reply_to"
          },
          {
            "id": "sender"
          }
        ]
      },
      "type_correspondant": {
        "role": "types d'identité (D61) — interdit certaines fusions",
        "valeurs": [
          {
            "id": "personne",
            "libelle": "Personne"
          },
          {
            "id": "fonctionnel",
            "libelle": "Boîte fonctionnelle",
            "note": "contact@, facturation@ — pas une personne"
          },
          {
            "id": "automate",
            "libelle": "Automate",
            "note": "no-reply@ — ne se fusionne jamais avec une personne"
          },
          {
            "id": "interne",
            "libelle": "Compte interne",
            "note": "un compte est une identité (D61)"
          }
        ]
      },
      "type_boite": {
        "role": "ce qu'est une boîte (D38, D39, D115, D124)",
        "valeurs": [
          {
            "id": "personnelle"
          },
          {
            "id": "partagee"
          },
          {
            "id": "alias",
            "note": "un alias est une vraie boîte"
          },
          {
            "id": "collecte",
            "note": "dmarc-reports@<domaine>, une par domaine (D115)"
          },
          {
            "id": "groupe",
            "note": "un groupe de discussion est une boîte (D124)"
          }
        ]
      },
      "role_acces": {
        "role": "rôles sur une boîte et d'administration (D72)",
        "valeurs": [
          {
            "id": "lecteur"
          },
          {
            "id": "membre"
          },
          {
            "id": "gestionnaire"
          },
          {
            "id": "admin_domaine",
            "note": "ne lit JAMAIS le dossier personnel (D134)"
          },
          {
            "id": "admin_instance"
          }
        ]
      },
      "fiabilite": {
        "role": "échelle signée de confiance (D137) — dérivée, jamais saisie",
        "valeurs": [
          {
            "id": -2,
            "libelle": "Malveillant connu"
          },
          {
            "id": -1,
            "libelle": "Douteux"
          },
          {
            "id": 0,
            "libelle": "Inconnu / non authentifiable"
          },
          {
            "id": 1,
            "libelle": "Connu, authentifié"
          },
          {
            "id": 2,
            "libelle": "Validé, authentifié"
          }
        ]
      },
      "type_identifiant": {
        "role": "un identifiant de correspondant porte un type (D98) — email en V1, téléphone en V4",
        "valeurs": [
          {
            "id": "email",
            "jalon": 1
          },
          {
            "id": "tel",
            "jalon": 4
          },
          {
            "id": "whatsapp",
            "jalon": 4
          }
        ]
      },
      "action_journal": {
        "role": "ce que le journal (D54) enregistre",
        "valeurs": [
          {
            "id": "lu"
          },
          {
            "id": "traite"
          },
          {
            "id": "partage"
          },
          {
            "id": "revoque"
          },
          {
            "id": "supprime"
          },
          {
            "id": "restaure"
          },
          {
            "id": "valide_expediteur",
            "note": "D137 — avec la portée"
          },
          {
            "id": "desabonne",
            "note": "D132 — acte de la boîte, sur boîte partagée engage les autres"
          },
          {
            "id": "vers_personnel",
            "note": "D134 — le déplacement, jamais le contenu"
          },
          {
            "id": "libere_quarantaine",
            "note": "D91 — enseigne"
          },
          {
            "id": "admin_lecture",
            "note": "D38 — un admin qui lit est tracé"
          }
        ]
      }
    },
    "workflows": [
      {
        "id": "traitement",
        "nom": "Traitement d'un message reçu",
        "entite": "rattachement",
        "champ": "statut",
        "decisions": [
          "D93",
          "D13",
          "D14",
          "D41"
        ],
        "etats": [
          "nouveau",
          "a_faire",
          "en_cours",
          "attente",
          "traite"
        ],
        "regles": [
          "le statut PILOTE, il ne classe pas : un tag classe, un statut dit où en est le traitement",
          "lu_le est un fait à part : on peut être lu et à faire, non lu et pris en charge par un collègue",
          "une nature liste n'entre pas dans la file ; une nature notification y entre (D130)"
        ],
        "transitions": [
          {
            "de": "nouveau",
            "vers": "a_faire",
            "geste": "Prendre",
            "qui": "membre",
            "effet": "auto-assignation"
          },
          {
            "de": "a_faire",
            "vers": "en_cours",
            "geste": "Commencer",
            "qui": "membre"
          },
          {
            "de": "en_cours",
            "vers": "attente",
            "geste": "Attendre une réponse",
            "qui": "membre",
            "effet": "reveil_le optionnel (D103)"
          },
          {
            "de": "attente",
            "vers": "en_cours",
            "geste": "Reprendre",
            "qui": "membre",
            "effet": "ou automatique au réveil"
          },
          {
            "de": "*",
            "vers": "traite",
            "geste": "Traiter",
            "qui": "membre",
            "effet": "sorti_le = maintenant, motif_sortie = traite — quitte la file (D14)"
          },
          {
            "de": "*",
            "vers": "*",
            "geste": "Archiver sans traiter",
            "qui": "membre",
            "effet": "sorti_le, motif_sortie = archive (D30) — statut inchangé"
          },
          {
            "de": "traite",
            "vers": "a_faire",
            "geste": "Reprendre dans la file",
            "qui": "membre",
            "effet": "sorti_le = NULL (Q09)"
          }
        ],
        "questions": [
          "Q35",
          "Q36",
          "Q09"
        ]
      },
      {
        "id": "suppression",
        "nom": "Supprimer, détacher, déchetterie",
        "entite": "rattachement",
        "decisions": [
          "D118",
          "D121",
          "D87"
        ],
        "regles": [
          "supprimer = DÉTACHER ce rattachement ; le message vit tant qu'un autre rattachement existe",
          "un rattachement supprimé n'est JAMAIS effacé : c'est ce qui rend la déchetterie lisible par domaine",
          "la déchetterie est un ÉTAT CALCULÉ (plus aucun rattachement actif), pas un dossier"
        ],
        "transitions": [
          {
            "de": "en file ou sorti",
            "vers": "corbeille",
            "geste": "Mettre à la corbeille",
            "qui": "membre",
            "effet": "dossier_origine_id mémorisé (D88)"
          },
          {
            "de": "corbeille",
            "vers": "état précédent",
            "geste": "Restaurer",
            "qui": "membre",
            "effet": "revient dans son dossier d'origine"
          },
          {
            "de": "corbeille",
            "vers": "detache",
            "geste": "Supprimer",
            "qui": "membre",
            "effet": "motif_sortie = supprime, supprime_par, restaurable_jusqu_au = +30 j (réglable par domaine)"
          },
          {
            "de": "detache",
            "vers": "état précédent",
            "geste": "Restaurer depuis la déchetterie",
            "qui": "admin_domaine",
            "effet": "chez le destinataire d'origine (D121)"
          },
          {
            "de": "detache",
            "vers": "efface",
            "geste": "Ramasse-miettes",
            "qui": "systeme",
            "effet": "après restaurable_jusqu_au, si plus aucun rattachement actif ni gel : le blob perd une référence (D87)"
          }
        ],
        "garde_fous": [
          "un rattachement gelé (legal hold) ne passe jamais à effacé (D104)",
          "un rattachement personnel (D134) ne remonte JAMAIS dans la déchetterie d'administration"
        ]
      },
      {
        "id": "envoi",
        "nom": "Cycle de vie d'un envoi",
        "entite": "envoi_destinataire",
        "champ": "etat",
        "decisions": [
          "D99",
          "D114",
          "D119",
          "D120",
          "D131"
        ],
        "etats": [
          "prepare",
          "programme",
          "remis",
          "accepte",
          "differe",
          "rejete",
          "livre"
        ],
        "transitions": [
          {
            "de": "prepare",
            "vers": "programme",
            "geste": "Programmer",
            "qui": "auteur",
            "effet": "programme_pour ; annulable avant l'heure"
          },
          {
            "de": "programme",
            "vers": "prepare",
            "geste": "Annuler l'envoi programmé",
            "qui": "auteur"
          },
          {
            "de": "prepare|programme",
            "vers": "remis",
            "geste": "Remettre au relais",
            "qui": "systeme",
            "effet": "queue_id, retour d'enveloppe VERP unique"
          },
          {
            "de": "remis",
            "vers": "accepte",
            "geste": "",
            "qui": "systeme",
            "effet": "journal du MTA : status=sent (D119)"
          },
          {
            "de": "remis",
            "vers": "differe",
            "geste": "",
            "qui": "systeme",
            "effet": "4xx — ne prouve rien"
          },
          {
            "de": "remis|differe",
            "vers": "rejete",
            "geste": "",
            "qui": "systeme",
            "effet": "DSN 5xx corrélé par VERP → reponse_possible = non sur l'adresse (D131)"
          },
          {
            "de": "accepte",
            "vers": "livre",
            "geste": "",
            "qui": "systeme",
            "effet": "NOTIFY=SUCCESS, opportuniste"
          }
        ],
        "regles": [
          "on n'émet jamais pour savoir : VERP socle, journal du MTA si le MTA est à nous, accusé opportuniste (D119)",
          "un renvoi réécrit l'enveloppe (SRS, D120) sinon le renvoi sur collègue casse SPF"
        ]
      },
      {
        "id": "quarantaine",
        "nom": "Quarantaine et apprentissage",
        "entite": "rattachement",
        "decisions": [
          "D71",
          "D91",
          "D139"
        ],
        "transitions": [
          {
            "de": "recu",
            "vers": "quarantaine",
            "geste": "",
            "qui": "systeme",
            "effet": "présomption forte (deux ★ de familles différentes, p=quarantine non aligné, PJ exécutable)"
          },
          {
            "de": "quarantaine",
            "vers": "boite",
            "geste": "Libérer",
            "qui": "destinataire",
            "effet": "ENSEIGNE (D91) ; propose d'enregistrer l'expéditeur au carnet (D126)"
          },
          {
            "de": "quarantaine",
            "vers": "detache",
            "geste": "Confirmer indésirable",
            "qui": "destinataire",
            "effet": "enseigne dans l'autre sens"
          },
          {
            "de": "quarantaine",
            "vers": "efface",
            "geste": "Expiration",
            "qui": "systeme",
            "effet": "après rétention de quarantaine"
          }
        ],
        "regles": [
          "la quarantaine est VISIBLE de son destinataire, pas seulement de l'administrateur",
          "jamais de réponse automatique, jamais de désabonnement, jamais de défi depuis la quarantaine"
        ]
      },
      {
        "id": "confiance",
        "nom": "Fiabilité d'un expéditeur",
        "entite": "adresse",
        "decisions": [
          "D137",
          "D126",
          "D128"
        ],
        "transitions": [
          {
            "de": "inconnu",
            "vers": "connu",
            "geste": "Enregistrer au carnet",
            "qui": "membre",
            "effet": "correspondant_id, lie_le"
          },
          {
            "de": "connu",
            "vers": "valide",
            "geste": "Marquer comme fiable",
            "qui": "membre",
            "effet": "valide_le, valide_par, valide_portee (boîte par défaut) — tracé ; IMPOSSIBLE sur un message non aligné"
          },
          {
            "de": "valide",
            "vers": "connu",
            "geste": "Retirer la validation",
            "qui": "membre"
          },
          {
            "de": "*",
            "vers": "douteux",
            "geste": "Ne plus jamais faire confiance",
            "qui": "membre",
            "effet": "fiabilité négative — alimente D91"
          },
          {
            "de": "valide",
            "vers": "connu",
            "geste": "",
            "qui": "systeme",
            "effet": "rupture d'habitude (B3), politique DMARC disparue : la confiance s'éteint"
          }
        ],
        "regles": [
          "l'indicateur ne s'affiche que si CE message est aligné",
          "la fiabilité positive n'annule jamais une règle ★ ; elle atténue les pondérateurs",
          "une adresse n'est jamais plus fiable que son domaine n'est authentifiable"
        ]
      },
      {
        "id": "desabonnement",
        "nom": "Se désabonner d'une liste",
        "entite": "comm_email",
        "decisions": [
          "D132",
          "D133",
          "D54"
        ],
        "transitions": [
          {
            "de": "abonne",
            "vers": "demande",
            "geste": "Se désabonner",
            "qui": "membre",
            "effet": "one-click (POST, Q51) ou mailto: par notre émission (D99) — JAMAIS automatique, jamais depuis la quarantaine ; tracé (acte de la boîte)"
          },
          {
            "de": "demande",
            "vers": "confirme",
            "geste": "",
            "qui": "systeme",
            "effet": "plus aucun message de ce List-Id depuis 30 j"
          },
          {
            "de": "demande",
            "vers": "ignore",
            "geste": "",
            "qui": "systeme",
            "effet": "des messages arrivent encore après 30 j : signalé — motif de plainte"
          }
        ]
      },
      {
        "id": "personnel",
        "nom": "Le dossier personnel",
        "entite": "rattachement",
        "champ": "personnel",
        "decisions": [
          "D134"
        ],
        "transitions": [
          {
            "de": "ordinaire",
            "vers": "personnel",
            "geste": "Déplacer vers Personnel",
            "qui": "proprietaire",
            "effet": "geste humain SEULEMENT — aucun filtre, aucun connecteur ne peut y déposer ; le journal trace le déplacement, jamais le contenu"
          },
          {
            "de": "personnel",
            "vers": "ordinaire",
            "geste": "Sortir de Personnel",
            "qui": "proprietaire",
            "effet": "rentre dans la rétention à partir de maintenant, pas rétroactivement"
          }
        ],
        "regles": [
          "hors accès administrateur, hors partage, hors rétention, hors legal hold, hors déchetterie d'administration",
          "toute requête transverse porte l'exclusion — un test d'exclusion par mécanique dès la V1"
        ]
      },
      {
        "id": "absence",
        "nom": "Absence et renvoi",
        "entite": "filtre",
        "decisions": [
          "D113",
          "D120",
          "D106"
        ],
        "regles": [
          "une règle du moteur avec une fenêtre de dates ; la fin est OBLIGATOIRE",
          "une seule réponse par correspondant et par période",
          "jamais vers une nature liste ou service, jamais depuis la quarantaine",
          "réglage COLLECTIF sur boîte partagée",
          "le renvoi vers un collègue réécrit l'enveloppe (SRS)"
        ]
      }
    ],
    "actions": [
      {
        "id": "ouvrir",
        "libelle": "Ouvrir",
        "contexte": "liste",
        "portee": "rattachement",
        "effet": "onglet provisoire ; double-clic épingle",
        "trace": "non",
        "poc": ".msg onclick",
        "decisions": [
          "D79"
        ]
      },
      {
        "id": "lire",
        "libelle": "Marquer lu / non lu",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "lu_le posé ou effacé — un fait, pas un état (D41)",
        "trace": "oui",
        "poc": "data-x=lire|nonLu",
        "decisions": [
          "D41"
        ]
      },
      {
        "id": "statuer",
        "libelle": "Changer le statut",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "workflow de traitement ; « traité » sort de la file",
        "trace": "oui",
        "poc": "select#stat → MessageService.statuer",
        "decisions": [
          "D93",
          "D14"
        ]
      },
      {
        "id": "archiver",
        "libelle": "Archiver sans traiter",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "sorti_le, motif archive",
        "trace": "oui",
        "poc": "MessageService.archiver",
        "decisions": [
          "D30"
        ]
      },
      {
        "id": "refile",
        "libelle": "Remettre dans la file",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "sorti_le = NULL",
        "trace": "oui",
        "poc": "data-x=refile",
        "decisions": [],
        "questions": [
          "Q09"
        ]
      },
      {
        "id": "corbeille",
        "libelle": "Mettre à la corbeille",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "dossier_origine mémorisé",
        "trace": "oui",
        "poc": "data-x=corbeille",
        "decisions": [
          "D88"
        ]
      },
      {
        "id": "restaurer",
        "libelle": "Restaurer",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "revient d'où il vient",
        "trace": "oui",
        "poc": "data-x=restaurer",
        "decisions": [
          "D88",
          "D121"
        ]
      },
      {
        "id": "supprimer",
        "libelle": "Supprimer définitivement",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "DÉTACHE : motif supprime, restaurable 30 j ; le message vit tant qu'un autre est attaché",
        "trace": "oui",
        "poc": "data-x=supprimer",
        "decisions": [
          "D118"
        ]
      },
      {
        "id": "vider_corbeille",
        "libelle": "Vider la corbeille",
        "contexte": "dossier",
        "portee": "rattachement",
        "effet": "supprimer sur chaque élément",
        "trace": "oui",
        "poc": "MessageService.viderCorbeille",
        "decisions": [
          "D118"
        ]
      },
      {
        "id": "junk",
        "libelle": "Indésirable / pas indésirable",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "quarantaine ou libération — ENSEIGNE (D91)",
        "trace": "oui",
        "poc": "data-x=junk|nonJunk",
        "decisions": [
          "D71",
          "D91"
        ]
      },
      {
        "id": "repondre",
        "libelle": "Répondre",
        "contexte": "message",
        "portee": "envoi",
        "effet": "composition depuis l'identité de la boîte qui a reçu (Q26) ; avertissement ou refus selon reponse_possible (D131)",
        "trace": "non",
        "poc": "data-c=rep",
        "decisions": [
          "D116",
          "D131"
        ]
      },
      {
        "id": "repondre_tous",
        "libelle": "Répondre à tous",
        "contexte": "message",
        "portee": "envoi",
        "effet": "",
        "trace": "non",
        "poc": "data-c=reptous",
        "decisions": [
          "D116"
        ]
      },
      {
        "id": "transferer",
        "libelle": "Transférer",
        "contexte": "message",
        "portee": "envoi",
        "effet": "par RÉFÉRENCE en interne (pas de copie, D58) ; encapsulé vers l'extérieur (D66)",
        "trace": "oui",
        "poc": "data-c=tr",
        "decisions": [
          "D58",
          "D66",
          "D67"
        ]
      },
      {
        "id": "ecrire_a_contact",
        "libelle": "Écrire au contact proposé",
        "contexte": "message",
        "portee": "envoi",
        "effet": "réorientation quand l'adresse n'accepte pas de réponse — montré, jamais présélectionné",
        "trace": "non",
        "poc": "bouton du bandeau",
        "decisions": [
          "D131"
        ]
      },
      {
        "id": "composer",
        "libelle": "Nouveau message",
        "contexte": "composition",
        "portee": "envoi",
        "effet": "choix de l'identité (D102), destinataires avec complétion (D109)",
        "trace": "non",
        "poc": "Compose.demarrer",
        "decisions": [
          "D102",
          "D109"
        ]
      },
      {
        "id": "joindre",
        "libelle": "Joindre un fichier",
        "contexte": "composition",
        "portee": "envoi",
        "effet": "ou par lien (D111) quand un fournisseur de fichiers est branché",
        "trace": "non",
        "poc": "ComposeService.joindre",
        "decisions": [
          "D111"
        ]
      },
      {
        "id": "envoyer",
        "libelle": "Envoyer",
        "contexte": "composition",
        "portee": "envoi",
        "effet": "internes livrés en base, externes remis au relais ; avertissement si mixte (D12)",
        "trace": "oui",
        "poc": "Compose.finir(t, true)",
        "decisions": [
          "D12",
          "D99",
          "D114"
        ]
      },
      {
        "id": "programmer",
        "libelle": "Envoyer plus tard",
        "contexte": "composition",
        "portee": "envoi",
        "effet": "programme_pour, annulable avant l'heure",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D99"
        ]
      },
      {
        "id": "brouillon",
        "libelle": "Enregistrer le brouillon",
        "contexte": "composition",
        "portee": "compte",
        "effet": "",
        "trace": "non",
        "poc": "ComposeService.enregistrer",
        "decisions": []
      },
      {
        "id": "taguer",
        "libelle": "Ajouter / retirer un tag",
        "contexte": "message",
        "portee": "comm",
        "effet": "fait PARTAGÉ (D17) ; source = manuel ; retirer un tag de connecteur = Q34",
        "trace": "oui",
        "poc": "MessageService.ajouterTag|retirerTag",
        "decisions": [
          "D17",
          "D18"
        ]
      },
      {
        "id": "noter",
        "libelle": "Note interne",
        "contexte": "message",
        "portee": "boite",
        "effet": "jamais transmise",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D101"
        ]
      },
      {
        "id": "reveil",
        "libelle": "Me le rappeler le…",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "reveil_le / echeance_le",
        "trace": "non",
        "poc": "non",
        "decisions": [
          "D103"
        ]
      },
      {
        "id": "valider_expediteur",
        "libelle": "Marquer cet expéditeur comme fiable",
        "contexte": "message",
        "portee": "adresse",
        "effet": "valide_le/par/portée — IMPOSSIBLE si le message n'est pas aligné",
        "trace": "oui",
        "poc": "bouton du bandeau (désactivé si non aligné)",
        "decisions": [
          "D137"
        ]
      },
      {
        "id": "mefiance",
        "libelle": "Ne plus jamais faire confiance",
        "contexte": "message",
        "portee": "adresse",
        "effet": "fiabilité négative",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D137",
          "D91"
        ]
      },
      {
        "id": "desabonner",
        "libelle": "Se désabonner",
        "contexte": "message",
        "portee": "boite",
        "effet": "acte de la boîte — collectif, tracé ; one-click ou mailto:",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D132",
          "D133"
        ]
      },
      {
        "id": "vers_personnel",
        "libelle": "Déplacer vers Personnel",
        "contexte": "message",
        "portee": "rattachement",
        "effet": "geste humain seulement ; le journal trace le déplacement, pas le contenu",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D134"
        ]
      },
      {
        "id": "imprimer",
        "libelle": "Imprimer / exporter en PDF",
        "contexte": "message",
        "portee": "comm",
        "effet": "",
        "trace": "non",
        "poc": "non",
        "decisions": [
          "D110"
        ]
      },
      {
        "id": "original",
        "libelle": "Télécharger l'original (.eml)",
        "contexte": "message",
        "portee": "comm",
        "effet": "reconstruction à l'octet (D25)",
        "trace": "oui",
        "poc": "logMessage(orig)",
        "decisions": [
          "D25"
        ]
      },
      {
        "id": "ouvrir_dossier",
        "libelle": "Ouvrir un dossier",
        "contexte": "arborescence",
        "portee": "compte",
        "effet": "vue engendrée (D77) ; un axe dérivé sélectionne par prédicat (D133)",
        "trace": "non",
        "poc": ".node onclick",
        "decisions": [
          "D77",
          "D133"
        ]
      },
      {
        "id": "filtrer_dossiers",
        "libelle": "Filtrer les dossiers",
        "contexte": "arborescence",
        "portee": "compte",
        "effet": "",
        "trace": "non",
        "poc": "#navq",
        "decisions": [
          "D77"
        ]
      },
      {
        "id": "ordonner_axes",
        "libelle": "Monter / descendre un axe",
        "contexte": "arborescence",
        "portee": "compte",
        "effet": "ordre manuel des axes, persistant",
        "trace": "non",
        "poc": "data-mv=up|down",
        "decisions": [
          "D135"
        ]
      },
      {
        "id": "trier_axe",
        "libelle": "Trier un axe (activité / A→Z)",
        "contexte": "arborescence",
        "portee": "compte",
        "effet": "jamais d'ordre manuel sur les valeurs",
        "trace": "non",
        "poc": "data-tri",
        "decisions": [
          "D135"
        ]
      },
      {
        "id": "voir_plus",
        "libelle": "Voir les N autres",
        "contexte": "arborescence",
        "portee": "compte",
        "effet": "pagination d'un axe",
        "trace": "non",
        "poc": "data-more",
        "decisions": [
          "D78"
        ]
      },
      {
        "id": "filtrer_liste",
        "libelle": "Filtrer / trier la liste",
        "contexte": "liste",
        "portee": "compte",
        "effet": "file, sortis, non lus, récents, PJ, lourds × sens × statut",
        "trace": "non",
        "poc": ".chip[data-f|data-s]",
        "decisions": [
          "D13"
        ]
      },
      {
        "id": "rechercher",
        "libelle": "Rechercher",
        "contexte": "liste",
        "portee": "compte",
        "effet": "plein texte sur la zone active par défaut (D34)",
        "trace": "non",
        "poc": "#q",
        "decisions": [
          "D34"
        ],
        "conseils": [
          "C05"
        ]
      },
      {
        "id": "liberer",
        "libelle": "Libérer de la quarantaine",
        "contexte": "quarantaine",
        "portee": "rattachement",
        "effet": "enseigne ; propose d'enregistrer au carnet",
        "trace": "oui",
        "poc": "data-x=nonJunk",
        "decisions": [
          "D91",
          "D126"
        ]
      },
      {
        "id": "partager",
        "libelle": "Partager une boîte / un message",
        "contexte": "administration",
        "portee": "boite",
        "effet": "acces daté, révocable ; la trace ne donne pas de droit",
        "trace": "oui",
        "poc": "page admin",
        "decisions": [
          "D57",
          "D60"
        ]
      },
      {
        "id": "revoquer",
        "libelle": "Révoquer un accès",
        "contexte": "administration",
        "portee": "boite",
        "effet": "fin posée, trace conservée",
        "trace": "oui",
        "poc": "page admin",
        "decisions": [
          "D54"
        ]
      },
      {
        "id": "parametrer",
        "libelle": "Régler / verrouiller un paramètre",
        "contexte": "administration",
        "portee": "instance|domaine|compte|boite",
        "effet": "cascade ; verrouillage jamais sur le poste de travail",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D106",
          "D117"
        ]
      },
      {
        "id": "dechetterie",
        "libelle": "Consulter la déchetterie",
        "contexte": "administration",
        "portee": "domaine",
        "effet": "métadonnées seules, restauration chez l'origine ; jamais le personnel",
        "trace": "oui",
        "poc": "non",
        "decisions": [
          "D121",
          "D134"
        ]
      },
      {
        "id": "brancher_capacite",
        "libelle": "Choisir un fournisseur de capacité",
        "contexte": "administration",
        "portee": "instance",
        "effet": "tâches, contacts, cloud, CRM : natif, connecteur, ou aucun",
        "trace": "oui",
        "poc": "Providers.choisir",
        "decisions": [
          "D94",
          "D95b"
        ]
      }
    ],
    "templates": [
      {
        "nom": "message.card",
        "contexte": "liste",
        "role": "la carte d'un message dans une liste — assemble header, body, meta, actions",
        "surchargeable": "oui",
        "appelle": [
          "message.card.header",
          "message.card.body",
          "message.card.meta",
          "message.card.actions"
        ]
      },
      {
        "nom": "message.card.header",
        "contexte": "liste",
        "role": "première ligne : indicateur de confiance, expéditeur normalisé, date",
        "surchargeable": "oui",
        "variantes": [
          "sent : montre le destinataire (« À : ») au lieu de l'expéditeur"
        ],
        "appelle": [
          "fiabilite",
          "expediteur"
        ]
      },
      {
        "nom": "message.card.body",
        "contexte": "liste",
        "role": "sujet et extrait",
        "surchargeable": "oui",
        "variantes": [
          "notification : sans extrait — une alerte de supervision n'en a pas besoin"
        ]
      },
      {
        "nom": "message.card.meta",
        "contexte": "liste",
        "role": "pièces jointes, statut, tags",
        "surchargeable": "oui",
        "variantes": [
          "notification",
          "sav : numéro de ticket en avant",
          "social",
          "developpement : numéro RM en avant, titre en info-bulle"
        ],
        "appelle": [
          "statut.chip",
          "tag.chip"
        ]
      },
      {
        "nom": "message.card.actions",
        "contexte": "liste",
        "role": "actions rapides au survol",
        "surchargeable": "oui"
      },
      {
        "nom": "expediteur",
        "contexte": "liste",
        "role": "le nom du carnet si connu, l'ADRESSE en avant sinon ; une machine n'est pas un inconnu suspect (D126, D130)",
        "surchargeable": "oui",
        "appelle": [
          "nature.chip"
        ],
        "decisions": [
          "D126",
          "D128",
          "D130"
        ]
      },
      {
        "nom": "fiabilite",
        "contexte": "liste",
        "role": "✓ validé / · connu — seulement si le message est aligné (D137)",
        "surchargeable": "oui",
        "decisions": [
          "D137"
        ]
      },
      {
        "nom": "nature.chip",
        "contexte": "liste",
        "role": "diffusion / notification / service — un fait de classement, en gris",
        "surchargeable": "oui",
        "decisions": [
          "D130"
        ]
      },
      {
        "nom": "statut.chip",
        "contexte": "liste",
        "role": "le statut de traitement, ou le motif de sortie",
        "surchargeable": "oui",
        "decisions": [
          "D93"
        ]
      },
      {
        "nom": "tag.chip",
        "contexte": "liste",
        "role": "un tag avec son axe et sa source",
        "surchargeable": "oui",
        "decisions": [
          "D17",
          "D19"
        ]
      },
      {
        "nom": "message.tags",
        "contexte": "message",
        "role": "les tags du message ouvert, avec ajout/retrait",
        "surchargeable": "oui",
        "decisions": [
          "D17"
        ]
      },
      {
        "nom": "attachment.list",
        "contexte": "message",
        "role": "liste des pièces jointes",
        "surchargeable": "oui",
        "appelle": [
          "attachment.card"
        ]
      },
      {
        "nom": "attachment.card",
        "contexte": "message",
        "role": "une pièce jointe : nom, taille, blob dédupliqué, actions",
        "surchargeable": "oui",
        "decisions": [
          "D11",
          "D24"
        ]
      },
      {
        "nom": "erp.panel",
        "contexte": "message",
        "role": "le contexte métier affiché sans être stocké (D19, D21) — fiche tiers, devis, factures",
        "surchargeable": "oui",
        "decisions": [
          "D19",
          "D21",
          "Q31"
        ]
      },
      {
        "nom": "thread.item",
        "contexte": "message",
        "role": "un message du fil (D55)",
        "surchargeable": "oui",
        "decisions": [
          "D55"
        ]
      },
      {
        "nom": "nav.node",
        "contexte": "arborescence",
        "role": "un nœud de l'arborescence engendrée : icône, libellé, compteur non lus/total",
        "surchargeable": "oui",
        "appelle": [
          "nav.axe.outils"
        ],
        "decisions": [
          "D77",
          "D78"
        ]
      },
      {
        "nom": "nav.axe.outils",
        "contexte": "arborescence",
        "role": "monter / descendre / trier un axe — visibles au survol seulement (D135)",
        "surchargeable": "oui",
        "decisions": [
          "D135"
        ]
      },
      {
        "nom": "message.bandeau.fiabilite",
        "contexte": "message",
        "role": "validé / non authentifié / connu sans validation — dit qui et quelle portée",
        "surchargeable": "à faire",
        "decisions": [
          "D137"
        ]
      },
      {
        "nom": "message.bandeau.reponse",
        "contexte": "message",
        "role": "diffusion / notification / refus daté sur DSN, avec le contact proposé",
        "surchargeable": "à faire",
        "decisions": [
          "D131"
        ]
      },
      {
        "nom": "message.bandeau.usurpation",
        "contexte": "message",
        "role": "nomme la règle déclenchée (B1, A8) ; alerte, ne rejette pas",
        "surchargeable": "à faire",
        "decisions": [
          "D128"
        ]
      },
      {
        "nom": "message.bandeau.lien",
        "contexte": "message",
        "role": "transfert par référence — le pointeur peut mourir (Q30)",
        "surchargeable": "à faire",
        "decisions": [
          "D58",
          "D67"
        ]
      },
      {
        "nom": "message.statut",
        "contexte": "message",
        "role": "le sélecteur de statut — l'action principale",
        "surchargeable": "à faire",
        "decisions": [
          "D93"
        ]
      },
      {
        "nom": "message.menu",
        "contexte": "message",
        "role": "actions rares et capacités enfichables, avec le nom du fournisseur",
        "surchargeable": "à faire",
        "decisions": [
          "D94"
        ]
      }
    ],
    "composants": {
      "noyau": [
        {
          "id": "registry",
          "nom": "Registre de vues partielles",
          "role": "define / defineFor / render / has / liste ; ctx.base() pour étendre une variante",
          "contrat": "R.define(nom, fn) ; R.defineFor(nom, variante, fn) ; R.render(nom, ctx)",
          "decisions": [
            "D79"
          ],
          "poc": "js/core/registry.js"
        },
        {
          "id": "store",
          "nom": "État persisté",
          "role": "le delta par rapport au corpus engendré + l'état d'interface ; seul lui va en stockage local",
          "contrat": "charge() / save() / patch(m, {…})",
          "poc": "js/core/store.js"
        },
        {
          "id": "bus",
          "nom": "Bus d'événements",
          "role": "découplage vues ↔ contrôleurs",
          "contrat": "on(evt, fn) / emit(evt, data)",
          "poc": "js/core/bus.js"
        },
        {
          "id": "prng",
          "nom": "Générateur déterministe",
          "role": "corpus identique d'une session à l'autre ; P.with(clé, fn) pour fabriquer hors flux sans décaler la séquence",
          "contrat": "next() / int(a,b) / pick(arr) / with(clé, fn)",
          "poc": "js/core/prng.js"
        },
        {
          "id": "format",
          "nom": "Formatage",
          "role": "esc, dt, poids, slug",
          "poc": "js/core/format.js"
        },
        {
          "id": "query_log",
          "nom": "Journal des requêtes",
          "role": "montre ce que le serveur FERAIT : ui → http → sql → json → render, avec l'index attendu et les avertissements",
          "contrat": "add(label, sql, index, warn, kind) ou add({label, etapes})",
          "decisions": [
            "D80"
          ],
          "poc": "js/services/query-log.js"
        },
        {
          "id": "api_trace",
          "nom": "Trace d'API",
          "role": "la route, le contrôleur, le contrat JSON — le POC ne les exécute pas, il les montre",
          "poc": "js/services/api-trace.js"
        },
        {
          "id": "corpus",
          "nom": "Corpus engendré",
          "role": "dossiers, messages, compteurs en UNE passe (D78), vues calculées, axe dérivé (D133)",
          "decisions": [
            "D77",
            "D78",
            "D133"
          ],
          "poc": "js/services/corpus.js"
        },
        {
          "id": "providers",
          "nom": "Fournisseurs de capacités",
          "role": "quelle implémentation porte chaque capacité (D94) ; l'entrée de menu disparaît si aucune",
          "decisions": [
            "D94",
            "D95b"
          ],
          "poc": "js/services/providers.js"
        },
        {
          "id": "cdc_index",
          "nom": "Index du CDC",
          "role": "GÉNÉRÉ : décisions, questions, chapitres, et désormais le dictionnaire — la page CDC du POC dit ce que dit le registre",
          "poc": "outils/gen-cdc-index.py → js/services/cdc-index.js"
        }
      ],
      "capacite": [
        {
          "id": "taches",
          "nom": "Gestionnaire de tâches",
          "contrat": "creer(titre, echeance, comm_id) / lister(filtre) / cloturer(id)",
          "fournisseurs": [
            "aucun",
            "natif (V3)",
            "dolibarr",
            "redmine"
          ],
          "decisions": [
            "D94",
            "D95b"
          ]
        },
        {
          "id": "contacts",
          "nom": "Carnet de contacts",
          "contrat": "lire(adresse) / chercher(q) / enregistrer(identité)",
          "fournisseurs": [
            "natif-lecture (V1",
            "D35)",
            "dolibarr",
            "natif-autorité (V3)"
          ],
          "decisions": [
            "D35",
            "D95b"
          ]
        },
        {
          "id": "fichiers",
          "nom": "Dépôt de fichiers",
          "contrat": "deposer(blob) → lien / lister",
          "fournisseurs": [
            "aucun",
            "nextcloud",
            "natif (V3)"
          ],
          "decisions": [
            "D111",
            "D95b"
          ]
        },
        {
          "id": "crm",
          "nom": "CRM",
          "contrat": "tiers(adresse) / opportunites / journal",
          "fournisseurs": [
            "aucun",
            "dolibarr",
            "natif (V3",
            "Q39)"
          ],
          "decisions": [
            "D94",
            "Q39"
          ]
        },
        {
          "id": "canaux",
          "nom": "Canaux",
          "contrat": "recevoir / emettre par canal",
          "fournisseurs": [
            "email (V1)",
            "interne (V2)",
            "sms",
            "whatsapp",
            "tel (V4)"
          ],
          "decisions": [
            "D97",
            "D98"
          ]
        }
      ],
      "embarquable": [
        {
          "id": "echanges_tiers",
          "nom": "Les échanges avec ce tiers",
          "role": "liste des communications d'un correspondant, tous canaux, insérable dans une fiche client",
          "exigences": "jeton à portée étroite ; 404 et non 403 hors portée",
          "decisions": [
            "D108"
          ]
        },
        {
          "id": "joindre_dossier",
          "nom": "Joindre ce message au dossier",
          "role": "poser un tag d'axe depuis l'application tierce",
          "decisions": [
            "D108",
            "D17"
          ]
        },
        {
          "id": "lecteur",
          "nom": "Le lecteur seul",
          "role": "afficher un message (affichage sûr D105) hors du webmail",
          "decisions": [
            "D108",
            "D105"
          ]
        },
        {
          "id": "composeur",
          "nom": "Le composeur",
          "role": "écrire depuis une application tierce, avec l'identité de la boîte",
          "decisions": [
            "D108",
            "D102"
          ]
        },
        {
          "id": "sdk_php",
          "nom": "SDK PHP",
          "role": "authentification, portée, pagination, erreurs typées",
          "decisions": [
            "D108"
          ]
        },
        {
          "id": "sdk_js",
          "nom": "SDK JS",
          "role": "idem, second",
          "decisions": [
            "D108"
          ]
        }
      ]
    },
    "protocoles": [
      {
        "id": "imap",
        "nom": "IMAP",
        "sens": "entrant",
        "jalon": 1,
        "role": "relève des boîtes existantes en lecture seule (IDLE, une connexion par boîte quand AtomBox classe lui-même)",
        "decisions": [
          "D42",
          "D44",
          "D46",
          "D48",
          "D74"
        ],
        "normes": [
          "RFC3501",
          "RFC9051"
        ]
      },
      {
        "id": "lmtp",
        "nom": "LMTP",
        "sens": "entrant",
        "jalon": 2,
        "role": "Postfix livre directement à AtomBox, qui devient le MDA ; sémantique 4xx/5xx à tester",
        "decisions": [
          "D42",
          "D45"
        ],
        "normes": [
          "RFC2033"
        ]
      },
      {
        "id": "smtp",
        "nom": "SMTP (soumission)",
        "sens": "sortant",
        "jalon": 1,
        "role": "remise au relais du client — pas de file de sortie propre",
        "decisions": [
          "D114",
          "D119"
        ],
        "normes": [
          "RFC5321",
          "RFC6409",
          "RFC6531"
        ]
      },
      {
        "id": "dsn",
        "nom": "DSN",
        "sens": "entrant",
        "jalon": 1,
        "role": "avis de non-remise corrélés à l'envoi par VERP ; Original-Envelope-Id ; NOTIFY=SUCCESS opportuniste",
        "decisions": [
          "D99",
          "D119"
        ],
        "normes": [
          "RFC3461",
          "RFC3464"
        ]
      },
      {
        "id": "verp",
        "nom": "VERP",
        "sens": "sortant",
        "jalon": 1,
        "role": "retour d'enveloppe unique par (envoi, destinataire) ; rejet du backscatter",
        "decisions": [
          "D119"
        ],
        "normes": []
      },
      {
        "id": "srs",
        "nom": "SRS",
        "sens": "sortant",
        "jalon": 1,
        "role": "réécriture de l'enveloppe sur les renvois — sans lui, le renvoi sur collègue casse SPF",
        "decisions": [
          "D120",
          "D113"
        ],
        "normes": []
      },
      {
        "id": "spf",
        "nom": "SPF",
        "sens": "entrant",
        "jalon": 1,
        "role": "verdict figé à l'ingestion ; NULL en V1 (IP perdue en relève IMAP)",
        "decisions": [
          "D26",
          "D27"
        ],
        "normes": [
          "RFC7208"
        ]
      },
      {
        "id": "dkim",
        "nom": "DKIM",
        "sens": "les deux",
        "jalon": 1,
        "role": "vérification à l'ingestion, revérifiable grâce à la réversibilité (D25) ; signature de nos envois",
        "decisions": [
          "D25",
          "D26"
        ],
        "normes": [
          "RFC6376"
        ]
      },
      {
        "id": "dmarc",
        "nom": "DMARC",
        "sens": "les deux",
        "jalon": 1,
        "role": "alignement = le pivot de la fiabilité (D137) et du geste (D139) ; rapports agrégés collectés par domaine",
        "decisions": [
          "D100",
          "D115",
          "D137",
          "D139"
        ],
        "normes": [
          "RFC7489"
        ]
      },
      {
        "id": "arc",
        "nom": "ARC",
        "sens": "entrant",
        "jalon": 1,
        "role": "annule un échec DMARC légitime (listes, redirections) — sans lui, p=reject rejette le courrier des listes",
        "decisions": [
          "D128",
          "D139"
        ],
        "normes": [
          "RFC8617"
        ]
      },
      {
        "id": "mime",
        "nom": "MIME",
        "sens": "les deux",
        "jalon": 1,
        "role": "structure des messages, extraction réversible des pièces jointes, noms encodés (RFC 2231)",
        "decisions": [
          "D24",
          "D25",
          "D69",
          "D70"
        ],
        "normes": [
          "RFC2045",
          "RFC2046",
          "RFC2047",
          "RFC2183",
          "RFC2231"
        ]
      },
      {
        "id": "list_headers",
        "nom": "En-têtes de liste",
        "sens": "entrant",
        "jalon": 1,
        "role": "List-Id, List-Unsubscribe, List-Unsubscribe-Post : nature liste, branche Abonnements, désabonnement",
        "decisions": [
          "D130",
          "D132",
          "D133"
        ],
        "normes": [
          "RFC2369",
          "RFC2919",
          "RFC8058"
        ]
      },
      {
        "id": "auto_submitted",
        "nom": "Auto-Submitted",
        "sens": "entrant",
        "jalon": 1,
        "role": "auto-generated → notification ; auto-replied → service ; Reply-To vide = ne pas répondre",
        "decisions": [
          "D130",
          "D131",
          "D113"
        ],
        "normes": [
          "RFC3834"
        ]
      },
      {
        "id": "maildir",
        "nom": "Maildir",
        "sens": "entrant",
        "jalon": 1,
        "role": "format d'import d'historique ; le stockage AtomBox n'est PAS un Maildir (D09b)",
        "decisions": [
          "D09b",
          "D107"
        ],
        "normes": []
      },
      {
        "id": "mbox_pst",
        "nom": "mbox / PST",
        "sens": "entrant",
        "jalon": 1,
        "role": "import d'historique",
        "decisions": [
          "D107"
        ],
        "normes": [
          "RFC4155"
        ]
      },
      {
        "id": "sieve",
        "nom": "Sieve",
        "sens": "—",
        "jalon": 1,
        "role": "REMPLACÉ par le moteur de filtres (D74) ; l'import d'un script Sieve existant est un besoin (chapitre 14)",
        "decisions": [
          "D74"
        ],
        "normes": [
          "RFC5228"
        ]
      },
      {
        "id": "http_rest",
        "nom": "HTTP / REST",
        "sens": "les deux",
        "jalon": 1,
        "role": "l'API (hypothèse Q07), jetons opaques, 404 hors portée",
        "decisions": [
          "D63",
          "D108"
        ],
        "normes": [
          "RFC9110",
          "RFC8259",
          "RFC3986"
        ]
      },
      {
        "id": "temps_reel",
        "nom": "Temps réel (SSE ou WebSocket)",
        "sens": "sortant",
        "jalon": 2,
        "role": "arrivée, prise en charge, chat — obligatoire avec les groupes (D125)",
        "decisions": [
          "D125"
        ],
        "normes": [
          "RFC6455"
        ]
      },
      {
        "id": "sso",
        "nom": "OAuth 2 / OpenID Connect",
        "sens": "entrant",
        "jalon": 1,
        "role": "SSO du webmail ; IMAP ne fait pas de SSO (chapitre 05)",
        "decisions": [
          "D63"
        ],
        "normes": [
          "RFC6749",
          "RFC6750"
        ]
      },
      {
        "id": "webdav",
        "nom": "WebDAV / API Nextcloud",
        "sens": "sortant",
        "jalon": 1,
        "role": "pièce jointe par lien : dépôt chez un fournisseur externe",
        "decisions": [
          "D111"
        ],
        "normes": [
          "RFC4918"
        ]
      },
      {
        "id": "erp_api",
        "nom": "API Dolibarr / Redmine",
        "sens": "les deux",
        "jalon": 1,
        "role": "contexte métier affiché sans être stocké ; tags poussés par l'application déclarante ; IBAN comparé au tiers",
        "decisions": [
          "D19",
          "D21",
          "D129"
        ],
        "normes": []
      },
      {
        "id": "whois_rdap",
        "nom": "RDAP / WHOIS",
        "sens": "sortant",
        "jalon": 2,
        "role": "âge d'un domaine (règle B5) — option, source externe",
        "decisions": [
          "D128"
        ],
        "normes": [
          "RFC7480"
        ]
      },
      {
        "id": "psl",
        "nom": "Public Suffix List",
        "sens": "—",
        "jalon": 1,
        "role": "domaine organisationnel (parent) — alignement relaxed, sosies",
        "decisions": [
          "D136"
        ],
        "normes": []
      },
      {
        "id": "one_click",
        "nom": "One-Click Unsubscribe (POST)",
        "sens": "sortant",
        "jalon": 2,
        "role": "première sortie HTTP vers un domaine arbitraire : SSRF à cadrer (Q51)",
        "decisions": [
          "D132"
        ],
        "normes": [
          "RFC8058"
        ]
      },
      {
        "id": "antivirus",
        "nom": "Analyse antivirale (ClamAV ou équivalent)",
        "sens": "entrant",
        "jalon": 2,
        "role": "code malveillant = refus ; indisponible = différer, jamais accepter en silence",
        "decisions": [
          "D139"
        ],
        "normes": []
      }
    ],
    "normes": [
      {
        "id": "RFC5321",
        "type": "rfc",
        "nom": "SMTP",
        "engage": "enveloppe ≠ en-têtes (Return-Path vs From : règle A5) ; codes 4xx/5xx ; la partie locale est théoriquement sensible à la casse, en pratique jamais (local_cmp, D136)"
      },
      {
        "id": "RFC5322",
        "type": "rfc",
        "nom": "Internet Message Format",
        "engage": "Message-ID, In-Reply-To, References (D55) ; un nom de champ ne contient pas de « / » (chapitre 14) ; le nom affiché n'est pas authentifié (D126)"
      },
      {
        "id": "RFC6409",
        "type": "rfc",
        "nom": "Message Submission",
        "engage": "port 587, authentification vers le relais (D114)"
      },
      {
        "id": "RFC6531",
        "type": "rfc",
        "nom": "SMTPUTF8",
        "engage": "adresses internationalisées : stocker punycode ET unicode (D136)"
      },
      {
        "id": "RFC2045",
        "type": "rfc",
        "nom": "MIME — format des corps",
        "engage": "base64 et ses +37 % (D69/D70) ; décoder avant stockage"
      },
      {
        "id": "RFC2046",
        "type": "rfc",
        "nom": "MIME — types de média",
        "engage": "multipart : la moitié des messages (chapitre 15) ; alternative ≠ pièce jointe"
      },
      {
        "id": "RFC2047",
        "type": "rfc",
        "nom": "MIME — en-têtes encodés",
        "engage": "sujets et noms affichés encodés : décoder à l'ingestion, une seule fois"
      },
      {
        "id": "RFC2183",
        "type": "rfc",
        "nom": "Content-Disposition",
        "engage": "inline vs attachment, content-id des images incluses (C09)"
      },
      {
        "id": "RFC2231",
        "type": "rfc",
        "nom": "Paramètres MIME encodés",
        "engage": "filename*=UTF-8''… : le nom de fichier n'est pas toujours dans filename= (chapitre 14)"
      },
      {
        "id": "RFC3501",
        "type": "rfc",
        "nom": "IMAP4rev1",
        "engage": "UID, UIDVALIDITY (D43), IDLE une connexion par dossier (D48, D74)"
      },
      {
        "id": "RFC9051",
        "type": "rfc",
        "nom": "IMAP4rev2",
        "engage": "idem, version courante"
      },
      {
        "id": "RFC2033",
        "type": "rfc",
        "nom": "LMTP",
        "engage": "un code retour PAR destinataire ; un 5xx à tort transforme une panne en courrier perdu (V2)"
      },
      {
        "id": "RFC3461",
        "type": "rfc",
        "nom": "DSN — extension SMTP",
        "engage": "NOTIFY=SUCCESS, ENVID (Original-Envelope-Id) pour corréler (D119)"
      },
      {
        "id": "RFC3464",
        "type": "rfc",
        "nom": "DSN — format",
        "engage": "multipart/report, Action, Status : la nature service (D130), le 550 qui fait passer reponse_possible à non (D131)"
      },
      {
        "id": "RFC3834",
        "type": "rfc",
        "nom": "Réponses automatiques",
        "engage": "Auto-Submitted ; Reply-To: <> = ne répondez pas (D131) ; garde-fous de toute réponse automatique (D113)"
      },
      {
        "id": "RFC2369",
        "type": "rfc",
        "nom": "En-têtes List-*",
        "engage": "List-Unsubscribe, List-Post : détection de la nature liste (D130), désabonnement (D132)"
      },
      {
        "id": "RFC2919",
        "type": "rfc",
        "nom": "List-Id",
        "engage": "la clé de regroupement de la branche Abonnements (D133) — stable là où le From varie"
      },
      {
        "id": "RFC8058",
        "type": "rfc",
        "nom": "One-Click Unsubscribe",
        "engage": "List-Unsubscribe-Post ; POST serveur→serveur = SSRF à cadrer (Q51)"
      },
      {
        "id": "RFC7208",
        "type": "rfc",
        "nom": "SPF",
        "engage": "vérifiable seulement avec l'IP de connexion : NULL en V1 (D26), jamais fail par défaut ; SRS sur les renvois (D120)"
      },
      {
        "id": "RFC6376",
        "type": "rfc",
        "nom": "DKIM",
        "engage": "revérifiable grâce à la reconstruction à l'octet (D25) ; liaison PJ avec encodage de partie"
      },
      {
        "id": "RFC7489",
        "type": "rfc",
        "nom": "DMARC",
        "engage": "alignement strict/relaxed (domaine organisationnel, D136) ; politique publiée = le geste (D139) ; rapports rua, _report._dmarc pour la collecte inter-domaines (D115)"
      },
      {
        "id": "RFC8617",
        "type": "rfc",
        "nom": "ARC",
        "engage": "annule un échec DMARC légitime (A9) — obligatoire avant tout p=reject (D139)"
      },
      {
        "id": "RFC5228",
        "type": "rfc",
        "nom": "Sieve",
        "engage": "ce qu'on REMPLACE (D74) ; ce qu'il faut savoir lire pour importer un script existant"
      },
      {
        "id": "RFC4155",
        "type": "rfc",
        "nom": "mbox",
        "engage": "import d'historique (D107)"
      },
      {
        "id": "RFC9110",
        "type": "rfc",
        "nom": "HTTP Semantics",
        "engage": "404 et non 403 hors portée (D108) ; caches"
      },
      {
        "id": "RFC8259",
        "type": "rfc",
        "nom": "JSON",
        "engage": "contrat d'API et champs json du modèle"
      },
      {
        "id": "RFC3986",
        "type": "rfc",
        "nom": "URI",
        "engage": "normalisation des List-Unsubscribe (D133), liens dans le corps (C1, C2)"
      },
      {
        "id": "RFC6749",
        "type": "rfc",
        "nom": "OAuth 2.0",
        "engage": "SSO ; jetons opaques et non JWT auto-porteurs (chapitre 05)"
      },
      {
        "id": "RFC6750",
        "type": "rfc",
        "nom": "Bearer Token",
        "engage": "transport du jeton d'API"
      },
      {
        "id": "RFC6455",
        "type": "rfc",
        "nom": "WebSocket",
        "engage": "temps réel (D125) — ou SSE"
      },
      {
        "id": "RFC4918",
        "type": "rfc",
        "nom": "WebDAV",
        "engage": "pièce jointe par lien via Nextcloud (D111)"
      },
      {
        "id": "RFC7480",
        "type": "rfc",
        "nom": "RDAP",
        "engage": "âge d'enregistrement d'un domaine (B5), optionnel"
      },
      {
        "id": "RFC3339",
        "type": "rfc",
        "nom": "Horodatages",
        "engage": "toutes les dates de l'API en RFC 3339 / ISO 8601, avec fuseau ; trois dates par message (C09)"
      },
      {
        "id": "RFC5424",
        "type": "rfc",
        "nom": "Syslog",
        "engage": "lecture du journal du MTA (queue_id, status=) — D119"
      },
      {
        "id": "PSL",
        "type": "referentiel",
        "nom": "Public Suffix List",
        "engage": "domaine organisationnel (parent_id, D136) — à embarquer et mettre à jour"
      },
      {
        "id": "RGPD",
        "type": "reglementaire",
        "nom": "Règlement général sur la protection des données",
        "engage": "effacement (ordre de priorité D104 : gel > conservation légale > effacement > rétention > corbeille) ; journal de lecture = donnée personnelle (D54, D59) ; IBAN jamais recopié en clair (D129) ; aucun traceur chargé (D105)"
      },
      {
        "id": "NIKON",
        "type": "jurisprudence",
        "nom": "Cass. soc. 2 oct. 2001 (Nikon) et suite",
        "engage": "un message identifié comme personnel échappe au contrôle de l'employeur : le dossier Personnel hors accès administrateur (D134)"
      },
      {
        "id": "LCEN",
        "type": "reglementaire",
        "nom": "Conservation des données de connexion / secret des correspondances",
        "engage": "le journal (D54) est une trace d'accès, pas un contenu ; l'administrateur qui lit est tracé (D38)"
      },
      {
        "id": "ZERO_TRACKER",
        "type": "referentiel",
        "nom": "Affichage sûr",
        "engage": "aucune image distante sans geste, aucun accusé de lecture, HTML assaini à l'affichage (D105) ; désabonnement jamais automatique (D132)"
      }
    ],
    "routes": [
      {
        "methode": "GET",
        "chemin": "/api/v1/messages",
        "role": "liste paginée par curseur : dossier, filtre, sens, statut, tri",
        "portee": "boîtes du jeton",
        "entites": [
          "comm",
          "rattachement"
        ],
        "etat": "maquettée",
        "decisions": [
          "D13",
          "D36"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/messages/{id}",
        "role": "un message : tronc + fille, participants, tags, pièces jointes, analyse",
        "portee": "rattachement dans les boîtes du jeton",
        "entites": [
          "comm",
          "comm_email",
          "participant",
          "analyse"
        ],
        "etat": "maquettée",
        "decisions": [
          "D138"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/messages",
        "role": "composer et envoyer, ou enregistrer un brouillon ; internes livrés en base, externes remis au relais",
        "portee": "identité de la boîte",
        "entites": [
          "comm",
          "envoi",
          "envoi_destinataire"
        ],
        "etat": "maquettée",
        "decisions": [
          "D12",
          "D99",
          "D114"
        ],
        "question": "Q08"
      },
      {
        "methode": "PATCH",
        "chemin": "/api/v1/messages/{id}/rattachement",
        "role": "lu, statut, sortie, dossier, drapeau, personnel — l'état PAR COMPTE/BOÎTE",
        "portee": "le rattachement du jeton",
        "entites": [
          "rattachement"
        ],
        "etat": "maquettée",
        "decisions": [
          "D36",
          "D41",
          "D93",
          "D134"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/messages/{id}/original",
        "role": "le .eml reconstruit à l'octet",
        "portee": "idem",
        "entites": [
          "comm_email",
          "blob"
        ],
        "etat": "décidée",
        "decisions": [
          "D25"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/messages/{id}/tags",
        "role": "poser un tag (source = le jeton : manuel, ou application)",
        "portee": "axe autorisé au jeton (ACL d'axe)",
        "entites": [
          "comm_tag"
        ],
        "etat": "décidée",
        "decisions": [
          "D17",
          "D18",
          "D19"
        ]
      },
      {
        "methode": "DELETE",
        "chemin": "/api/v1/messages/{id}/tags/{tag}",
        "role": "retirer un tag — Q34 si posé par un connecteur",
        "portee": "idem",
        "entites": [
          "comm_tag"
        ],
        "etat": "hypothèse",
        "question": "Q34"
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/messages/{id}/notes",
        "role": "note interne d'équipe",
        "portee": "membre de la boîte",
        "entites": [
          "note"
        ],
        "etat": "décidée",
        "decisions": [
          "D101"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/messages/{id}/transfert",
        "role": "transfert par référence (interne) ou encapsulé (externe)",
        "portee": "",
        "entites": [
          "comm",
          "envoi"
        ],
        "etat": "décidée",
        "decisions": [
          "D58",
          "D66"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/recherche",
        "role": "plein texte, zone active par défaut, portée du jeton",
        "portee": "boîtes du jeton",
        "entites": [
          "comm"
        ],
        "etat": "décidée",
        "decisions": [
          "D34"
        ],
        "conseils": [
          "C05"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/arborescence",
        "role": "les axes et leurs valeurs avec compteurs — UNE passe",
        "portee": "",
        "entites": [
          "axe",
          "tag"
        ],
        "etat": "décidée",
        "decisions": [
          "D77",
          "D78"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/correspondants/{id}/echanges",
        "role": "toute la communication avec ce tiers, tous canaux — le composant embarquable",
        "portee": "jeton à portée étroite (un tiers)",
        "entites": [
          "comm",
          "correspondant"
        ],
        "etat": "décidée",
        "decisions": [
          "D108",
          "D138"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/adresses/{id}/validation",
        "role": "marquer fiable, avec portée ; refusé si le message de référence n'est pas aligné",
        "portee": "boîte, ou domaine pour un gestionnaire",
        "entites": [
          "adresse",
          "journal"
        ],
        "etat": "décidée",
        "decisions": [
          "D137"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/listes/{list_id}/desabonnement",
        "role": "one-click ou mailto: — jamais automatique",
        "portee": "boîte (collectif)",
        "entites": [
          "comm_email",
          "journal"
        ],
        "etat": "décidée",
        "decisions": [
          "D132"
        ],
        "question": "Q51"
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/quarantaine",
        "role": "ce qui n'est pas arrivé, visible du destinataire",
        "portee": "boîtes du jeton",
        "entites": [
          "rattachement",
          "analyse"
        ],
        "etat": "décidée",
        "decisions": [
          "D71"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/quarantaine/{id}/liberer",
        "role": "libérer — enseigne",
        "portee": "",
        "entites": [
          "rattachement"
        ],
        "etat": "décidée",
        "decisions": [
          "D91"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/envois",
        "role": "cycle de vie des envois, par destinataire",
        "portee": "",
        "entites": [
          "envoi",
          "envoi_destinataire"
        ],
        "etat": "décidée",
        "decisions": [
          "D99"
        ]
      },
      {
        "methode": "DELETE",
        "chemin": "/api/v1/envois/{id}",
        "role": "annuler un envoi programmé avant l'heure",
        "portee": "auteur",
        "entites": [
          "envoi"
        ],
        "etat": "décidée",
        "decisions": [
          "D99"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/dmarc",
        "role": "délivrabilité : rapports agrégés par domaine",
        "portee": "gestionnaire de domaine",
        "entites": [
          "dmarc_rapport",
          "dmarc_ligne"
        ],
        "etat": "décidée",
        "decisions": [
          "D100"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/parametres",
        "role": "la cascade résolue pour la portée demandée, avec l'origine et le verrou",
        "portee": "",
        "entites": [
          "parametre"
        ],
        "etat": "décidée",
        "decisions": [
          "D106",
          "D117"
        ]
      },
      {
        "methode": "PUT",
        "chemin": "/api/v1/parametres",
        "role": "régler ou verrouiller",
        "portee": "selon le niveau",
        "entites": [
          "parametre",
          "journal"
        ],
        "etat": "décidée",
        "decisions": [
          "D106",
          "D117"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/dechetterie",
        "role": "métadonnées des détachés, par domaine — jamais le personnel",
        "portee": "administrateur de domaine",
        "entites": [
          "rattachement"
        ],
        "etat": "décidée",
        "decisions": [
          "D121",
          "D134"
        ]
      },
      {
        "methode": "POST",
        "chemin": "/api/v1/evenements/abonnements",
        "role": "webhooks sortants, rejouables",
        "portee": "application",
        "entites": [
          "application"
        ],
        "etat": "maquettée",
        "decisions": [
          "D86"
        ]
      },
      {
        "methode": "GET",
        "chemin": "/api/v1/groupes/{id}/messages",
        "role": "le fil d'un groupe, avec la position de lecture",
        "portee": "membre",
        "entites": [
          "comm_groupe",
          "lecture_groupe"
        ],
        "etat": "décidée",
        "decisions": [
          "D122",
          "D124"
        ]
      }
    ],
    "fonctionnalites": [
      {
        "id": "F001",
        "libelle": "Ingestion IMAP des boîtes administrées",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D46",
          "D49"
        ],
        "questions": []
      },
      {
        "id": "F002",
        "libelle": "Stockage compressé zstd, hors base",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D05",
          "D07"
        ],
        "questions": []
      },
      {
        "id": "F003",
        "libelle": "Déduplication des messages identiques",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D10",
          "D64"
        ],
        "questions": []
      },
      {
        "id": "F004",
        "libelle": "Détachement et déduplication des pièces jointes",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D11",
          "D24"
        ],
        "questions": []
      },
      {
        "id": "F005",
        "libelle": "Verdicts DKIM / SPF figés à l'ingestion",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D26",
          "D27"
        ],
        "questions": []
      },
      {
        "id": "F006",
        "libelle": "Quarantaine et apprentissage anti-spam",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D71",
          "D91"
        ],
        "questions": []
      },
      {
        "id": "F007",
        "libelle": "Livraison LMTP (sans Dovecot)",
        "domaine": "Réception et stockage",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D42",
          "D45"
        ],
        "questions": []
      },
      {
        "id": "F008",
        "libelle": "Module de stockage Dovecot",
        "domaine": "Réception et stockage",
        "jalon": 2,
        "etat": "à trancher",
        "decisions": [],
        "questions": [
          "Q24"
        ]
      },
      {
        "id": "F009",
        "libelle": "Import d'historique (IMAP, mbox, PST)",
        "domaine": "Réception et stockage",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D107"
        ],
        "questions": []
      },
      {
        "id": "F010",
        "libelle": "Axes calés sur une arborescence IMAP réelle",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D16"
        ],
        "questions": []
      },
      {
        "id": "F011",
        "libelle": "Tags par axes, paramétrables, avec ACL",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D02",
          "D16",
          "D18"
        ],
        "questions": []
      },
      {
        "id": "F012",
        "libelle": "Dossiers virtuels = filtres enregistrés",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D75",
          "D77"
        ],
        "questions": []
      },
      {
        "id": "F013",
        "libelle": "Dossiers utilisateur classiques",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D51"
        ],
        "questions": []
      },
      {
        "id": "F014",
        "libelle": "Recherche plein texte sur la zone active",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D34"
        ],
        "questions": []
      },
      {
        "id": "F015",
        "libelle": "Recherche dans les pièces jointes (nom)",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D96"
        ],
        "questions": []
      },
      {
        "id": "F016",
        "libelle": "Moteur de filtres (remplace Sieve)",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D74"
        ],
        "questions": []
      },
      {
        "id": "F017",
        "libelle": "Nature du message : diffusion, notification, service",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D130"
        ],
        "questions": []
      },
      {
        "id": "F018",
        "libelle": "Newsletters hors de la file, factures dedans",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D130",
          "D13"
        ],
        "questions": []
      },
      {
        "id": "F019",
        "libelle": "Un dossier par liste, déduit du corpus",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D133",
          "D77"
        ],
        "questions": []
      },
      {
        "id": "F020",
        "libelle": "Archivage par sortie de file",
        "domaine": "Classement et recherche",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D14",
          "D30"
        ],
        "questions": []
      },
      {
        "id": "F021",
        "libelle": "Statut de traitement (workflow)",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D93"
        ],
        "questions": []
      },
      {
        "id": "F022",
        "libelle": "Onglets multiples, restaurés",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [],
        "questions": []
      },
      {
        "id": "F023",
        "libelle": "Composition : nouveau, réponse, transfert",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D58"
        ],
        "questions": [
          "Q26"
        ]
      },
      {
        "id": "F024",
        "libelle": "Transfert par référence, sans copie",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D58",
          "D67"
        ],
        "questions": []
      },
      {
        "id": "F025",
        "libelle": "Envoi interne hors SMTP",
        "domaine": "Travail au quotidien",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D12"
        ],
        "questions": []
      },
      {
        "id": "F026",
        "libelle": "Groupes de discussion par service",
        "domaine": "Travail au quotidien",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D122"
        ],
        "questions": [
          "Q46"
        ]
      },
      {
        "id": "F027",
        "libelle": "Messages de groupe stockés en base, pas en fichiers",
        "domaine": "Travail au quotidien",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D123"
        ],
        "questions": []
      },
      {
        "id": "F028",
        "libelle": "Position de lecture par membre",
        "domaine": "Travail au quotidien",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D124"
        ],
        "questions": []
      },
      {
        "id": "F029",
        "libelle": "Temps réel (arrivée, prise en charge)",
        "domaine": "Travail au quotidien",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D125"
        ],
        "questions": []
      },
      {
        "id": "F030",
        "libelle": "File de travail partagée sur boîte commune",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "à trancher",
        "decisions": [],
        "questions": [
          "Q35"
        ]
      },
      {
        "id": "F031",
        "libelle": "Note interne d'équipe, jamais transmise",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D101"
        ],
        "questions": []
      },
      {
        "id": "F032",
        "libelle": "Identités d'expédition et signatures",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D102"
        ],
        "questions": []
      },
      {
        "id": "F033",
        "libelle": "Boîte partagée : « au nom de » optionnel",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D116"
        ],
        "questions": []
      },
      {
        "id": "F034",
        "libelle": "Réponses types partagées",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D102"
        ],
        "questions": []
      },
      {
        "id": "F035",
        "libelle": "Réveil et échéance sur un message",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D103"
        ],
        "questions": []
      },
      {
        "id": "F036",
        "libelle": "Complétion des destinataires",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D109"
        ],
        "questions": []
      },
      {
        "id": "F037",
        "libelle": "Impression et export PDF",
        "domaine": "Travail au quotidien",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D110"
        ],
        "questions": []
      },
      {
        "id": "F038",
        "libelle": "Boîtes communes, alias = vraies boîtes",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D38",
          "D39"
        ],
        "questions": []
      },
      {
        "id": "F039",
        "libelle": "ACL par email, partage révocable",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D57",
          "D60"
        ],
        "questions": []
      },
      {
        "id": "F040",
        "libelle": "Journal d'activité (qui a lu, traité)",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D54",
          "D56"
        ],
        "questions": []
      },
      {
        "id": "F041",
        "libelle": "Rôles d'administration",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D72"
        ],
        "questions": []
      },
      {
        "id": "F042",
        "libelle": "Authentification par jeton, SSO possible",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D63"
        ],
        "questions": []
      },
      {
        "id": "F043",
        "libelle": "Paramétrage en cascade, verrouillable",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D106"
        ],
        "questions": []
      },
      {
        "id": "F044",
        "libelle": "Interface responsive (mobile)",
        "domaine": "Collaboration et accès",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D112"
        ],
        "questions": []
      },
      {
        "id": "F045",
        "libelle": "Accès IMAP en repli assumé",
        "domaine": "Collaboration et accès",
        "jalon": 2,
        "etat": "à trancher",
        "decisions": [
          "D112"
        ],
        "questions": [
          "Q24"
        ]
      },
      {
        "id": "F046",
        "libelle": "API REST — hypothèse de travail",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "à trancher",
        "decisions": [],
        "questions": [
          "Q07",
          "Q08"
        ]
      },
      {
        "id": "F047",
        "libelle": "Contexte métier affiché sans être stocké",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D19",
          "D21"
        ],
        "questions": []
      },
      {
        "id": "F048",
        "libelle": "Applications connectées, jetons, portée",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D20",
          "D37"
        ],
        "questions": []
      },
      {
        "id": "F049",
        "libelle": "Événements sortants (webhooks) rejouables",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D86"
        ],
        "questions": []
      },
      {
        "id": "F050",
        "libelle": "Mise en cache du contexte métier",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "à trancher",
        "decisions": [],
        "questions": [
          "Q31"
        ]
      },
      {
        "id": "F051",
        "libelle": "SDK par langage (PHP, puis JS)",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D108"
        ],
        "questions": []
      },
      {
        "id": "F052",
        "libelle": "Composants d'interface embarquables",
        "domaine": "Intégration",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D108"
        ],
        "questions": []
      },
      {
        "id": "F053",
        "libelle": "Cycle de vie de l'envoi, par destinataire",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D99"
        ],
        "questions": []
      },
      {
        "id": "F054",
        "libelle": "Envoi programmé, annulable avant l'heure",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D99"
        ],
        "questions": []
      },
      {
        "id": "F055",
        "libelle": "Retours de non-remise corrélés (DSN)",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D99",
          "D66"
        ],
        "questions": []
      },
      {
        "id": "F056",
        "libelle": "Rapports DMARC agrégés, délivrabilité",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D100"
        ],
        "questions": []
      },
      {
        "id": "F057",
        "libelle": "Absence et réponse auto, renvoi sur collègue",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D113",
          "D74"
        ],
        "questions": []
      },
      {
        "id": "F058",
        "libelle": "Pièce jointe par lien de téléchargement",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D111"
        ],
        "questions": []
      },
      {
        "id": "F059",
        "libelle": "Émission via le relais du client",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D114"
        ],
        "questions": []
      },
      {
        "id": "F060",
        "libelle": "Retour d'enveloppe unique (VERP)",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D119"
        ],
        "questions": []
      },
      {
        "id": "F061",
        "libelle": "Réécriture d'enveloppe (SRS) sur les renvois",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D120"
        ],
        "questions": []
      },
      {
        "id": "F062",
        "libelle": "Journal du MTA : sort connu en secondes",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D119"
        ],
        "questions": []
      },
      {
        "id": "F063",
        "libelle": "Boîte de collecte DMARC + dépouillement",
        "domaine": "Émission et délivrabilité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D115"
        ],
        "questions": []
      },
      {
        "id": "F064",
        "libelle": "Adresse non répondable apprise d'un DSN 5xx",
        "domaine": "Émission et délivrabilité",
        "jalon": 2,
        "etat": "maquetté",
        "decisions": [
          "D131",
          "D119"
        ],
        "questions": []
      },
      {
        "id": "F065",
        "libelle": "Désabonnement en un clic (List-Unsubscribe)",
        "domaine": "Émission et délivrabilité",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D132"
        ],
        "questions": [
          "Q51"
        ]
      },
      {
        "id": "F066",
        "libelle": "HTML assaini à l'affichage, pas à l'ingestion",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D105",
          "D25"
        ],
        "questions": []
      },
      {
        "id": "F067",
        "libelle": "Images externes bloquées, proxy serveur",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D105"
        ],
        "questions": []
      },
      {
        "id": "F068",
        "libelle": "Bannière « expéditeur externe »",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D105"
        ],
        "questions": []
      },
      {
        "id": "F069",
        "libelle": "Avertir avant de répondre à un « noreply@ »",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D131"
        ],
        "questions": []
      },
      {
        "id": "F070",
        "libelle": "Réorienter vers un contact connu du domaine",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D131"
        ],
        "questions": []
      },
      {
        "id": "F071",
        "libelle": "Aucun accusé de lecture émis ni demandé",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D105"
        ],
        "questions": []
      },
      {
        "id": "F072",
        "libelle": "Rétention par type de contenu et par boîte",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D104"
        ],
        "questions": []
      },
      {
        "id": "F073",
        "libelle": "Gel sur litige — prime sur toute purge",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D104"
        ],
        "questions": []
      },
      {
        "id": "F074",
        "libelle": "Suppression = détachement, déchetterie",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D118"
        ],
        "questions": []
      },
      {
        "id": "F075",
        "libelle": "Déchetterie : métadonnées, restauration à l'origine",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D121"
        ],
        "questions": []
      },
      {
        "id": "F076",
        "libelle": "Verrouillage : jamais le poste de travail",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D117"
        ],
        "questions": []
      },
      {
        "id": "F077",
        "libelle": "Expéditeur normalisé sur le carnet",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D126"
        ],
        "questions": []
      },
      {
        "id": "F078",
        "libelle": "Signal d'usurpation par nom (règle B1)",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D128"
        ],
        "questions": []
      },
      {
        "id": "F079",
        "libelle": "Table domaine + adresse éclatée (local@domaine)",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D136"
        ],
        "questions": []
      },
      {
        "id": "F080",
        "libelle": "Pivot comm partitionné par canal",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D138"
        ],
        "questions": []
      },
      {
        "id": "F081",
        "libelle": "Refus, quarantaine ou alerte selon le motif",
        "domaine": "Sécurité et conformité",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D139"
        ],
        "questions": []
      },
      {
        "id": "F082",
        "libelle": "Poids et seuils du score",
        "domaine": "Sécurité et conformité",
        "jalon": 2,
        "etat": "à trancher",
        "decisions": [],
        "questions": [
          "Q55"
        ]
      },
      {
        "id": "F083",
        "libelle": "Indicateur d'expéditeur fiable, jamais sans alignement",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D137"
        ],
        "questions": []
      },
      {
        "id": "F084",
        "libelle": "Validation humaine d'un expéditeur, avec portée",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D137",
          "D106"
        ],
        "questions": []
      },
      {
        "id": "F085",
        "libelle": "Défi anti-robot (« je ne suis pas un robot »)",
        "domaine": "Sécurité et conformité",
        "jalon": 0,
        "etat": "en pause",
        "decisions": [],
        "questions": [
          "Q54"
        ]
      },
      {
        "id": "F086",
        "libelle": "Catalogue de règles anti-usurpation",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D127",
          "D128"
        ],
        "questions": []
      },
      {
        "id": "F087",
        "libelle": "Cohérence IBAN / tiers de l'ERP",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D129"
        ],
        "questions": []
      },
      {
        "id": "F088",
        "libelle": "Refuser sur un fait, quarantaine sur une présomption, alerte sur un indice",
        "domaine": "Sécurité et conformité",
        "jalon": 1,
        "etat": "décidé",
        "decisions": [
          "D139"
        ],
        "questions": []
      },
      {
        "id": "F089",
        "libelle": "Analyse des traceurs d'images (option)",
        "domaine": "Sécurité et conformité",
        "jalon": 5,
        "etat": "à venir",
        "decisions": [
          "D105"
        ],
        "questions": []
      },
      {
        "id": "F090",
        "libelle": "Contacts — lecture du correspondant",
        "domaine": "Suite collaborative",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D35",
          "D95b"
        ],
        "questions": []
      },
      {
        "id": "F091",
        "libelle": "Tâches, contacts, cloud, CRM par connecteur",
        "domaine": "Suite collaborative",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [
          "D94"
        ],
        "questions": []
      },
      {
        "id": "F092",
        "libelle": "Contacts — carnet d'adresses",
        "domaine": "Suite collaborative",
        "jalon": 3,
        "etat": "à venir",
        "decisions": [
          "D95b"
        ],
        "questions": []
      },
      {
        "id": "F093",
        "libelle": "Tâches internes",
        "domaine": "Suite collaborative",
        "jalon": 3,
        "etat": "à venir",
        "decisions": [
          "D95b"
        ],
        "questions": []
      },
      {
        "id": "F094",
        "libelle": "Cloud interne",
        "domaine": "Suite collaborative",
        "jalon": 3,
        "etat": "à venir",
        "decisions": [
          "D95b"
        ],
        "questions": []
      },
      {
        "id": "F095",
        "libelle": "CRM interne",
        "domaine": "Suite collaborative",
        "jalon": 3,
        "etat": "à venir",
        "decisions": [
          "D95b"
        ],
        "questions": [
          "Q39"
        ]
      },
      {
        "id": "F096",
        "libelle": "E-mail",
        "domaine": "Canaux",
        "jalon": 1,
        "etat": "maquetté",
        "decisions": [],
        "questions": []
      },
      {
        "id": "F097",
        "libelle": "Messagerie interne",
        "domaine": "Canaux",
        "jalon": 2,
        "etat": "décidé",
        "decisions": [
          "D12"
        ],
        "questions": []
      },
      {
        "id": "F098",
        "libelle": "SMS",
        "domaine": "Canaux",
        "jalon": 4,
        "etat": "à venir",
        "decisions": [
          "D97"
        ],
        "questions": []
      },
      {
        "id": "F099",
        "libelle": "WhatsApp",
        "domaine": "Canaux",
        "jalon": 4,
        "etat": "à venir",
        "decisions": [
          "D97"
        ],
        "questions": []
      },
      {
        "id": "F100",
        "libelle": "Téléphonie",
        "domaine": "Canaux",
        "jalon": 4,
        "etat": "à venir",
        "decisions": [
          "D97"
        ],
        "questions": []
      }
    ],
    "jalons": [
      {
        "id": "V1",
        "titre": "Le moteur, l'API, le webmail",
        "etat": "en conception",
        "note": "Le produit est utilisable seul : une messagerie qui classe et qui se branche.",
        "contenu": [
          "Ingestion IMAP en lecture seule sur le domaine pilote",
          "Stockage zstd hors base, index PostgreSQL",
          "Déduplication des messages et des pièces jointes",
          "Tags par axes, dossiers virtuels, archivage",
          "Webmail : lecture, composition, statut de traitement",
          "API et applications connectées (Dolibarr, Redmine, Nextcloud)",
          "Suite collaborative : par connecteur, ou absente",
          "Émission suivie : état par destinataire, envoi programmé, DSN corrélés",
          "Délivrabilité : rapports DMARC agrégés",
          "Affichage sûr, rétention et gel, paramétrage en cascade",
          "Import d'historique, SDK et composants embarquables",
          "Nature du message (humain, liste, notification, service) — la file de travail ne se remplit plus de bruit",
          "Branche Abonnements : un dossier par liste, déduit du corpus",
          "Table domaine, adresse éclatée, indicateur de confiance jamais sans alignement",
          "Pivot comm partitionné par canal — la séparation accélère le chemin chaud",
          "Dossier Personnel par défaut, hors accès administrateur",
          "Ordre des dossiers réglé par l'utilisateur, jamais par un préfixe dans le nom",
          "Alerte et quarantaine selon trois axes (le refus attend la V2)"
        ]
      },
      {
        "id": "V2",
        "titre": "La livraison",
        "etat": "cadré",
        "note": "AtomBox cesse de lire les boîtes des autres pour recevoir directement.",
        "contenu": [
          "Livraison LMTP sans passer par Dovecot",
          "Messagerie interne hors SMTP",
          "Module de stockage Dovecot (à trancher — Q24)",
          "Refus à la réception : p=reject non aligné, code malveillant — avec ARC, sans quoi on rejette les listes",
          "Antivirus sur le chemin d'ingestion ; indisponible = différer",
          "Désabonnement en un clic (mailto: d'abord, POST après cadrage du SSRF — Q51)",
          "Adresse non répondable apprise d'un DSN 5xx"
        ]
      },
      {
        "id": "V3",
        "titre": "Les composants internes",
        "etat": "cible",
        "note": "AtomBox devient la suite collaborative. Le CRM est le morceau le plus ambitieux : à chiffrer comme un produit à part entière.",
        "contenu": [
          "Carnet de contacts",
          "Tâches",
          "Cloud (fichiers)",
          "CRM"
        ]
      },
      {
        "id": "V4",
        "titre": "Les canaux",
        "etat": "horizon",
        "note": "AtomBox cesse d'être une messagerie pour devenir un hub de communication. Le pivot reste le correspondant — c'est lui qui unifie un mail, un SMS et un appel.",
        "contenu": [
          "SMS",
          "WhatsApp Business",
          "Téléphonie (CTI, journal d'appels)"
        ]
      },
      {
        "id": "V5",
        "titre": "L'horizon — et il n'est pas un plan",
        "etat": "réserve",
        "note": "Une seule entrée, et c'est volontaire : ce jalon existe pour empêcher de faire l'analyse de traceurs en V1 « puisqu'on y est ». Un jalon qui ne contient qu'une ligne est un jalon honnête ; le remplir d'idées serait l'erreur que le phasage sert justement à éviter.",
        "contenu": [
          "Analyse des images externes : distinguer le contenu du pixel espion (option)"
        ]
      }
    ]
  }
};
})(window.ABX = window.ABX || {});
