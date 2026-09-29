-- SCHÉMA ATOMBOX — engendré par outils/gen-schema.py depuis le dictionnaire des données.
-- NE PAS ÉDITER : la source est .mmi-pm/docs/dict/*.yml (F114, D154). PostgreSQL ≥ 14 (D027).
-- 40 tables, 88 clés étrangères, 74 index, 9 unicités. Identifiants : uuid v7 engendrés par
-- l'application (D145). Le tronc comm n'est PAS partitionné en V0 : la partition par canal (D138)
-- se pose quand un second canal existe — l'uuid rend la clé indépendante de la partition.

BEGIN;

-- comm — Le TRONC polymorphe : une communication datée, avec un sens et des participants, quel que soit son canal. Port
CREATE TABLE "comm" (
  "comm_id" uuid NOT NULL,
  "type" text NOT NULL,
  "date_recue" timestamptz NOT NULL,
  "date_declaree" timestamptz,
  "date_ingestion" timestamptz NOT NULL,
  "sens" text NOT NULL,
  "sujet" text,
  "sujet_normalise" text,
  "thread_id" uuid,
  "nature" text NOT NULL,
  "from_adresse" text NOT NULL,
  "from_nom" text,
  "taille" bigint NOT NULL,
  "nb_pieces_jointes" bigint NOT NULL,
  "langue" text,
  "est_chiffre" boolean NOT NULL,
  "est_signe" boolean NOT NULL,
  "snippet" text,
  "corps_texte" text,
  CONSTRAINT "pk_comm" PRIMARY KEY ("comm_id"),
  CONSTRAINT "ck_comm_type" CHECK ("type" IN ('email', 'interne', 'groupe', 'sms', 'whatsapp', 'tel')),
  CONSTRAINT "ck_comm_sens" CHECK ("sens" IN ('in', 'out')),
  CONSTRAINT "ck_comm_nature" CHECK ("nature" IN ('humain', 'liste', 'notification', 'service'))
);

-- reinitialisation — Une demande de réinitialisation de mot de passe (D164) : un jeton haché, à usage unique, valable trente minute
CREATE TABLE "reinitialisation" (
  "reinitialisation_id" uuid NOT NULL,
  "compte_id" uuid NOT NULL,
  "jeton_empreinte" text NOT NULL,
  "envoye_a" text NOT NULL,
  "demande_le" timestamptz NOT NULL,
  "expire_le" timestamptz NOT NULL,
  "utilise_le" timestamptz,
  "demande_par_ip" text,
  CONSTRAINT "pk_reinitialisation" PRIMARY KEY ("reinitialisation_id")
);

-- comm_citation — Le lien entre une réponse et le message qu'elle CITE dans son corps (D163). Une relation, jamais une substitut
CREATE TABLE "comm_citation" (
  "comm_citation_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "cite_comm_id" uuid,
  "cite_message_id" text,
  "part_citee" numeric NOT NULL,
  "part_modifiee" numeric NOT NULL,
  "position" text NOT NULL,
  "recette" jsonb,
  "origine" text NOT NULL,
  "detecte_le" timestamptz NOT NULL,
  CONSTRAINT "pk_comm_citation" PRIMARY KEY ("comm_citation_id"),
  CONSTRAINT "ck_comm_citation_position" CHECK ("position" IN ('avant', 'apres', 'intercale')),
  CONSTRAINT "ck_comm_citation_origine" CHECK ("origine" IN ('emission', 'ingestion'))
);

-- comm_email — La fille « email » du tronc : en-têtes, identifiants de fil, verdicts d'authentification, référence du blob, e
CREATE TABLE "comm_email" (
  "comm_id" uuid NOT NULL,
  "message_id" text,
  "in_reply_to" text,
  "references" text,
  "return_path" text,
  "list_id" text,
  "list_unsubscribe" text,
  "headers" text NOT NULL,
  "verdict_spf" text,
  "verdict_dkim" text,
  "verdict_dmarc" text,
  "arc_valide" boolean,
  "blob_ref" text NOT NULL,
  "empreinte" text NOT NULL,
  "structure_mime" jsonb,
  "uid" bigint,
  "uid_validity" bigint,
  "queue_id" text,
  "reponse_possible" text NOT NULL,
  CONSTRAINT "pk_comm_email" PRIMARY KEY ("comm_id"),
  CONSTRAINT "ck_comm_email_verdict_spf" CHECK ("verdict_spf" IN ('pass', 'fail', 'none', 'None')),
  CONSTRAINT "ck_comm_email_verdict_dkim" CHECK ("verdict_dkim" IN ('pass', 'fail', 'none', 'None')),
  CONSTRAINT "ck_comm_email_verdict_dmarc" CHECK ("verdict_dmarc" IN ('pass', 'fail', 'none', 'None')),
  CONSTRAINT "ck_comm_email_reponse_possible" CHECK ("reponse_possible" IN ('oui', 'avertir', 'non'))
);

-- comm_interne — Fille « message interne » (note ou message direct entre comptes), hors SMTP, en base.
CREATE TABLE "comm_interne" (
  "comm_id" uuid NOT NULL,
  "de_compte_id" uuid NOT NULL,
  "a_compte_id" uuid,
  "corps" text NOT NULL,
  CONSTRAINT "pk_comm_interne" PRIMARY KEY ("comm_id")
);

-- comm_groupe — Fille « message de groupe » : chat de service, stocké en base, jamais vers l'extérieur.
CREATE TABLE "comm_groupe" (
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "auteur_compte_id" uuid NOT NULL,
  "corps" text NOT NULL,
  "modifie_le" timestamptz,
  "supprime_le" timestamptz,
  CONSTRAINT "pk_comm_groupe" PRIMARY KEY ("comm_id")
);

-- participant — Une adresse impliquée dans une communication, avec son rôle (from/to/cc/bcc/reply-to), son NOM AFFICHÉ tel que
CREATE TABLE "participant" (
  "comm_id" uuid NOT NULL,
  "role" text NOT NULL,
  "adresse_id" uuid NOT NULL,
  "nom_affiche" text,
  "ordre" bigint NOT NULL,
  CONSTRAINT "pk_participant" PRIMARY KEY ("comm_id", "ordre"),
  CONSTRAINT "ck_participant_role" CHECK ("role" IN ('from', 'to', 'cc', 'bcc', 'reply_to', 'sender'))
);

-- piece_jointe — Une pièce jointe dédupliquée : nom, type déclaré, taille, blob. Le nom appartient au message (liaison), le con
CREATE TABLE "piece_jointe" (
  "piece_jointe_id" uuid NOT NULL,
  "blob_ref" text NOT NULL,
  "type_detecte" text NOT NULL,
  "taille_octets" bigint NOT NULL,
  "blob_origine" text,
  "recompresse_le" timestamptz,
  "nb_references" bigint NOT NULL,
  CONSTRAINT "pk_piece_jointe" PRIMARY KEY ("piece_jointe_id")
);

-- comm_piece_jointe — La liaison message ↔ pièce jointe, qui conserve ordre, encodage de transfert, disposition, content-id et param
CREATE TABLE "comm_piece_jointe" (
  "comm_id" uuid NOT NULL,
  "piece_jointe_id" uuid NOT NULL,
  "ordre" bigint NOT NULL,
  "nom_declare" text,
  "type_declare" text,
  "transfer_encoding" text,
  "disposition" text,
  "content_id" text,
  "parametres" jsonb,
  "renomme_en" text,
  CONSTRAINT "pk_comm_piece_jointe" PRIMARY KEY ("comm_id", "ordre")
);

-- blob — Un contenu binaire adressé par empreinte, compressé zstd, hors base. Compteur de références pour le ramasse-mi
CREATE TABLE "blob" (
  "empreinte" text NOT NULL,
  "taille_octets" bigint NOT NULL,
  "taille_stockee" bigint NOT NULL,
  "compression" text NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "nb_references" bigint NOT NULL,
  "dernier_acces" timestamptz,
  CONSTRAINT "pk_blob" PRIMARY KEY ("empreinte")
);

-- correspondant — Une IDENTITÉ — personne, boîte fonctionnelle, automate, compte interne — qui peut porter plusieurs adresses. C
CREATE TABLE "correspondant" (
  "correspondant_id" uuid NOT NULL,
  "nom_canonique" text NOT NULL,
  "type" text NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "organisation_id" uuid,
  CONSTRAINT "pk_correspondant" PRIMARY KEY ("correspondant_id"),
  CONSTRAINT "ck_correspondant_type" CHECK ("type" IN ('personne', 'fonctionnel', 'automate', 'interne'))
);

-- adresse — Une adresse email = partie locale + référence au domaine. Porte l'adresse complète dénormalisée, la forme norm
CREATE TABLE "adresse" (
  "adresse_id" uuid NOT NULL,
  "local" text NOT NULL,
  "local_cmp" text NOT NULL,
  "local_base" text,
  "domaine_id" uuid NOT NULL,
  "adresse_complete" text NOT NULL,
  "correspondant_id" uuid,
  "lie_le" timestamptz,
  "delie_le" timestamptz,
  "verifie_le" timestamptz,
  "verifie_methode" text,
  "valide_le" timestamptz,
  "valide_par" uuid,
  "valide_portee" text,
  "fiabilite" bigint,
  "fiabilite_calculee_le" timestamptz,
  CONSTRAINT "pk_adresse" PRIMARY KEY ("adresse_id"),
  CONSTRAINT "ck_adresse_valide_portee" CHECK ("valide_portee" IN ('instance', 'domaine', 'compte', 'boite'))
);

-- domaine — Un domaine DNS, avec son domaine organisationnel parent (Public Suffix List). Porte ce qui appartient au domai
CREATE TABLE "domaine" (
  "domaine_id" uuid NOT NULL,
  "nom_ascii" text NOT NULL,
  "nom_unicode" text NOT NULL,
  "parent_id" uuid,
  "heberge_par_nous" boolean NOT NULL,
  "politique_dmarc" text,
  "politique_lue_le" timestamptz,
  "sosie_de" uuid,
  "enregistre_le" date,
  "plateforme" text,
  "valide_le" timestamptz,
  "valide_par" uuid,
  "valide_portee" text,
  "fiabilite" bigint,
  CONSTRAINT "pk_domaine" PRIMARY KEY ("domaine_id"),
  CONSTRAINT "ck_domaine_politique_dmarc" CHECK ("politique_dmarc" IN ('none', 'quarantine', 'reject')),
  CONSTRAINT "ck_domaine_valide_portee" CHECK ("valide_portee" IN ('instance', 'domaine', 'compte', 'boite'))
);

-- identite — Ce SOUS QUOI un compte écrit depuis une boîte : nom affiché, adresse, Reply-To, signature. « Au nom de » optio
CREATE TABLE "identite" (
  "identite_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "nom_affiche" text NOT NULL,
  "adresse_id" uuid NOT NULL,
  "reply_to" text,
  "signature" text,
  "au_nom_de" boolean NOT NULL,
  "par_defaut" boolean NOT NULL,
  CONSTRAINT "pk_identite" PRIMARY KEY ("identite_id")
);

-- compte — Une personne qui se connecte. Est une identité interne (D061). Porte ses préférences personnelles (ordre des d
CREATE TABLE "compte" (
  "compte_id" uuid NOT NULL,
  "login" text NOT NULL,
  "nom" text NOT NULL,
  "mot_de_passe_empreinte" text,
  "email_secours" text,
  "correspondant_id" uuid,
  "actif" boolean NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "desactive_le" timestamptz,
  "preferences" jsonb,
  "langue" text,
  "fuseau" text,
  CONSTRAINT "pk_compte" PRIMARY KEY ("compte_id")
);

-- boite — Une adresse de réception administrée : personnelle, partagée, alias (un alias est une vraie boîte), de collect
CREATE TABLE "boite" (
  "boite_id" uuid NOT NULL,
  "adresse_id" uuid NOT NULL,
  "domaine_id" uuid NOT NULL,
  "type" text NOT NULL,
  "absence" jsonb,
  CONSTRAINT "pk_boite" PRIMARY KEY ("boite_id"),
  CONSTRAINT "ck_boite_type" CHECK ("type" IN ('personnelle', 'partagee', 'alias', 'collecte', 'groupe'))
);

-- rattachement — LE lien entre une communication et une boîte : c'est ici que vit l'ACTE COLLECTIF — le statut de traitement, l
CREATE TABLE "rattachement" (
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "compte_id" uuid,
  "correspondant_id" uuid,
  "repondu_le" timestamptz,
  "transfere_le" timestamptz,
  "status" text NOT NULL,
  "status_at" timestamptz,
  "status_by" uuid,
  "exit_reason" text,
  "processed_at" timestamptz,
  "processed_by" uuid,
  "archived_at" timestamptz,
  "archived_by" uuid,
  "deleted_at" timestamptz,
  "deleted_by" uuid,
  "junk_at" timestamptz,
  "junk_by" uuid,
  "restaurable_jusqu_au" timestamptz,
  "dossier_id" uuid,
  "dossier_origine_id" uuid,
  "uid_imap" bigint,
  "uid_servi" bigint,
  "personnel" boolean NOT NULL,
  "echeance_le" timestamptz,
  "gele" boolean NOT NULL,
  CONSTRAINT "pk_rattachement" PRIMARY KEY ("comm_id", "boite_id"),
  CONSTRAINT "ck_rattachement_status" CHECK ("status" IN ('new', 'todo', 'doing', 'waiting', 'processed')),
  CONSTRAINT "ck_rattachement_exit_reason" CHECK ("exit_reason" IN ('processed', 'archived', 'deleted', 'junk'))
);

-- read_state — LES FAITS DE LECTURE, par personne (D175 § 1) : ouvert quand, revu quand, combien de fois, et le drapeau — per
CREATE TABLE "read_state" (
  "compte_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "opened_at" timestamptz,
  "last_seen_at" timestamptz,
  "open_count" bigint NOT NULL,
  "flagged" boolean NOT NULL,
  CONSTRAINT "pk_read_state" PRIMARY KEY ("compte_id", "comm_id", "boite_id")
);

-- marker — LA DÉCLARATION d'un marqueur (D178) : son code, ce qu'il porte, sa portée, qui peut le poser. Le workflow est 
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
);

-- marker_collective — Un marqueur de portée COLLECTIVE posé sur un message dans une boîte : signé, daté (D178).
CREATE TABLE "marker_collective" (
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "marker_id" uuid NOT NULL,
  "set_at" timestamptz NOT NULL,
  "set_by" uuid,
  "due_at" timestamptz,
  "value" text,
  CONSTRAINT "pk_marker_collective" PRIMARY KEY ("comm_id", "boite_id", "marker_id")
);

-- marker_personal — Un marqueur de portée PERSONNELLE posé par un compte sur un message dans une boîte (D178) : « à revoir », mise
CREATE TABLE "marker_personal" (
  "compte_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "marker_id" uuid NOT NULL,
  "set_at" timestamptz NOT NULL,
  "due_at" timestamptz,
  "value" text,
  CONSTRAINT "pk_marker_personal" PRIMARY KEY ("compte_id", "comm_id", "boite_id", "marker_id")
);

-- acces — Un droit d'un compte sur une boîte (ou une identité), DATÉ : début, fin, rôle, révocation tracée. La trace ne 
CREATE TABLE "acces" (
  "compte_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "role" text NOT NULL,
  "debut" timestamptz NOT NULL,
  "fin" timestamptz,
  "accorde_par" uuid NOT NULL,
  "stands_in_for" uuid,
  "options" jsonb,
  CONSTRAINT "pk_acces" PRIMARY KEY ("compte_id", "boite_id"),
  CONSTRAINT "ck_acces_role" CHECK ("role" IN ('lecteur', 'membre', 'gestionnaire', 'admin_domaine', 'admin_instance'))
);

-- lecture_groupe — Position de lecture d'un compte dans un groupe : dernier message lu, vu le. Trente lignes au lieu de trente-tr
CREATE TABLE "lecture_groupe" (
  "compte_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "dernier_message_lu" uuid,
  "vu_le" timestamptz,
  CONSTRAINT "pk_lecture_groupe" PRIMARY KEY ("compte_id", "boite_id")
);

-- application — Une instance d'application connectée (type de connecteur + instance) : jeton, portée (boîtes/domaines), axes q
CREATE TABLE "application" (
  "application_id" uuid NOT NULL,
  "type_connecteur" text NOT NULL,
  "nom" text NOT NULL,
  "jeton_empreinte" text NOT NULL,
  "portee" jsonb NOT NULL,
  "axes" jsonb,
  "debit_max" bigint,
  "actif" boolean NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "dernier_appel" timestamptz,
  CONSTRAINT "pk_application" PRIMARY KEY ("application_id")
);

-- axe — Une catégorie de tags — un « tag_group » — porteuse d'ACL, déclarée par une application qui en alimente les va
CREATE TABLE "axe" (
  "axe_id" uuid NOT NULL,
  "nom" text NOT NULL,
  "application_id" uuid,
  "acl" jsonb NOT NULL,
  "derive" boolean NOT NULL,
  "ordre" bigint,
  CONSTRAINT "pk_axe" PRIMARY KEY ("axe_id")
);

-- tag — Une valeur d'un axe : une CLÉ stable (l'identifiant chez l'application — 1042, RM2881 — ou le List-Id) et un L
CREATE TABLE "tag" (
  "tag_id" uuid NOT NULL,
  "axe_id" uuid NOT NULL,
  "valeur" text NOT NULL,
  "libelle" text NOT NULL,
  "ref_externe" jsonb,
  "actif" boolean NOT NULL,
  CONSTRAINT "pk_tag" PRIMARY KEY ("tag_id")
);

-- comm_tag — La liaison communication ↔ tag, avec sa SOURCE (quelle application ou quel filtre l'a posée) et la date de sor
CREATE TABLE "comm_tag" (
  "comm_id" uuid NOT NULL,
  "tag_id" uuid NOT NULL,
  "source" text NOT NULL,
  "application_id" uuid,
  "pose_le" timestamptz NOT NULL,
  "sorti_le" timestamptz,
  CONSTRAINT "pk_comm_tag" PRIMARY KEY ("comm_id", "tag_id")
);

-- dossier — Un dossier UTILISATEUR classique (un message dans un seul). Les spéciaux sont des vues calculées ; les virtuel
CREATE TABLE "dossier" (
  "dossier_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "parent_id" uuid,
  "nom" text NOT NULL,
  "alias_imap" text,
  "protege" boolean NOT NULL,
  "ordre" bigint,
  "uid_validity" bigint,
  "uid_suivant" bigint,
  "uid_validity_servie" bigint,
  "uid_servi_suivant" bigint,
  CONSTRAINT "pk_dossier" PRIMARY KEY ("dossier_id")
);

-- filtre — Une règle du moteur : prédicat + action, ordre explicite, portée en cascade, rétroactive possible, compteur de
CREATE TABLE "filtre" (
  "filtre_id" uuid NOT NULL,
  "portee_type" text NOT NULL,
  "portee_id" uuid NOT NULL,
  "nom" text NOT NULL,
  "ordre" bigint NOT NULL,
  "predicat" jsonb NOT NULL,
  "action" jsonb,
  "actif" boolean NOT NULL,
  "retroactif" boolean NOT NULL,
  "fenetre_debut" timestamptz,
  "fenetre_fin" timestamptz,
  "nb_declenchements" bigint NOT NULL,
  "dernier_declenchement" timestamptz,
  "cree_par" uuid NOT NULL,
  "importe_de" text,
  CONSTRAINT "pk_filtre" PRIMARY KEY ("filtre_id"),
  CONSTRAINT "ck_filtre_portee_type" CHECK ("portee_type" IN ('instance', 'domaine', 'compte', 'boite'))
);

-- envoi — Un message émis : identité d'expédition, boîte, programmé pour, remis au relais le, queue_id du MTA, retour d'
CREATE TABLE "envoi" (
  "envoi_id" uuid NOT NULL,
  "comm_id" uuid NOT NULL,
  "identite_id" uuid NOT NULL,
  "programme_pour" timestamptz,
  "remis_le" timestamptz,
  "queue_id" text,
  "retour_enveloppe" text NOT NULL,
  CONSTRAINT "pk_envoi" PRIMARY KEY ("envoi_id")
);

-- envoi_destinataire — Une ligne PAR DESTINATAIRE d'un envoi : état (préparé, remis, accepté, différé, rejeté, livré), DSN corrélé, c
CREATE TABLE "envoi_destinataire" (
  "envoi_id" uuid NOT NULL,
  "adresse_id" uuid NOT NULL,
  "etat" text NOT NULL,
  "dsn_comm_id" uuid,
  "code" text,
  "mis_a_jour_le" timestamptz NOT NULL,
  CONSTRAINT "pk_envoi_destinataire" PRIMARY KEY ("envoi_id", "adresse_id"),
  CONSTRAINT "ck_envoi_destinataire_etat" CHECK ("etat" IN ('prepare', 'programme', 'remis', 'accepte', 'differe', 'rejete', 'livre'))
);

-- dmarc_rapport — Un rapport DMARC agrégé reçu (émetteur, report_id, période, domaine). Unicité (emetteur, report_id).
CREATE TABLE "dmarc_rapport" (
  "dmarc_rapport_id" uuid NOT NULL,
  "domaine_id" uuid NOT NULL,
  "emetteur" text NOT NULL,
  "report_id" text NOT NULL,
  "debut" timestamptz NOT NULL,
  "fin" timestamptz NOT NULL,
  "recu_le" timestamptz NOT NULL,
  "comm_id" uuid,
  CONSTRAINT "pk_dmarc_rapport" PRIMARY KEY ("dmarc_rapport_id")
);

-- dmarc_ligne — Une ligne d'un rapport : IP source, nombre, disposition, résultats SPF/DKIM, alignement.
CREATE TABLE "dmarc_ligne" (
  "dmarc_ligne_id" uuid NOT NULL,
  "dmarc_rapport_id" uuid NOT NULL,
  "ip_source" text NOT NULL,
  "nombre" bigint NOT NULL,
  "disposition" text NOT NULL,
  "resultat_spf" text,
  "resultat_dkim" text,
  "aligne_spf" boolean NOT NULL,
  "aligne_dkim" boolean NOT NULL,
  "en_tete_from" text,
  CONSTRAINT "pk_dmarc_ligne" PRIMARY KEY ("dmarc_ligne_id")
);

-- analyse — Un indice produit par le moteur sur une communication : règle, poids, détails, calculé le. Distingue ce qui es
CREATE TABLE "analyse" (
  "comm_id" uuid NOT NULL,
  "regle" text NOT NULL,
  "poids" bigint NOT NULL,
  "details" jsonb,
  "calcule_le" timestamptz NOT NULL,
  "fige" boolean NOT NULL,
  CONSTRAINT "pk_analyse" PRIMARY KEY ("comm_id", "regle")
);

-- note — Une note interne PARTAGÉE entre les collaborateurs d'une boîte, sur un message OU sur un fil (« je l'ai eu hie
CREATE TABLE "note" (
  "note_id" uuid NOT NULL,
  "boite_id" uuid NOT NULL,
  "comm_id" uuid,
  "thread_id" uuid,
  "auteur_id" uuid NOT NULL,
  "corps" text NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "modifie_le" timestamptz,
  "epinglee" boolean NOT NULL,
  CONSTRAINT "pk_note" PRIMARY KEY ("note_id")
);

-- parametre — Un réglage en cascade : (portée_type, portée_id, clé, valeur, verrouillé, modifié par, modifié le). Instance →
CREATE TABLE "parametre" (
  "portee_type" text NOT NULL,
  "portee_id" uuid NOT NULL,
  "cle" text NOT NULL,
  "valeur" jsonb NOT NULL,
  "verrouille" boolean NOT NULL,
  "modifie_par" uuid NOT NULL,
  "modifie_le" timestamptz NOT NULL,
  CONSTRAINT "pk_parametre" PRIMARY KEY ("portee_type", "portee_id", "cle"),
  CONSTRAINT "ck_parametre_portee_type" CHECK ("portee_type" IN ('instance', 'domaine', 'compte', 'boite'))
);

-- journal — Le journal d'activité : qui a lu, traité, partagé, validé, désabonné, déplacé vers le personnel. Jamais purgé.
CREATE TABLE "journal" (
  "journal_id" uuid NOT NULL,
  "quand" timestamptz NOT NULL,
  "qui" uuid NOT NULL,
  "action" text NOT NULL,
  "cible_type" text NOT NULL,
  "cible_id" uuid NOT NULL,
  "details" jsonb,
  CONSTRAINT "pk_journal" PRIMARY KEY ("journal_id"),
  CONSTRAINT "ck_journal_action" CHECK ("action" IN ('opened', 'processed', 'archived', 'deleted', 'junked', 'refiled', 'status_changed', 'marked', 'shared', 'revoked', 'restored', 'sender_trusted', 'unsubscribed', 'to_personal', 'quarantine_released', 'admin_read'))
);

-- modele — Un MODÈLE de message : gabarit de sujet et de corps avec variables, une catégorie (commande fournisseur, courr
CREATE TABLE "modele" (
  "modele_id" uuid NOT NULL,
  "libelle" text NOT NULL,
  "categorie" text,
  "portee" text NOT NULL,
  "boite_id" uuid,
  "domaine_id" uuid,
  "application_id" uuid,
  "sujet" text NOT NULL,
  "corps" text NOT NULL,
  "variables" jsonb,
  "pieces_jointes" jsonb,
  "identite_id" uuid,
  "langue" text,
  "cree_par" uuid NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "maj_le" timestamptz NOT NULL,
  "nb_utilisations" bigint NOT NULL,
  CONSTRAINT "pk_modele" PRIMARY KEY ("modele_id"),
  CONSTRAINT "ck_modele_portee" CHECK ("portee" IN ('instance', 'domaine', 'compte', 'boite'))
);

-- session — Une session ouverte par un compte (POST /session) : un jeton opaque haché, une expiration, une révocation. C'e
CREATE TABLE "session" (
  "session_id" uuid NOT NULL,
  "compte_id" uuid NOT NULL,
  "jeton_empreinte" text NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "expire_le" timestamptz NOT NULL,
  "revoque_le" timestamptz,
  "agent" text,
  CONSTRAINT "pk_session" PRIMARY KEY ("session_id")
);

-- evenement — Un événement PERSISTÉ, écrit dans la transaction du fait métier et traité hors processus, au moins une fois, a
CREATE TABLE "evenement" (
  "evenement_id" uuid NOT NULL,
  "type" text NOT NULL,
  "module" text NOT NULL,
  "cible" text,
  "charge" jsonb NOT NULL,
  "cree_le" timestamptz NOT NULL,
  "prochaine_tentative" timestamptz NOT NULL,
  "tentatives" bigint NOT NULL,
  "traite_le" timestamptz,
  "abandonne" boolean,
  "erreur" text,
  CONSTRAINT "pk_evenement" PRIMARY KEY ("evenement_id")
);

-- clés étrangères, après toutes les tables : l'ordre de création n'importe plus
ALTER TABLE "comm" ADD CONSTRAINT "fk_comm_thread_id" FOREIGN KEY ("thread_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "reinitialisation" ADD CONSTRAINT "fk_reinitialisation_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_citation" ADD CONSTRAINT "fk_comm_citation_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_citation" ADD CONSTRAINT "fk_comm_citation_cite_comm_id" FOREIGN KEY ("cite_comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_email" ADD CONSTRAINT "fk_comm_email_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_email" ADD CONSTRAINT "fk_comm_email_blob_ref" FOREIGN KEY ("blob_ref") REFERENCES "blob" ("empreinte") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_interne" ADD CONSTRAINT "fk_comm_interne_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_interne" ADD CONSTRAINT "fk_comm_interne_de_compte_id" FOREIGN KEY ("de_compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_interne" ADD CONSTRAINT "fk_comm_interne_a_compte_id" FOREIGN KEY ("a_compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_groupe" ADD CONSTRAINT "fk_comm_groupe_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_groupe" ADD CONSTRAINT "fk_comm_groupe_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_groupe" ADD CONSTRAINT "fk_comm_groupe_auteur_compte_id" FOREIGN KEY ("auteur_compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "participant" ADD CONSTRAINT "fk_participant_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "participant" ADD CONSTRAINT "fk_participant_adresse_id" FOREIGN KEY ("adresse_id") REFERENCES "adresse" ("adresse_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "piece_jointe" ADD CONSTRAINT "fk_piece_jointe_blob_ref" FOREIGN KEY ("blob_ref") REFERENCES "blob" ("empreinte") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "piece_jointe" ADD CONSTRAINT "fk_piece_jointe_blob_origine" FOREIGN KEY ("blob_origine") REFERENCES "blob" ("empreinte") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_piece_jointe" ADD CONSTRAINT "fk_comm_piece_jointe_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_piece_jointe" ADD CONSTRAINT "fk_comm_piece_jointe_piece_jointe_id" FOREIGN KEY ("piece_jointe_id") REFERENCES "piece_jointe" ("piece_jointe_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "adresse" ADD CONSTRAINT "fk_adresse_domaine_id" FOREIGN KEY ("domaine_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "adresse" ADD CONSTRAINT "fk_adresse_correspondant_id" FOREIGN KEY ("correspondant_id") REFERENCES "correspondant" ("correspondant_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "adresse" ADD CONSTRAINT "fk_adresse_valide_par" FOREIGN KEY ("valide_par") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "domaine" ADD CONSTRAINT "fk_domaine_parent_id" FOREIGN KEY ("parent_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "domaine" ADD CONSTRAINT "fk_domaine_sosie_de" FOREIGN KEY ("sosie_de") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "domaine" ADD CONSTRAINT "fk_domaine_valide_par" FOREIGN KEY ("valide_par") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "identite" ADD CONSTRAINT "fk_identite_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "identite" ADD CONSTRAINT "fk_identite_adresse_id" FOREIGN KEY ("adresse_id") REFERENCES "adresse" ("adresse_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "compte" ADD CONSTRAINT "fk_compte_correspondant_id" FOREIGN KEY ("correspondant_id") REFERENCES "correspondant" ("correspondant_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "boite" ADD CONSTRAINT "fk_boite_adresse_id" FOREIGN KEY ("adresse_id") REFERENCES "adresse" ("adresse_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "boite" ADD CONSTRAINT "fk_boite_domaine_id" FOREIGN KEY ("domaine_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_correspondant_id" FOREIGN KEY ("correspondant_id") REFERENCES "correspondant" ("correspondant_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_status_by" FOREIGN KEY ("status_by") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_processed_by" FOREIGN KEY ("processed_by") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_archived_by" FOREIGN KEY ("archived_by") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_deleted_by" FOREIGN KEY ("deleted_by") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_junk_by" FOREIGN KEY ("junk_by") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_dossier_id" FOREIGN KEY ("dossier_id") REFERENCES "dossier" ("dossier_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "rattachement" ADD CONSTRAINT "fk_rattachement_dossier_origine_id" FOREIGN KEY ("dossier_origine_id") REFERENCES "dossier" ("dossier_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "read_state" ADD CONSTRAINT "fk_read_state_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "read_state" ADD CONSTRAINT "fk_read_state_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "read_state" ADD CONSTRAINT "fk_read_state_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker" ADD CONSTRAINT "fk_marker_domaine_id" FOREIGN KEY ("domaine_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_collective" ADD CONSTRAINT "fk_marker_collective_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_collective" ADD CONSTRAINT "fk_marker_collective_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_collective" ADD CONSTRAINT "fk_marker_collective_marker_id" FOREIGN KEY ("marker_id") REFERENCES "marker" ("marker_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_collective" ADD CONSTRAINT "fk_marker_collective_set_by" FOREIGN KEY ("set_by") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_personal" ADD CONSTRAINT "fk_marker_personal_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_personal" ADD CONSTRAINT "fk_marker_personal_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_personal" ADD CONSTRAINT "fk_marker_personal_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "marker_personal" ADD CONSTRAINT "fk_marker_personal_marker_id" FOREIGN KEY ("marker_id") REFERENCES "marker" ("marker_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "acces" ADD CONSTRAINT "fk_acces_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "acces" ADD CONSTRAINT "fk_acces_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "acces" ADD CONSTRAINT "fk_acces_accorde_par" FOREIGN KEY ("accorde_par") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "acces" ADD CONSTRAINT "fk_acces_stands_in_for" FOREIGN KEY ("stands_in_for") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "lecture_groupe" ADD CONSTRAINT "fk_lecture_groupe_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "lecture_groupe" ADD CONSTRAINT "fk_lecture_groupe_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "lecture_groupe" ADD CONSTRAINT "fk_lecture_groupe_dernier_message_lu" FOREIGN KEY ("dernier_message_lu") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "axe" ADD CONSTRAINT "fk_axe_application_id" FOREIGN KEY ("application_id") REFERENCES "application" ("application_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "tag" ADD CONSTRAINT "fk_tag_axe_id" FOREIGN KEY ("axe_id") REFERENCES "axe" ("axe_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_tag" ADD CONSTRAINT "fk_comm_tag_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_tag" ADD CONSTRAINT "fk_comm_tag_tag_id" FOREIGN KEY ("tag_id") REFERENCES "tag" ("tag_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "comm_tag" ADD CONSTRAINT "fk_comm_tag_application_id" FOREIGN KEY ("application_id") REFERENCES "application" ("application_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "dossier" ADD CONSTRAINT "fk_dossier_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "dossier" ADD CONSTRAINT "fk_dossier_parent_id" FOREIGN KEY ("parent_id") REFERENCES "dossier" ("dossier_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "filtre" ADD CONSTRAINT "fk_filtre_cree_par" FOREIGN KEY ("cree_par") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "envoi" ADD CONSTRAINT "fk_envoi_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "envoi" ADD CONSTRAINT "fk_envoi_identite_id" FOREIGN KEY ("identite_id") REFERENCES "identite" ("identite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "envoi_destinataire" ADD CONSTRAINT "fk_envoi_destinataire_envoi_id" FOREIGN KEY ("envoi_id") REFERENCES "envoi" ("envoi_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "envoi_destinataire" ADD CONSTRAINT "fk_envoi_destinataire_adresse_id" FOREIGN KEY ("adresse_id") REFERENCES "adresse" ("adresse_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "envoi_destinataire" ADD CONSTRAINT "fk_envoi_destinataire_dsn_comm_id" FOREIGN KEY ("dsn_comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "dmarc_rapport" ADD CONSTRAINT "fk_dmarc_rapport_domaine_id" FOREIGN KEY ("domaine_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "dmarc_rapport" ADD CONSTRAINT "fk_dmarc_rapport_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "dmarc_ligne" ADD CONSTRAINT "fk_dmarc_ligne_dmarc_rapport_id" FOREIGN KEY ("dmarc_rapport_id") REFERENCES "dmarc_rapport" ("dmarc_rapport_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "analyse" ADD CONSTRAINT "fk_analyse_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "note" ADD CONSTRAINT "fk_note_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "note" ADD CONSTRAINT "fk_note_comm_id" FOREIGN KEY ("comm_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "note" ADD CONSTRAINT "fk_note_thread_id" FOREIGN KEY ("thread_id") REFERENCES "comm" ("comm_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "note" ADD CONSTRAINT "fk_note_auteur_id" FOREIGN KEY ("auteur_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "parametre" ADD CONSTRAINT "fk_parametre_modifie_par" FOREIGN KEY ("modifie_par") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "journal" ADD CONSTRAINT "fk_journal_qui" FOREIGN KEY ("qui") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "modele" ADD CONSTRAINT "fk_modele_boite_id" FOREIGN KEY ("boite_id") REFERENCES "boite" ("boite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "modele" ADD CONSTRAINT "fk_modele_domaine_id" FOREIGN KEY ("domaine_id") REFERENCES "domaine" ("domaine_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "modele" ADD CONSTRAINT "fk_modele_application_id" FOREIGN KEY ("application_id") REFERENCES "application" ("application_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "modele" ADD CONSTRAINT "fk_modele_identite_id" FOREIGN KEY ("identite_id") REFERENCES "identite" ("identite_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "modele" ADD CONSTRAINT "fk_modele_cree_par" FOREIGN KEY ("cree_par") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;
ALTER TABLE "session" ADD CONSTRAINT "fk_session_compte_id" FOREIGN KEY ("compte_id") REFERENCES "compte" ("compte_id") DEFERRABLE INITIALLY IMMEDIATE;

-- unicités
ALTER TABLE "reinitialisation" ADD CONSTRAINT "uq_reinitialisation_jeton_empreinte" UNIQUE ("jeton_empreinte");
ALTER TABLE "adresse" ADD CONSTRAINT "uq_adresse_adresse_complete" UNIQUE ("adresse_complete");
ALTER TABLE "domaine" ADD CONSTRAINT "uq_domaine_nom_ascii" UNIQUE ("nom_ascii");
ALTER TABLE "compte" ADD CONSTRAINT "uq_compte_login" UNIQUE ("login");
ALTER TABLE "marker" ADD CONSTRAINT "uq_marker_code" UNIQUE ("code");
ALTER TABLE "tag" ADD CONSTRAINT "uq_tag_axe_id_valeur" UNIQUE ("axe_id", "valeur");
ALTER TABLE "dossier" ADD CONSTRAINT "uq_dossier_boite_id_alias_imap" UNIQUE ("boite_id", "alias_imap");
ALTER TABLE "dmarc_rapport" ADD CONSTRAINT "uq_dmarc_rapport_emetteur_report_id" UNIQUE ("emetteur", "report_id");
ALTER TABLE "session" ADD CONSTRAINT "uq_session_jeton_empreinte" UNIQUE ("jeton_empreinte");

-- index des références
CREATE INDEX "ix_comm_thread_id" ON "comm" ("thread_id");
CREATE INDEX "ix_reinitialisation_compte_id" ON "reinitialisation" ("compte_id");
CREATE INDEX "ix_comm_citation_comm_id" ON "comm_citation" ("comm_id");
CREATE INDEX "ix_comm_citation_cite_comm_id" ON "comm_citation" ("cite_comm_id");
CREATE INDEX "ix_comm_email_blob_ref" ON "comm_email" ("blob_ref");
CREATE INDEX "ix_comm_interne_de_compte_id" ON "comm_interne" ("de_compte_id");
CREATE INDEX "ix_comm_interne_a_compte_id" ON "comm_interne" ("a_compte_id");
CREATE INDEX "ix_comm_groupe_boite_id" ON "comm_groupe" ("boite_id");
CREATE INDEX "ix_comm_groupe_auteur_compte_id" ON "comm_groupe" ("auteur_compte_id");
CREATE INDEX "ix_participant_adresse_id" ON "participant" ("adresse_id");
CREATE INDEX "ix_piece_jointe_blob_ref" ON "piece_jointe" ("blob_ref");
CREATE INDEX "ix_piece_jointe_blob_origine" ON "piece_jointe" ("blob_origine");
CREATE INDEX "ix_comm_piece_jointe_piece_jointe_id" ON "comm_piece_jointe" ("piece_jointe_id");
CREATE INDEX "ix_adresse_domaine_id" ON "adresse" ("domaine_id");
CREATE INDEX "ix_adresse_correspondant_id" ON "adresse" ("correspondant_id");
CREATE INDEX "ix_adresse_valide_par" ON "adresse" ("valide_par");
CREATE INDEX "ix_domaine_parent_id" ON "domaine" ("parent_id");
CREATE INDEX "ix_domaine_sosie_de" ON "domaine" ("sosie_de");
CREATE INDEX "ix_domaine_valide_par" ON "domaine" ("valide_par");
CREATE INDEX "ix_identite_boite_id" ON "identite" ("boite_id");
CREATE INDEX "ix_identite_adresse_id" ON "identite" ("adresse_id");
CREATE INDEX "ix_compte_correspondant_id" ON "compte" ("correspondant_id");
CREATE INDEX "ix_boite_adresse_id" ON "boite" ("adresse_id");
CREATE INDEX "ix_boite_domaine_id" ON "boite" ("domaine_id");
CREATE INDEX "ix_rattachement_boite_id" ON "rattachement" ("boite_id");
CREATE INDEX "ix_rattachement_compte_id" ON "rattachement" ("compte_id");
CREATE INDEX "ix_rattachement_correspondant_id" ON "rattachement" ("correspondant_id");
CREATE INDEX "ix_rattachement_status_by" ON "rattachement" ("status_by");
CREATE INDEX "ix_rattachement_processed_by" ON "rattachement" ("processed_by");
CREATE INDEX "ix_rattachement_archived_by" ON "rattachement" ("archived_by");
CREATE INDEX "ix_rattachement_deleted_by" ON "rattachement" ("deleted_by");
CREATE INDEX "ix_rattachement_junk_by" ON "rattachement" ("junk_by");
CREATE INDEX "ix_rattachement_dossier_id" ON "rattachement" ("dossier_id");
CREATE INDEX "ix_rattachement_dossier_origine_id" ON "rattachement" ("dossier_origine_id");
CREATE INDEX "ix_read_state_comm_id" ON "read_state" ("comm_id");
CREATE INDEX "ix_read_state_boite_id" ON "read_state" ("boite_id");
CREATE INDEX "ix_marker_domaine_id" ON "marker" ("domaine_id");
CREATE INDEX "ix_marker_collective_boite_id" ON "marker_collective" ("boite_id");
CREATE INDEX "ix_marker_collective_marker_id" ON "marker_collective" ("marker_id");
CREATE INDEX "ix_marker_collective_set_by" ON "marker_collective" ("set_by");
CREATE INDEX "ix_marker_personal_comm_id" ON "marker_personal" ("comm_id");
CREATE INDEX "ix_marker_personal_boite_id" ON "marker_personal" ("boite_id");
CREATE INDEX "ix_marker_personal_marker_id" ON "marker_personal" ("marker_id");
CREATE INDEX "ix_acces_boite_id" ON "acces" ("boite_id");
CREATE INDEX "ix_acces_accorde_par" ON "acces" ("accorde_par");
CREATE INDEX "ix_acces_stands_in_for" ON "acces" ("stands_in_for");
CREATE INDEX "ix_lecture_groupe_boite_id" ON "lecture_groupe" ("boite_id");
CREATE INDEX "ix_lecture_groupe_dernier_message_lu" ON "lecture_groupe" ("dernier_message_lu");
CREATE INDEX "ix_axe_application_id" ON "axe" ("application_id");
CREATE INDEX "ix_tag_axe_id" ON "tag" ("axe_id");
CREATE INDEX "ix_comm_tag_tag_id" ON "comm_tag" ("tag_id");
CREATE INDEX "ix_comm_tag_application_id" ON "comm_tag" ("application_id");
CREATE INDEX "ix_dossier_boite_id" ON "dossier" ("boite_id");
CREATE INDEX "ix_dossier_parent_id" ON "dossier" ("parent_id");
CREATE INDEX "ix_filtre_cree_par" ON "filtre" ("cree_par");
CREATE INDEX "ix_envoi_comm_id" ON "envoi" ("comm_id");
CREATE INDEX "ix_envoi_identite_id" ON "envoi" ("identite_id");
CREATE INDEX "ix_envoi_destinataire_adresse_id" ON "envoi_destinataire" ("adresse_id");
CREATE INDEX "ix_envoi_destinataire_dsn_comm_id" ON "envoi_destinataire" ("dsn_comm_id");
CREATE INDEX "ix_dmarc_rapport_domaine_id" ON "dmarc_rapport" ("domaine_id");
CREATE INDEX "ix_dmarc_rapport_comm_id" ON "dmarc_rapport" ("comm_id");
CREATE INDEX "ix_dmarc_ligne_dmarc_rapport_id" ON "dmarc_ligne" ("dmarc_rapport_id");
CREATE INDEX "ix_note_boite_id" ON "note" ("boite_id");
CREATE INDEX "ix_note_comm_id" ON "note" ("comm_id");
CREATE INDEX "ix_note_thread_id" ON "note" ("thread_id");
CREATE INDEX "ix_note_auteur_id" ON "note" ("auteur_id");
CREATE INDEX "ix_parametre_modifie_par" ON "parametre" ("modifie_par");
CREATE INDEX "ix_journal_qui" ON "journal" ("qui");
CREATE INDEX "ix_modele_boite_id" ON "modele" ("boite_id");
CREATE INDEX "ix_modele_domaine_id" ON "modele" ("domaine_id");
CREATE INDEX "ix_modele_application_id" ON "modele" ("application_id");
CREATE INDEX "ix_modele_identite_id" ON "modele" ("identite_id");
CREATE INDEX "ix_modele_cree_par" ON "modele" ("cree_par");
CREATE INDEX "ix_session_compte_id" ON "session" ("compte_id");

COMMIT;
