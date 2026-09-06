"""CONTRAT — schémas Pydantic engendrés par outils/gen-modeles.py depuis le dictionnaire (D141, D158).
Les noms sont ceux de champs.yml : ce que le webmail lit. NE PAS ÉDITER."""
from __future__ import annotations
import datetime, decimal, uuid
from pydantic import BaseModel, ConfigDict

class Comm(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    type: str
    date_recue: datetime.datetime
    date_declaree: datetime.datetime | None = None
    date_ingestion: datetime.datetime
    sens: str
    sujet: str | None = None
    sujet_normalise: str | None = None
    thread_id: uuid.UUID | None = None
    nature: str
    from_adresse: str
    from_nom: str | None = None
    taille: int
    nb_pieces_jointes: int
    langue: str | None = None
    est_chiffre: bool
    est_signe: bool
    snippet: str | None = None

class CommEmail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    message_id: str | None = None
    in_reply_to: str | None = None
    references: str | None = None
    return_path: str | None = None
    list_id: str | None = None
    list_unsubscribe: str | None = None
    headers: str
    verdict_spf: str | None = None
    verdict_dkim: str | None = None
    verdict_dmarc: str | None = None
    arc_valide: bool | None = None
    blob_ref: str
    empreinte: str
    structure_mime: dict | list | None = None
    uid: int | None = None
    uid_validity: int | None = None
    queue_id: str | None = None
    reponse_possible: str

class CommInterne(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    de_compte_id: uuid.UUID
    a_compte_id: uuid.UUID | None = None
    corps: str

class CommGroupe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    boite_id: uuid.UUID
    auteur_compte_id: uuid.UUID
    corps: str
    modifie_le: datetime.datetime | None = None
    supprime_le: datetime.datetime | None = None

class Participant(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    role: str
    adresse_id: uuid.UUID
    nom_affiche: str | None = None
    ordre: int

class PieceJointe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    piece_jointe_id: uuid.UUID
    blob_ref: str
    type_detecte: str
    taille_octets: int
    blob_origine: str | None = None
    recompresse_le: datetime.datetime | None = None
    nb_references: int

class CommPieceJointe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    piece_jointe_id: uuid.UUID
    ordre: int
    nom_declare: str | None = None
    type_declare: str | None = None
    transfer_encoding: str | None = None
    disposition: str | None = None
    content_id: str | None = None
    parametres: dict | list | None = None
    renomme_en: str | None = None

class Blob(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    empreinte: str
    taille_octets: int
    taille_stockee: int
    compression: str
    cree_le: datetime.datetime
    nb_references: int
    dernier_acces: datetime.datetime | None = None

class Correspondant(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    correspondant_id: uuid.UUID
    nom_canonique: str
    type: str
    cree_le: datetime.datetime
    organisation_id: uuid.UUID | None = None

class Adresse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    adresse_id: uuid.UUID
    local: str
    local_cmp: str
    local_base: str | None = None
    domaine_id: uuid.UUID
    adresse_complete: str
    correspondant_id: uuid.UUID | None = None
    lie_le: datetime.datetime | None = None
    delie_le: datetime.datetime | None = None
    verifie_le: datetime.datetime | None = None
    verifie_methode: str | None = None
    valide_le: datetime.datetime | None = None
    valide_par: uuid.UUID | None = None
    valide_portee: str | None = None
    fiabilite: int | None = None
    fiabilite_calculee_le: datetime.datetime | None = None

class Domaine(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    domaine_id: uuid.UUID
    nom_ascii: str
    nom_unicode: str
    parent_id: uuid.UUID | None = None
    heberge_par_nous: bool
    politique_dmarc: str | None = None
    politique_lue_le: datetime.datetime | None = None
    sosie_de: uuid.UUID | None = None
    enregistre_le: datetime.date | None = None
    plateforme: str | None = None
    valide_le: datetime.datetime | None = None
    valide_par: uuid.UUID | None = None
    valide_portee: str | None = None
    fiabilite: int | None = None

class Identite(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    identite_id: uuid.UUID
    boite_id: uuid.UUID
    nom_affiche: str
    adresse_id: uuid.UUID
    reply_to: str | None = None
    signature: str | None = None
    au_nom_de: bool
    par_defaut: bool

class Compte(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compte_id: uuid.UUID
    login: str
    nom: str
    mot_de_passe_empreinte: str | None = None
    correspondant_id: uuid.UUID | None = None
    actif: bool
    cree_le: datetime.datetime
    desactive_le: datetime.datetime | None = None
    preferences: dict | list | None = None
    langue: str | None = None
    fuseau: str | None = None

class Boite(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    boite_id: uuid.UUID
    adresse_id: uuid.UUID
    domaine_id: uuid.UUID
    type: str
    absence: dict | list | None = None

class Rattachement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    boite_id: uuid.UUID
    compte_id: uuid.UUID | None = None
    correspondant_id: uuid.UUID | None = None
    lu_le: datetime.datetime | None = None
    repondu_le: datetime.datetime | None = None
    transfere_le: datetime.datetime | None = None
    drapeau: bool
    statut: str
    sorti_le: datetime.datetime | None = None
    motif_sortie: str | None = None
    supprime_par: uuid.UUID | None = None
    restaurable_jusqu_au: datetime.datetime | None = None
    dossier_id: uuid.UUID | None = None
    dossier_origine_id: uuid.UUID | None = None
    personnel: bool
    reveil_le: datetime.datetime | None = None
    echeance_le: datetime.datetime | None = None
    gele: bool

class Acces(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compte_id: uuid.UUID
    boite_id: uuid.UUID
    role: str
    debut: datetime.datetime
    fin: datetime.datetime | None = None
    accorde_par: uuid.UUID

class LectureGroupe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compte_id: uuid.UUID
    boite_id: uuid.UUID
    dernier_message_lu: uuid.UUID | None = None
    vu_le: datetime.datetime | None = None

class Application(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    application_id: uuid.UUID
    type_connecteur: str
    nom: str
    jeton_empreinte: str
    portee: dict | list
    axes: dict | list | None = None
    debit_max: int | None = None
    actif: bool
    cree_le: datetime.datetime
    dernier_appel: datetime.datetime | None = None

class Axe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    axe_id: uuid.UUID
    nom: str
    application_id: uuid.UUID | None = None
    acl: dict | list
    derive: bool
    ordre: int | None = None

class Tag(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tag_id: uuid.UUID
    axe_id: uuid.UUID
    valeur: str
    libelle: str
    ref_externe: dict | list | None = None
    actif: bool

class CommTag(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    tag_id: uuid.UUID
    source: str
    application_id: uuid.UUID | None = None
    pose_le: datetime.datetime
    sorti_le: datetime.datetime | None = None

class Dossier(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dossier_id: uuid.UUID
    boite_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    nom: str
    alias_imap: str | None = None
    protege: bool
    ordre: int | None = None
    uid_validity: int | None = None
    uid_suivant: int | None = None

class Filtre(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    filtre_id: uuid.UUID
    portee_type: str
    portee_id: uuid.UUID
    nom: str
    ordre: int
    predicat: dict | list
    action: dict | list | None = None
    actif: bool
    retroactif: bool
    fenetre_debut: datetime.datetime | None = None
    fenetre_fin: datetime.datetime | None = None
    nb_declenchements: int
    dernier_declenchement: datetime.datetime | None = None
    cree_par: uuid.UUID
    importe_de: str | None = None

class Envoi(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    envoi_id: uuid.UUID
    comm_id: uuid.UUID
    identite_id: uuid.UUID
    programme_pour: datetime.datetime | None = None
    remis_le: datetime.datetime | None = None
    queue_id: str | None = None
    retour_enveloppe: str

class EnvoiDestinataire(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    envoi_id: uuid.UUID
    adresse_id: uuid.UUID
    etat: str
    dsn_comm_id: uuid.UUID | None = None
    code: str | None = None
    mis_a_jour_le: datetime.datetime

class DmarcRapport(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dmarc_rapport_id: uuid.UUID
    domaine_id: uuid.UUID
    emetteur: str
    report_id: str
    debut: datetime.datetime
    fin: datetime.datetime
    recu_le: datetime.datetime
    comm_id: uuid.UUID | None = None

class DmarcLigne(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    dmarc_ligne_id: uuid.UUID
    dmarc_rapport_id: uuid.UUID
    ip_source: str
    nombre: int
    disposition: str
    resultat_spf: str | None = None
    resultat_dkim: str | None = None
    aligne_spf: bool
    aligne_dkim: bool
    en_tete_from: str | None = None

class Analyse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    comm_id: uuid.UUID
    regle: str
    poids: int
    details: dict | list | None = None
    calcule_le: datetime.datetime
    fige: bool

class Note(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    note_id: uuid.UUID
    boite_id: uuid.UUID
    comm_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None
    auteur_id: uuid.UUID
    corps: str
    cree_le: datetime.datetime
    modifie_le: datetime.datetime | None = None
    epinglee: bool

class Parametre(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    portee_type: str
    portee_id: uuid.UUID
    cle: str
    valeur: dict | list
    verrouille: bool
    modifie_par: uuid.UUID
    modifie_le: datetime.datetime

class Journal(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    journal_id: uuid.UUID
    quand: datetime.datetime
    qui: uuid.UUID
    action: str
    cible_type: str
    cible_id: uuid.UUID
    details: dict | list | None = None

class Modele(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    modele_id: uuid.UUID
    libelle: str
    categorie: str | None = None
    portee: str
    boite_id: uuid.UUID | None = None
    domaine_id: uuid.UUID | None = None
    application_id: uuid.UUID | None = None
    sujet: str
    corps: str
    variables: dict | list | None = None
    pieces_jointes: dict | list | None = None
    identite_id: uuid.UUID | None = None
    langue: str | None = None
    cree_par: uuid.UUID
    cree_le: datetime.datetime
    maj_le: datetime.datetime
    nb_utilisations: int

class Session(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: uuid.UUID
    compte_id: uuid.UUID
    jeton_empreinte: str
    cree_le: datetime.datetime
    expire_le: datetime.datetime
    revoque_le: datetime.datetime | None = None
    agent: str | None = None

class Evenement(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    evenement_id: uuid.UUID
    type: str
    module: str
    cible: str | None = None
    charge: dict | list
    cree_le: datetime.datetime
    prochaine_tentative: datetime.datetime
    tentatives: int
    traite_le: datetime.datetime | None = None
    abandonne: bool | None = None
    erreur: str | None = None

CONTRAT = {"comm": Comm, "comm_email": CommEmail, "comm_interne": CommInterne, "comm_groupe": CommGroupe, "participant": Participant, "piece_jointe": PieceJointe, "comm_piece_jointe": CommPieceJointe, "blob": Blob, "correspondant": Correspondant, "adresse": Adresse, "domaine": Domaine, "identite": Identite, "compte": Compte, "boite": Boite, "rattachement": Rattachement, "acces": Acces, "lecture_groupe": LectureGroupe, "application": Application, "axe": Axe, "tag": Tag, "comm_tag": CommTag, "dossier": Dossier, "filtre": Filtre, "envoi": Envoi, "envoi_destinataire": EnvoiDestinataire, "dmarc_rapport": DmarcRapport, "dmarc_ligne": DmarcLigne, "analyse": Analyse, "note": Note, "parametre": Parametre, "journal": Journal, "modele": Modele, "session": Session, "evenement": Evenement}
