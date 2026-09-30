"""CE QU'ATOMBOX DONNE À VOIR EN IMAP (D180) — la traduction entre notre modèle et celui d'un client.

La session ne connaît que cette interface ; c'est elle qui parle à la base et au magasin. Le
découpage n'est pas décoratif : il permet d'éprouver tout le dialogue avec une vue doublée, et il
isole en un seul endroit les choix de traduction — lesquels sont des choix de PRODUIT, pas de
protocole.

Trois d'entre eux méritent d'être dits :

1. **Une boîte aux lettres IMAP est une ligne de `dossier`** (D183) — un dossier utilisateur, ou
   l'une des quatre boîtes d'état (Traités, Archivés, Corbeille, Indésirables). Quand le compte a
   plusieurs boîtes, les noms se préfixent par l'adresse (`contact@exemple.fr/Archive`) : sans ça,
   deux « INBOX » se marchent dessus et le client n'a aucun moyen de les distinguer. La boîte
   principale garde le nom nu `INBOX`, qu'IMAP traite à part (RFC 3501 § 5.1).

   **Déplacer un message vers `Archive`, c'est écrire son état** — pas le recopier. C'est le sens de
   la demande, et c'est ce que `MOVE` fait ici : `exit_reason` change, le message apparaît dans la
   boîte d'arrivée avec un UID neuf, et disparaît de celle d'où il vient.

2. **Les drapeaux sont PERSONNELS** (D175 § 3, RM3320). Ils ont été collectifs le temps que l'état
   personnel n'existe pas ; il existe. Et c'est ici que ça se justifie le mieux : une session IMAP
   est authentifiée par UN compte, donc `\\Seen` et `\\Flagged` ne peuvent dire que « MOI je l'ai
   ouvert », « MOI je l'ai marqué ». Sur une boîte partagée, deux clients voient deux états — ce qui
   est la vérité, et ce que l'ancien modèle ne savait pas exprimer.

3. **Le corps servi est l'octet du magasin**, jamais une reconstruction. C'est l'exigence de D025 et
   de RM3213 : un client qui télécharge un message doit obtenir le fichier d'origine, pas notre
   idée de ce qu'il contient.
"""
from __future__ import annotations
import email.utils
from datetime import datetime, timezone
from sqlalchemy import select
from ..journal import journal
from ..schema.modeles import Acces, Adresse, Boite, Comm, CommEmail, Compte, Dossier, Rattachement

log = journal("imap")


class BoiteAuxLettres:
    """une boîte aux lettres telle qu'un client la voit : un nom, des UID, une validité"""

    def __init__(self, nom, dossier, uids, uid_validity, uid_next, special_use=None, etat=None):
        self.nom, self.dossier_id = nom, dossier
        self.uids, self.uid_validity, self.uid_next = uids, uid_validity, uid_next
        self.etat = etat                 # l'exit_reason que cette boîte représente, ou None
        # SPECIAL-USE (RFC 6154) : c'est ce qui permet à un client de savoir qu'une boîte EST la
        # corbeille, et donc d'y envoyer le bouton « supprimer », sans que l'utilisateur configure
        # quoi que ce soit. Sans cet attribut, Thunderbird crée SA propre « Trash » à côté.
        self.attributs = ["\\HasNoChildren"] + ([special_use] if special_use else [])


class MessageServi:
    """un message, vu d'un client : ses drapeaux, sa taille, et ses octets à la demande"""

    def __init__(self, uid, comm, rattachement, magasin, blob_ref, message_id=None, etat=None):
        self.uid, self._c, self._r = uid, comm, rattachement
        self._magasin, self._blob, self._message_id = magasin, blob_ref, message_id
        self.taille = comm.taille or 0
        self.date_interne = email.utils.format_datetime(comm.date_recue).replace(",", "")[:26] \
            if comm.date_recue else "01-Jan-1970 00:00:00 +0000"
        # DEUX ORIGINES, ET C'EST LE FOND DE D175 : `\\Seen` et `\\Flagged` viennent de l'état
        # PERSONNEL du compte connecté (`etat` absent = il n'y a jamais touché) ; `\\Answered` et
        # `\\Deleted` viennent du rattachement, parce que répondre et supprimer sont des actes
        # COLLECTIFS — tout le monde voit qu'il y a été répondu.
        self.drapeaux = []
        if etat is not None and etat.vu: self.drapeaux.append("\\Seen")
        if etat is not None and etat.flagged: self.drapeaux.append("\\Flagged")
        if rattachement.repondu_le is not None: self.drapeaux.append("\\Answered")
        if rattachement.exit_reason == "deleted": self.drapeaux.append("\\Deleted")

    def enveloppe(self):
        """ENVELOPPE au sens RFC 3501 § 7.4.2 — l'ordre des dix champs est imposé et ne se devine pas"""
        c = self._c
        une = lambda adr, nom: [[nom, None, adr.split("@")[0], adr.split("@")[-1]]] if adr else None
        de = une(c.from_adresse, c.from_nom)
        return [email.utils.format_datetime(c.date_recue) if c.date_recue else None,
                c.sujet, de, de, de, None, None, None, None, self._message_id]

    def structure(self):
        """BODYSTRUCTURE minimal : on annonce UNE partie texte de la bonne taille.

        Décrire faux la structure interne serait pire que de ne rien dire : le client s'en sert
        pour décider quoi télécharger, et irait chercher des parties qui n'existent pas. Tant qu'on
        ne sait pas la rendre exactement, on annonce le message comme un tout — et `BODY[]` le
        rend à l'octet."""
        return ["TEXT", "PLAIN", ["CHARSET", "UTF-8"], None, None, "8BIT", self.taille,
                max(1, (self._c.corps_texte or "").count("\n") + 1)]

    def octets(self, section: str):
        brut = self._magasin.lire(self._blob) if self._blob else None
        if brut is None: return None
        s = (section or "").upper()
        if s in ("", "TEXT") and s != "TEXT": return brut
        tete, _, corps = brut.partition(b"\r\n\r\n")
        if s == "HEADER": return tete + b"\r\n\r\n"
        if s == "TEXT": return corps
        if s.startswith("HEADER.FIELDS"):
            champs = {c.strip().lower() for c in s[s.index("(") + 1:s.rindex(")")].split()} if "(" in s else set()
            gardees, garde = [], False
            for ligne in tete.split(b"\r\n"):
                if ligne[:1] in (b" ", b"\t"):                    # une suite de l'en-tête précédent
                    if garde: gardees.append(ligne)
                    continue
                garde = ligne.split(b":", 1)[0].decode("latin-1", "replace").strip().lower() in champs
                if garde: gardees.append(ligne)
            return b"\r\n".join(gardees) + b"\r\n\r\n"
        log.info("section de corps non servie : %r", section)
        return None


class Vue:
    """La vue servie à une session. Une session = un compte = une connexion à la base.

    Elle garde sa propre session SQLAlchemy SYNCHRONE : le serveur IMAP tourne dans son processus,
    et mélanger une session asynchrone partagée avec des connexions de longue durée est le meilleur
    moyen de bloquer tout le monde derrière un client qui télécharge un gros message."""

    def __init__(self, session, magasin):
        self.s, self.magasin = session, magasin
        self.compte = None     # posé à l'authentification : les drapeaux servis sont les SIENS

    # ── qui es-tu ───────────────────────────────────────────────────────────────────────────────
    def authentifier(self, identifiant: str, mot_de_passe: str):
        from ..api.securite import verifier_mot_de_passe
        c = self.s.scalar(select(Compte).where(Compte.login == (identifiant or "").strip().lower()))
        if c is None or not c.actif: return None
        if not verifier_mot_de_passe(mot_de_passe or "", c.mot_de_passe_empreinte): return None
        self.compte = c
        return c

    # ── que vois-tu ─────────────────────────────────────────────────────────────────────────────
    def _dossiers(self, compte):
        """(nom IMAP, Dossier) pour tout ce que ce compte peut voir, la boîte principale en tête"""
        boites = list(self.s.scalars(select(Boite).join(Acces, Acces.boite_id == Boite.boite_id)
                                     .where(Acces.compte_id == compte.compte_id, Acces.fin.is_(None))))
        sortie = []
        for i, b in enumerate(boites):
            adresse = self.s.get(Adresse, b.adresse_id).adresse_complete
            from ..services.mailbox import nom_servi
            for d in self.s.scalars(select(Dossier).where(Dossier.boite_id == b.boite_id).order_by(Dossier.nom)):
                alias = nom_servi(d)
                # La boîte PRINCIPALE garde le nom nu : IMAP traite « INBOX » à part (RFC 3501
                # § 5.1), et un client qui ne trouve pas d'INBOX refuse souvent de continuer.
                nom = alias if i == 0 else "%s/%s" % (adresse, alias)
                sortie.append((nom, d))
        return sortie

    def boites(self, compte):
        return [self._boite(nom, d) for nom, d in self._dossiers(compte)]

    def _boite(self, nom, d):
        uids = [u for (u,) in self.s.execute(
            select(Rattachement.uid_servi).where(Rattachement.dossier_id == d.dossier_id,
                                                 Rattachement.uid_servi.isnot(None))
            .order_by(Rattachement.uid_servi))]
        return BoiteAuxLettres(nom, d.dossier_id, uids, d.uid_validity_servie or 1,
                               d.uid_servi_suivant or 1, d.special_use, d.exit_reason)

    def ouvrir(self, compte, nom):
        for n, d in self._dossiers(compte):
            if n.lower() == (nom or "").lower(): return self._boite(n, d)
        return None

    def etat(self, compte, nom):
        b = self.ouvrir(compte, nom)
        if b is None: return None
        # UNSEEN est le compte de CE client, pas celui de la boîte (D175) : deux personnes sur une
        # boîte partagée n'ont pas le même nombre de non-lus, et annoncer un chiffre commun ferait
        # clignoter l'une pour ce que l'autre a déjà lu.
        from ..services.personal_state import a_voir_par
        non_lus = self.s.scalar(select(__import__("sqlalchemy").func.count()).select_from(Rattachement)
                                .where(Rattachement.dossier_id == b.dossier_id,
                                       a_voir_par(compte.compte_id))) or 0
        return {"MESSAGES": len(b.uids), "RECENT": 0, "UIDNEXT": b.uid_next,
                "UIDVALIDITY": b.uid_validity, "UNSEEN": non_lus}

    # ── que contient-il ─────────────────────────────────────────────────────────────────────────
    def message(self, boite, uid: int):
        r = self.s.scalar(select(Rattachement).where(Rattachement.dossier_id == boite.dossier_id,
                                                     Rattachement.uid_servi == uid))
        if r is None: return None
        c = self.s.get(Comm, r.comm_id)
        e = self.s.get(CommEmail, r.comm_id)
        if c is None: return None
        from ..services.personal_state import etat_sync
        etat = etat_sync(self.s, self.compte.compte_id if self.compte else None, r.comm_id, r.boite_id)
        return MessageServi(uid, c, r, self.magasin, e.blob_ref if e else None,
                            message_id=e.message_id if e else None, etat=etat)

    def contient(self, boite, uid: int, champ: str, aiguille: str) -> bool:
        m = self.message(boite, uid)
        if m is None: return False
        c = m._c
        ou = {"FROM": (c.from_adresse or "") + " " + (c.from_nom or ""), "SUBJECT": c.sujet or "",
              "BODY": c.corps_texte or "", "TEXT": " ".join(filter(None, [c.sujet, c.corps_texte, c.from_adresse]))}
        if champ in ("TO", "CC"):
            from ..schema.modeles import Participant
            roles = [p.adresse for p in self.s.scalars(
                select(Participant).where(Participant.comm_id == c.comm_id, Participant.role == champ.lower()))]
            return aiguille in " ".join(roles).lower()
        return aiguille in (ou.get(champ, "")).lower()

    def annuler(self):
        """rend la session utilisable après une écriture refusée — appelée par la session IMAP.

        C'est la vue qui tient la session SQLAlchemy, donc c'est elle qui sait l'annuler. Sans ça,
        une seule erreur d'écriture rendait la connexion entière inutilisable jusqu'à reconnexion."""
        self.s.rollback()

    # ── que peut-on écrire ──────────────────────────────────────────────────────────────────────
    def dossier_nomme(self, compte, nom):
        """le Dossier derrière un nom IMAP, ou None — la destination d'un MOVE"""
        for n, d in self._dossiers(compte):
            if n.lower() == (nom or "").lower(): return d
        return None

    def deplacer(self, compte, boite, uids: list[int], nom_dest: str):
        """MOVE — écrit l'ÉTAT du message, et rend [(uid source, uid d'arrivée)].

        Ce n'est pas une copie suivie d'une suppression : c'est UNE écriture, celle de
        `exit_reason`, faite par le même service que le clic du webmail (D183). Rend None si la
        destination n'existe pas, pour que la session réponde `TRYCREATE` plutôt qu'un succès muet.

        LE MESSAGE NE PEUT PAS ÊTRE DANS DEUX BOÎTES DE LA MÊME ADRESSE : la clé du rattachement
        est (message, boîte), et c'est le modèle — un message reçu est dans une et une seule des
        cinq (D175 § 4). Un déplacement est donc le seul geste possible, et le bon."""
        from ..services import mailbox
        dest = self.dossier_nomme(compte, nom_dest)
        if dest is None: return None
        couples = []
        for uid in uids:
            r = self.s.scalar(select(Rattachement).where(Rattachement.dossier_id == boite.dossier_id,
                                                        Rattachement.uid_servi == uid))
            if r is None: continue
            # L'ÉTAT SUIT LA DESTINATION : une boîte d'état l'impose, un dossier ordinaire le remet
            # à rien — sortir de la corbeille en déplaçant vers INBOX, c'est la même écriture.
            mailbox.deplacer_sync(self.s, r, dest.exit_reason, compte.compte_id, cible=dest)
            couples.append((uid, r.uid_servi))
        self.s.commit()
        if couples: log.info("MOVE de %d message(s) vers « %s » (état %s)",
                             len(couples), nom_dest, dest.exit_reason or "aucun")
        return couples

    def drapeaux(self, compte, boite, uids: list[int], ajouter: list[str], retirer: list[str]):
        """STORE — les drapeaux qu'on sait écrire, et rien d'autre.

        `\\Seen` et `\\Flagged` vont sur l'état PERSONNEL du compte connecté (D175) ; `\\Deleted`
        est une TRANSITION vers la corbeille, pas un drapeau qu'on pose à côté — c'est la
        traduction du modèle, et elle est volontaire : un client qui supprime un message doit le
        retrouver dans la corbeille, pas le voir disparaître.

        Un `\\Seen` RETIRÉ ne détruit pas la date d'ouverture : il pose « à revoir » (D175 § 2).
        Le message repasse en gras chez le client comme dans le webmail, et le fait reste écrit."""
        from ..services import mailbox, personal_state as perso
        touches = []
        for uid in uids:
            r = self.s.scalar(select(Rattachement).where(Rattachement.dossier_id == boite.dossier_id,
                                                        Rattachement.uid_servi == uid))
            if r is None: continue
            for f in ajouter:
                if f == "\\Seen":
                    self.s.execute(perso.ordre_ouvrir(compte.compte_id, r.comm_id, r.boite_id))
                    perso.retirer_sync(self.s, compte.compte_id, r.comm_id, r.boite_id, perso.A_REVOIR)
                elif f == "\\Flagged":
                    self.s.execute(perso.ordre_drapeau(compte.compte_id, r.comm_id, r.boite_id, True))
                elif f == "\\Deleted" and r.exit_reason != "deleted":
                    mailbox.deplacer_sync(self.s, r, "deleted", compte.compte_id)
                elif f == "\\Answered":
                    r.repondu_le = r.repondu_le or datetime.now(timezone.utc)
            for f in retirer:
                if f == "\\Seen":
                    perso.poser_sync(self.s, compte.compte_id, r.comm_id, r.boite_id, perso.A_REVOIR)
                elif f == "\\Flagged":
                    self.s.execute(perso.ordre_drapeau(compte.compte_id, r.comm_id, r.boite_id, False))
                elif f == "\\Deleted" and r.exit_reason == "deleted":
                    mailbox.deplacer_sync(self.s, r, None, compte.compte_id)
            touches.append(uid)
        self.s.commit()
        return touches
