"""MODÈLES ORM — engendrés par outils/gen-modeles.py le 2026-09-07T02:49:49 depuis le dictionnaire (D158).
NE PAS ÉDITER : corriger .mmi-pm/docs/dict/*.yml, régénérer. Les tables sont celles de schema.sql (F114)."""
from __future__ import annotations
import datetime, decimal, uuid
from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, LargeBinary, Numeric, PrimaryKeyConstraint, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Comm(Base):
    """Le TRONC polymorphe : une communication datée, avec un sens et des participants, quel que soit son canal. Porte uniqueme"""
    __tablename__ = "comm"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    date_recue: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_declaree: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_ingestion: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sens: Mapped[str] = mapped_column(Text, nullable=False)
    sujet: Mapped[str | None] = mapped_column(Text, nullable=True)
    sujet_normalise: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_comm_thread_id"), nullable=True)
    nature: Mapped[str] = mapped_column(Text, nullable=False)
    from_adresse: Mapped[str] = mapped_column(Text, nullable=False)
    from_nom: Mapped[str | None] = mapped_column(Text, nullable=True)
    taille: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nb_pieces_jointes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    langue: Mapped[str | None] = mapped_column(Text, nullable=True)
    est_chiffre: Mapped[bool] = mapped_column(Boolean, nullable=False)
    est_signe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    corps_texte: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread: Mapped[Comm | None] = relationship("Comm", foreign_keys=[thread_id], remote_side=[comm_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", name="pk_comm"), CheckConstraint("\"type\" IN ('email', 'interne', 'groupe', 'sms', 'whatsapp', 'tel')", name="ck_comm_type"), CheckConstraint("\"sens\" IN ('in', 'out')", name="ck_comm_sens"), CheckConstraint("\"nature\" IN ('humain', 'liste', 'notification', 'service')", name="ck_comm_nature"),)

class CommEmail(Base):
    """La fille « email » du tronc : en-têtes, identifiants de fil, verdicts d'authentification, référence du blob, empreinte, """
    __tablename__ = "comm_email"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_comm_email_comm_id"), nullable=False)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_reply_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    references: Mapped[str | None] = mapped_column(Text, nullable=True)
    return_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    list_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    list_unsubscribe: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[str] = mapped_column(Text, nullable=False)
    verdict_spf: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict_dkim: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict_dmarc: Mapped[str | None] = mapped_column(Text, nullable=True)
    arc_valide: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    blob_ref: Mapped[str] = mapped_column(Text, ForeignKey("blob.empreinte", name="fk_comm_email_blob_ref"), nullable=False)
    empreinte: Mapped[str] = mapped_column(Text, nullable=False)
    structure_mime: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    uid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uid_validity: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    queue_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    reponse_possible: Mapped[str] = mapped_column(Text, nullable=False)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", name="pk_comm_email"), CheckConstraint("\"verdict_spf\" IN ('pass', 'fail', 'none', 'None')", name="ck_comm_email_verdict_spf"), CheckConstraint("\"verdict_dkim\" IN ('pass', 'fail', 'none', 'None')", name="ck_comm_email_verdict_dkim"), CheckConstraint("\"verdict_dmarc\" IN ('pass', 'fail', 'none', 'None')", name="ck_comm_email_verdict_dmarc"), CheckConstraint("\"reponse_possible\" IN ('oui', 'avertir', 'non')", name="ck_comm_email_reponse_possible"),)

class CommInterne(Base):
    """Fille « message interne » (note ou message direct entre comptes), hors SMTP, en base."""
    __tablename__ = "comm_interne"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_comm_interne_comm_id"), nullable=False)
    de_compte_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_comm_interne_de_compte_id"), nullable=False)
    a_compte_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_comm_interne_a_compte_id"), nullable=True)
    corps: Mapped[str] = mapped_column(Text, nullable=False)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    de_compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[de_compte_id])
    a_compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[a_compte_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", name="pk_comm_interne"),)

class CommGroupe(Base):
    """Fille « message de groupe » : chat de service, stocké en base, jamais vers l'extérieur."""
    __tablename__ = "comm_groupe"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_comm_groupe_comm_id"), nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_comm_groupe_boite_id"), nullable=False)
    auteur_compte_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_comm_groupe_auteur_compte_id"), nullable=False)
    corps: Mapped[str] = mapped_column(Text, nullable=False)
    modifie_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    supprime_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    auteur_compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[auteur_compte_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", name="pk_comm_groupe"),)

class Participant(Base):
    """Une adresse impliquée dans une communication, avec son rôle (from/to/cc/bcc/reply-to), son NOM AFFICHÉ tel que déclaré d"""
    __tablename__ = "participant"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_participant_comm_id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    adresse_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("adresse.adresse_id", name="fk_participant_adresse_id"), nullable=False)
    nom_affiche: Mapped[str | None] = mapped_column(Text, nullable=True)
    ordre: Mapped[int] = mapped_column(BigInteger, nullable=False)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    adresse: Mapped[Adresse | None] = relationship("Adresse", foreign_keys=[adresse_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", "ordre", name="pk_participant"), CheckConstraint("\"role\" IN ('from', 'to', 'cc', 'bcc', 'reply_to', 'sender')", name="ck_participant_role"),)

class PieceJointe(Base):
    """Une pièce jointe dédupliquée : nom, type déclaré, taille, blob. Le nom appartient au message (liaison), le contenu au bl"""
    __tablename__ = "piece_jointe"
    piece_jointe_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    blob_ref: Mapped[str] = mapped_column(Text, ForeignKey("blob.empreinte", name="fk_piece_jointe_blob_ref"), nullable=False)
    type_detecte: Mapped[str] = mapped_column(Text, nullable=False)
    taille_octets: Mapped[int] = mapped_column(BigInteger, nullable=False)
    blob_origine: Mapped[str | None] = mapped_column(Text, ForeignKey("blob.empreinte", name="fk_piece_jointe_blob_origine"), nullable=True)
    recompresse_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nb_references: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (PrimaryKeyConstraint("piece_jointe_id", name="pk_piece_jointe"),)

class CommPieceJointe(Base):
    """La liaison message ↔ pièce jointe, qui conserve ordre, encodage de transfert, disposition, content-id et paramètres de p"""
    __tablename__ = "comm_piece_jointe"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_comm_piece_jointe_comm_id"), nullable=False)
    piece_jointe_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("piece_jointe.piece_jointe_id", name="fk_comm_piece_jointe_piece_jointe_id"), nullable=False)
    ordre: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nom_declare: Mapped[str | None] = mapped_column(Text, nullable=True)
    type_declare: Mapped[str | None] = mapped_column(Text, nullable=True)
    transfer_encoding: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposition: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    parametres: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    renomme_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    piece_jointe: Mapped[PieceJointe | None] = relationship("PieceJointe", foreign_keys=[piece_jointe_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", "ordre", name="pk_comm_piece_jointe"),)

class Blob(Base):
    """Un contenu binaire adressé par empreinte, compressé zstd, hors base. Compteur de références pour le ramasse-miettes ; un"""
    __tablename__ = "blob"
    empreinte: Mapped[str] = mapped_column(Text, nullable=False)
    taille_octets: Mapped[int] = mapped_column(BigInteger, nullable=False)
    taille_stockee: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compression: Mapped[str] = mapped_column(Text, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nb_references: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dernier_acces: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (PrimaryKeyConstraint("empreinte", name="pk_blob"),)

class Correspondant(Base):
    """Une IDENTITÉ — personne, boîte fonctionnelle, automate, compte interne — qui peut porter plusieurs adresses. C'est une i"""
    __tablename__ = "correspondant"
    correspondant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    nom_canonique: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    organisation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    __table_args__ = (PrimaryKeyConstraint("correspondant_id", name="pk_correspondant"), CheckConstraint("\"type\" IN ('personne', 'fonctionnel', 'automate', 'interne')", name="ck_correspondant_type"),)

class Adresse(Base):
    """Une adresse email = partie locale + référence au domaine. Porte l'adresse complète dénormalisée, la forme normalisée qui"""
    __tablename__ = "adresse"
    adresse_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    local: Mapped[str] = mapped_column(Text, nullable=False)
    local_cmp: Mapped[str] = mapped_column(Text, nullable=False)
    local_base: Mapped[str | None] = mapped_column(Text, nullable=True)
    domaine_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("domaine.domaine_id", name="fk_adresse_domaine_id"), nullable=False)
    adresse_complete: Mapped[str] = mapped_column(Text, nullable=False)
    correspondant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("correspondant.correspondant_id", name="fk_adresse_correspondant_id"), nullable=True)
    lie_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delie_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verifie_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verifie_methode: Mapped[str | None] = mapped_column(Text, nullable=True)
    valide_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valide_par: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_adresse_valide_par"), nullable=True)
    valide_portee: Mapped[str | None] = mapped_column(Text, nullable=True)
    fiabilite: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    fiabilite_calculee_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    domaine: Mapped[Domaine | None] = relationship("Domaine", foreign_keys=[domaine_id])
    correspondant: Mapped[Correspondant | None] = relationship("Correspondant", foreign_keys=[correspondant_id])
    __table_args__ = (PrimaryKeyConstraint("adresse_id", name="pk_adresse"), UniqueConstraint("adresse_complete", name="uq_adresse_adresse_complete"), CheckConstraint("\"valide_portee\" IN ('instance', 'domaine', 'compte', 'boite')", name="ck_adresse_valide_portee"),)

class Domaine(Base):
    """Un domaine DNS, avec son domaine organisationnel parent (Public Suffix List). Porte ce qui appartient au domaine et non """
    __tablename__ = "domaine"
    domaine_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    nom_ascii: Mapped[str] = mapped_column(Text, nullable=False)
    nom_unicode: Mapped[str] = mapped_column(Text, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("domaine.domaine_id", name="fk_domaine_parent_id"), nullable=True)
    heberge_par_nous: Mapped[bool] = mapped_column(Boolean, nullable=False)
    politique_dmarc: Mapped[str | None] = mapped_column(Text, nullable=True)
    politique_lue_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sosie_de: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("domaine.domaine_id", name="fk_domaine_sosie_de"), nullable=True)
    enregistre_le: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    plateforme: Mapped[str | None] = mapped_column(Text, nullable=True)
    valide_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valide_par: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_domaine_valide_par"), nullable=True)
    valide_portee: Mapped[str | None] = mapped_column(Text, nullable=True)
    fiabilite: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    parent: Mapped[Domaine | None] = relationship("Domaine", foreign_keys=[parent_id], remote_side=[domaine_id])
    __table_args__ = (PrimaryKeyConstraint("domaine_id", name="pk_domaine"), UniqueConstraint("nom_ascii", name="uq_domaine_nom_ascii"), CheckConstraint("\"politique_dmarc\" IN ('none', 'quarantine', 'reject')", name="ck_domaine_politique_dmarc"), CheckConstraint("\"valide_portee\" IN ('instance', 'domaine', 'compte', 'boite')", name="ck_domaine_valide_portee"),)

class Identite(Base):
    """Ce SOUS QUOI un compte écrit depuis une boîte : nom affiché, adresse, Reply-To, signature. « Au nom de » optionnel sur b"""
    __tablename__ = "identite"
    identite_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_identite_boite_id"), nullable=False)
    nom_affiche: Mapped[str] = mapped_column(Text, nullable=False)
    adresse_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("adresse.adresse_id", name="fk_identite_adresse_id"), nullable=False)
    reply_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    au_nom_de: Mapped[bool] = mapped_column(Boolean, nullable=False)
    par_defaut: Mapped[bool] = mapped_column(Boolean, nullable=False)
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    adresse: Mapped[Adresse | None] = relationship("Adresse", foreign_keys=[adresse_id])
    __table_args__ = (PrimaryKeyConstraint("identite_id", name="pk_identite"),)

class Compte(Base):
    """Une personne qui se connecte. Est une identité interne (D061). Porte ses préférences personnelles (ordre des dossiers, t"""
    __tablename__ = "compte"
    compte_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    login: Mapped[str] = mapped_column(Text, nullable=False)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    mot_de_passe_empreinte: Mapped[str | None] = mapped_column(Text, nullable=True)
    correspondant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("correspondant.correspondant_id", name="fk_compte_correspondant_id"), nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    desactive_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    langue: Mapped[str | None] = mapped_column(Text, nullable=True)
    fuseau: Mapped[str | None] = mapped_column(Text, nullable=True)
    correspondant: Mapped[Correspondant | None] = relationship("Correspondant", foreign_keys=[correspondant_id])
    __table_args__ = (PrimaryKeyConstraint("compte_id", name="pk_compte"), UniqueConstraint("login", name="uq_compte_login"),)

class Boite(Base):
    """Une adresse de réception administrée : personnelle, partagée, alias (un alias est une vraie boîte), de collecte (dmarc-r"""
    __tablename__ = "boite"
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    adresse_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("adresse.adresse_id", name="fk_boite_adresse_id"), nullable=False)
    domaine_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("domaine.domaine_id", name="fk_boite_domaine_id"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    absence: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    adresse: Mapped[Adresse | None] = relationship("Adresse", foreign_keys=[adresse_id])
    domaine: Mapped[Domaine | None] = relationship("Domaine", foreign_keys=[domaine_id])
    __table_args__ = (PrimaryKeyConstraint("boite_id", name="pk_boite"), CheckConstraint("\"type\" IN ('personnelle', 'partagee', 'alias', 'collecte', 'groupe')", name="ck_boite_type"),)

class Rattachement(Base):
    """LE lien entre une communication et une boîte/un compte : c'est ici que vivent les flags de lecture, le statut de traitem"""
    __tablename__ = "rattachement"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_rattachement_comm_id"), nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_rattachement_boite_id"), nullable=False)
    compte_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_rattachement_compte_id"), nullable=True)
    correspondant_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("correspondant.correspondant_id", name="fk_rattachement_correspondant_id"), nullable=True)
    lu_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repondu_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    transfere_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    drapeau: Mapped[bool] = mapped_column(Boolean, nullable=False)
    statut: Mapped[str] = mapped_column(Text, nullable=False)
    sorti_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motif_sortie: Mapped[str | None] = mapped_column(Text, nullable=True)
    supprime_par: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_rattachement_supprime_par"), nullable=True)
    restaurable_jusqu_au: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dossier_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dossier.dossier_id", name="fk_rattachement_dossier_id"), nullable=True)
    dossier_origine_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dossier.dossier_id", name="fk_rattachement_dossier_origine_id"), nullable=True)
    personnel: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reveil_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    echeance_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gele: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[compte_id])
    correspondant: Mapped[Correspondant | None] = relationship("Correspondant", foreign_keys=[correspondant_id])
    dossier: Mapped[Dossier | None] = relationship("Dossier", foreign_keys=[dossier_id])
    dossier_origine: Mapped[Dossier | None] = relationship("Dossier", foreign_keys=[dossier_origine_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", "boite_id", name="pk_rattachement"), CheckConstraint("\"statut\" IN ('nouveau', 'a_faire', 'en_cours', 'attente', 'traite')", name="ck_rattachement_statut"), CheckConstraint("\"motif_sortie\" IN ('traite', 'archive', 'supprime')", name="ck_rattachement_motif_sortie"),)

class Acces(Base):
    """Un droit d'un compte sur une boîte (ou une identité), DATÉ : début, fin, rôle, révocation tracée. La trace ne donne pas """
    __tablename__ = "acces"
    compte_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_acces_compte_id"), nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_acces_boite_id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    debut: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accorde_par: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_acces_accorde_par"), nullable=False)
    compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[compte_id])
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    __table_args__ = (PrimaryKeyConstraint("compte_id", "boite_id", name="pk_acces"), CheckConstraint("\"role\" IN ('lecteur', 'membre', 'gestionnaire', 'admin_domaine', 'admin_instance')", name="ck_acces_role"),)

class LectureGroupe(Base):
    """Position de lecture d'un compte dans un groupe : dernier message lu, vu le. Trente lignes au lieu de trente-trois millio"""
    __tablename__ = "lecture_groupe"
    compte_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_lecture_groupe_compte_id"), nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_lecture_groupe_boite_id"), nullable=False)
    dernier_message_lu: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_lecture_groupe_dernier_message_lu"), nullable=True)
    vu_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[compte_id])
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    __table_args__ = (PrimaryKeyConstraint("compte_id", "boite_id", name="pk_lecture_groupe"),)

class Application(Base):
    """Une instance d'application connectée (type de connecteur + instance) : jeton, portée (boîtes/domaines), axes qu'elle déc"""
    __tablename__ = "application"
    application_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    type_connecteur: Mapped[str] = mapped_column(Text, nullable=False)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    jeton_empreinte: Mapped[str] = mapped_column(Text, nullable=False)
    portee: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    axes: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    debit_max: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dernier_appel: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (PrimaryKeyConstraint("application_id", name="pk_application"),)

class Axe(Base):
    """Une catégorie de tags — un « tag_group » — porteuse d'ACL, déclarée par une application qui en alimente les valeurs ; ou"""
    __tablename__ = "axe"
    axe_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("application.application_id", name="fk_axe_application_id"), nullable=True)
    acl: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    derive: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ordre: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    application: Mapped[Application | None] = relationship("Application", foreign_keys=[application_id])
    __table_args__ = (PrimaryKeyConstraint("axe_id", name="pk_axe"),)

class Tag(Base):
    """Une valeur d'un axe : une CLÉ stable (l'identifiant chez l'application — 1042, RM2881 — ou le List-Id) et un LIBELLÉ aff"""
    __tablename__ = "tag"
    tag_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    axe_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("axe.axe_id", name="fk_tag_axe_id"), nullable=False)
    valeur: Mapped[str] = mapped_column(Text, nullable=False)
    libelle: Mapped[str] = mapped_column(Text, nullable=False)
    ref_externe: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False)
    axe: Mapped[Axe | None] = relationship("Axe", foreign_keys=[axe_id])
    __table_args__ = (PrimaryKeyConstraint("tag_id", name="pk_tag"), UniqueConstraint("axe_id", "valeur", name="uq_tag_axe_id_valeur"),)

class CommTag(Base):
    """La liaison communication ↔ tag, avec sa SOURCE (quelle application ou quel filtre l'a posée) et la date de sortie dénorm"""
    __tablename__ = "comm_tag"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_comm_tag_comm_id"), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tag.tag_id", name="fk_comm_tag_tag_id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    application_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("application.application_id", name="fk_comm_tag_application_id"), nullable=True)
    pose_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sorti_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    tag: Mapped[Tag | None] = relationship("Tag", foreign_keys=[tag_id])
    application: Mapped[Application | None] = relationship("Application", foreign_keys=[application_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", "tag_id", name="pk_comm_tag"),)

class Dossier(Base):
    """Un dossier UTILISATEUR classique (un message dans un seul). Les spéciaux sont des vues calculées ; les virtuels sont des"""
    __tablename__ = "dossier"
    dossier_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_dossier_boite_id"), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("dossier.dossier_id", name="fk_dossier_parent_id"), nullable=True)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    alias_imap: Mapped[str | None] = mapped_column(Text, nullable=True)
    protege: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ordre: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uid_validity: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uid_suivant: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    parent: Mapped[Dossier | None] = relationship("Dossier", foreign_keys=[parent_id], remote_side=[dossier_id])
    __table_args__ = (PrimaryKeyConstraint("dossier_id", name="pk_dossier"), UniqueConstraint("boite_id", "alias_imap", name="uq_dossier_boite_id_alias_imap"),)

class Filtre(Base):
    """Une règle du moteur : prédicat + action, ordre explicite, portée en cascade, rétroactive possible, compteur de déclenche"""
    __tablename__ = "filtre"
    filtre_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    portee_type: Mapped[str] = mapped_column(Text, nullable=False)
    portee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    nom: Mapped[str] = mapped_column(Text, nullable=False)
    ordre: Mapped[int] = mapped_column(BigInteger, nullable=False)
    predicat: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    action: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    actif: Mapped[bool] = mapped_column(Boolean, nullable=False)
    retroactif: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fenetre_debut: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fenetre_fin: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nb_declenchements: Mapped[int] = mapped_column(BigInteger, nullable=False)
    dernier_declenchement: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cree_par: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_filtre_cree_par"), nullable=False)
    importe_de: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (PrimaryKeyConstraint("filtre_id", name="pk_filtre"), CheckConstraint("\"portee_type\" IN ('instance', 'domaine', 'compte', 'boite')", name="ck_filtre_portee_type"),)

class Envoi(Base):
    """Un message émis : identité d'expédition, boîte, programmé pour, remis au relais le, queue_id du MTA, retour d'enveloppe """
    __tablename__ = "envoi"
    envoi_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_envoi_comm_id"), nullable=False)
    identite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("identite.identite_id", name="fk_envoi_identite_id"), nullable=False)
    programme_pour: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remis_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    queue_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    retour_enveloppe: Mapped[str] = mapped_column(Text, nullable=False)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    identite: Mapped[Identite | None] = relationship("Identite", foreign_keys=[identite_id])
    __table_args__ = (PrimaryKeyConstraint("envoi_id", name="pk_envoi"),)

class EnvoiDestinataire(Base):
    """Une ligne PAR DESTINATAIRE d'un envoi : état (préparé, remis, accepté, différé, rejeté, livré), DSN corrélé, code et dat"""
    __tablename__ = "envoi_destinataire"
    envoi_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("envoi.envoi_id", name="fk_envoi_destinataire_envoi_id"), nullable=False)
    adresse_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("adresse.adresse_id", name="fk_envoi_destinataire_adresse_id"), nullable=False)
    etat: Mapped[str] = mapped_column(Text, nullable=False)
    dsn_comm_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_envoi_destinataire_dsn_comm_id"), nullable=True)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    mis_a_jour_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    envoi: Mapped[Envoi | None] = relationship("Envoi", foreign_keys=[envoi_id])
    adresse: Mapped[Adresse | None] = relationship("Adresse", foreign_keys=[adresse_id])
    dsn_comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[dsn_comm_id])
    __table_args__ = (PrimaryKeyConstraint("envoi_id", "adresse_id", name="pk_envoi_destinataire"), CheckConstraint("\"etat\" IN ('prepare', 'programme', 'remis', 'accepte', 'differe', 'rejete', 'livre')", name="ck_envoi_destinataire_etat"),)

class DmarcRapport(Base):
    """Un rapport DMARC agrégé reçu (émetteur, report_id, période, domaine). Unicité (emetteur, report_id)."""
    __tablename__ = "dmarc_rapport"
    dmarc_rapport_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    domaine_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("domaine.domaine_id", name="fk_dmarc_rapport_domaine_id"), nullable=False)
    emetteur: Mapped[str] = mapped_column(Text, nullable=False)
    report_id: Mapped[str] = mapped_column(Text, nullable=False)
    debut: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recu_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comm_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_dmarc_rapport_comm_id"), nullable=True)
    domaine: Mapped[Domaine | None] = relationship("Domaine", foreign_keys=[domaine_id])
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    __table_args__ = (PrimaryKeyConstraint("dmarc_rapport_id", name="pk_dmarc_rapport"), UniqueConstraint("emetteur", "report_id", name="uq_dmarc_rapport_emetteur_report_id"),)

class DmarcLigne(Base):
    """Une ligne d'un rapport : IP source, nombre, disposition, résultats SPF/DKIM, alignement."""
    __tablename__ = "dmarc_ligne"
    dmarc_ligne_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    dmarc_rapport_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("dmarc_rapport.dmarc_rapport_id", name="fk_dmarc_ligne_dmarc_rapport_id"), nullable=False)
    ip_source: Mapped[str] = mapped_column(Text, nullable=False)
    nombre: Mapped[int] = mapped_column(BigInteger, nullable=False)
    disposition: Mapped[str] = mapped_column(Text, nullable=False)
    resultat_spf: Mapped[str | None] = mapped_column(Text, nullable=True)
    resultat_dkim: Mapped[str | None] = mapped_column(Text, nullable=True)
    aligne_spf: Mapped[bool] = mapped_column(Boolean, nullable=False)
    aligne_dkim: Mapped[bool] = mapped_column(Boolean, nullable=False)
    en_tete_from: Mapped[str | None] = mapped_column(Text, nullable=True)
    dmarc_rapport: Mapped[DmarcRapport | None] = relationship("DmarcRapport", foreign_keys=[dmarc_rapport_id])
    __table_args__ = (PrimaryKeyConstraint("dmarc_ligne_id", name="pk_dmarc_ligne"),)

class Analyse(Base):
    """Un indice produit par le moteur sur une communication : règle, poids, détails, calculé le. Distingue ce qui est FIGÉ à l"""
    __tablename__ = "analyse"
    comm_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_analyse_comm_id"), nullable=False)
    regle: Mapped[str] = mapped_column(Text, nullable=False)
    poids: Mapped[int] = mapped_column(BigInteger, nullable=False)
    details: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    calcule_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fige: Mapped[bool] = mapped_column(Boolean, nullable=False)
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    __table_args__ = (PrimaryKeyConstraint("comm_id", "regle", name="pk_analyse"),)

class Note(Base):
    """Une note interne PARTAGÉE entre les collaborateurs d'une boîte, sur un message OU sur un fil (« je l'ai eu hier, on en d"""
    __tablename__ = "note"
    note_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    boite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_note_boite_id"), nullable=False)
    comm_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_note_comm_id"), nullable=True)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("comm.comm_id", name="fk_note_thread_id"), nullable=True)
    auteur_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_note_auteur_id"), nullable=False)
    corps: Mapped[str] = mapped_column(Text, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    modifie_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    epinglee: Mapped[bool] = mapped_column(Boolean, nullable=False)
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    comm: Mapped[Comm | None] = relationship("Comm", foreign_keys=[comm_id])
    thread: Mapped[Comm | None] = relationship("Comm", foreign_keys=[thread_id])
    auteur: Mapped[Compte | None] = relationship("Compte", foreign_keys=[auteur_id])
    __table_args__ = (PrimaryKeyConstraint("note_id", name="pk_note"),)

class Parametre(Base):
    """Un réglage en cascade : (portée_type, portée_id, clé, valeur, verrouillé, modifié par, modifié le). Instance → domaine →"""
    __tablename__ = "parametre"
    portee_type: Mapped[str] = mapped_column(Text, nullable=False)
    portee_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    cle: Mapped[str] = mapped_column(Text, nullable=False)
    valeur: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    verrouille: Mapped[bool] = mapped_column(Boolean, nullable=False)
    modifie_par: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_parametre_modifie_par"), nullable=False)
    modifie_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (PrimaryKeyConstraint("portee_type", "portee_id", "cle", name="pk_parametre"), CheckConstraint("\"portee_type\" IN ('instance', 'domaine', 'compte', 'boite')", name="ck_parametre_portee_type"),)

class Journal(Base):
    """Le journal d'activité : qui a lu, traité, partagé, validé, désabonné, déplacé vers le personnel. Jamais purgé. Sur le do"""
    __tablename__ = "journal"
    journal_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    quand: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    qui: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_journal_qui"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    cible_type: Mapped[str] = mapped_column(Text, nullable=False)
    cible_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    details: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    __table_args__ = (PrimaryKeyConstraint("journal_id", name="pk_journal"), CheckConstraint("\"action\" IN ('lu', 'traite', 'partage', 'revoque', 'supprime', 'restaure', 'valide_expediteur', 'desabonne', 'vers_personnel', 'libere_quarantaine', 'admin_lecture')", name="ck_journal_action"),)

class Modele(Base):
    """Un MODÈLE de message : gabarit de sujet et de corps avec variables, une catégorie (commande fournisseur, courrier RH…), """
    __tablename__ = "modele"
    modele_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    libelle: Mapped[str] = mapped_column(Text, nullable=False)
    categorie: Mapped[str | None] = mapped_column(Text, nullable=True)
    portee: Mapped[str] = mapped_column(Text, nullable=False)
    boite_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("boite.boite_id", name="fk_modele_boite_id"), nullable=True)
    domaine_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("domaine.domaine_id", name="fk_modele_domaine_id"), nullable=True)
    application_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("application.application_id", name="fk_modele_application_id"), nullable=True)
    sujet: Mapped[str] = mapped_column(Text, nullable=False)
    corps: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    pieces_jointes: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    identite_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("identite.identite_id", name="fk_modele_identite_id"), nullable=True)
    langue: Mapped[str | None] = mapped_column(Text, nullable=True)
    cree_par: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_modele_cree_par"), nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    maj_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    nb_utilisations: Mapped[int] = mapped_column(BigInteger, nullable=False)
    boite: Mapped[Boite | None] = relationship("Boite", foreign_keys=[boite_id])
    domaine: Mapped[Domaine | None] = relationship("Domaine", foreign_keys=[domaine_id])
    application: Mapped[Application | None] = relationship("Application", foreign_keys=[application_id])
    identite: Mapped[Identite | None] = relationship("Identite", foreign_keys=[identite_id])
    __table_args__ = (PrimaryKeyConstraint("modele_id", name="pk_modele"), CheckConstraint("\"portee\" IN ('instance', 'domaine', 'compte', 'boite')", name="ck_modele_portee"),)

class Session(Base):
    """Une session ouverte par un compte (POST /session) : un jeton opaque haché, une expiration, une révocation. C'est le port"""
    __tablename__ = "session"
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    compte_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("compte.compte_id", name="fk_session_compte_id"), nullable=False)
    jeton_empreinte: Mapped[str] = mapped_column(Text, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expire_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoque_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    compte: Mapped[Compte | None] = relationship("Compte", foreign_keys=[compte_id])
    __table_args__ = (PrimaryKeyConstraint("session_id", name="pk_session"), UniqueConstraint("jeton_empreinte", name="uq_session_jeton_empreinte"),)

class Evenement(Base):
    """Un événement PERSISTÉ, écrit dans la transaction du fait métier et traité hors processus, au moins une fois, avec tentat"""
    __tablename__ = "evenement"
    evenement_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    cible: Mapped[str | None] = mapped_column(Text, nullable=True)
    charge: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    cree_le: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prochaine_tentative: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    tentatives: Mapped[int] = mapped_column(BigInteger, nullable=False)
    traite_le: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abandonne: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (PrimaryKeyConstraint("evenement_id", name="pk_evenement"),)

MODELES = {"comm": Comm, "comm_email": CommEmail, "comm_interne": CommInterne, "comm_groupe": CommGroupe, "participant": Participant, "piece_jointe": PieceJointe, "comm_piece_jointe": CommPieceJointe, "blob": Blob, "correspondant": Correspondant, "adresse": Adresse, "domaine": Domaine, "identite": Identite, "compte": Compte, "boite": Boite, "rattachement": Rattachement, "acces": Acces, "lecture_groupe": LectureGroupe, "application": Application, "axe": Axe, "tag": Tag, "comm_tag": CommTag, "dossier": Dossier, "filtre": Filtre, "envoi": Envoi, "envoi_destinataire": EnvoiDestinataire, "dmarc_rapport": DmarcRapport, "dmarc_ligne": DmarcLigne, "analyse": Analyse, "note": Note, "parametre": Parametre, "journal": Journal, "modele": Modele, "session": Session, "evenement": Evenement}
