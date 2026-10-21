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
from ..schema.models import Acces, Adresse, Boite, Comm, CommEmail, Compte, Dossier, Rattachement

log = journal("imap")


class Mailbox:
    """une boîte aux lettres telle qu'un client la voit : un nom, des UID, une validité"""

    def __init__(self, name, dossier, uids, uid_validity, uid_next, special_use=None, state=None):
        self.name, self.dossier_id = name, dossier
        self.uids, self.uid_validity, self.uid_next = uids, uid_validity, uid_next
        self.state = state                 # l'exit_reason que cette boîte représente, ou None
        # SPECIAL-USE (RFC 6154) : c'est ce qui permet à un client de savoir qu'une boîte EST la
        # corbeille, et donc d'y envoyer le bouton « supprimer », sans que l'utilisateur configure
        # quoi que ce soit. Sans cet attribut, Thunderbird crée SA propre « Trash » à côté.
        self.attributes = ["\\HasNoChildren"] + ([special_use] if special_use else [])


class ServedMessage:
    """un message, vu d'un client : ses drapeaux, sa taille, et ses octets à la demande"""

    def __init__(self, uid, comm, rattachement, store, blob_ref, message_id=None, state=None):
        self.uid, self._c, self._r = uid, comm, rattachement
        self._store, self._blob, self._message_id = store, blob_ref, message_id
        self.size = comm.taille or 0
        self.internal_date = email.utils.format_datetime(comm.date_recue).replace(",", "")[:26] \
            if comm.date_recue else "01-Jan-1970 00:00:00 +0000"
        # DEUX ORIGINES, ET C'EST LE FOND DE D175 : `\\Seen` et `\\Flagged` viennent de l'état
        # PERSONNEL du compte connecté (`etat` absent = il n'y a jamais touché) ; `\\Answered` et
        # `\\Deleted` viennent du rattachement, parce que répondre et supprimer sont des actes
        # COLLECTIFS — tout le monde voit qu'il y a été répondu.
        self.flags = []
        if state is not None and state.seen: self.flags.append("\\Seen")
        if state is not None and state.flagged: self.flags.append("\\Flagged")
        if rattachement.repondu_le is not None: self.flags.append("\\Answered")
        # ON NE SERT JAMAIS `\\Deleted`, ET C'EST UN CHOIX DE TRADUCTION, pas un oubli.
        #
        # En IMAP, `\\Deleted` veut dire « marqué pour suppression, en attente d'EXPUNGE » — pas
        # « supprimé ». Les clients le traitent comme tel : Thunderbird MASQUE par défaut les
        # messages qui le portent. Le servir sur les messages de la corbeille les rendait donc
        # invisibles — reçus, et cachés. Constaté en produit, et introuvable autrement qu'en
        # lisant ce que le serveur met sur le fil.
        #
        # Chez nous, un message de la corbeille n'attend rien : il EST dans la corbeille, et il
        # n'en sortira pas tout seul (D118 : un rattachement supprimé n'est jamais effacé). L'état
        # est porté par la BOÎTE AUX LETTRES où il se trouve, ce qui est exactement ce que D183
        # voulait dire — les cinq états sont des boîtes, pas des drapeaux.
        #
        # Le client peut toujours POSER `\\Deleted` (c'est sa façon de dire « supprime »), et
        # `PERMANENTFLAGS` l'annonce : c'est ce STORE qui déplace vers la corbeille.

    def envelope(self):
        """ENVELOPPE au sens RFC 3501 § 7.4.2 — l'ordre des dix champs est imposé et ne se devine pas"""
        c = self._c
        one = lambda adr, name: [[name, None, adr.split("@")[0], adr.split("@")[-1]]] if adr else None
        sender = one(c.from_adresse, c.from_nom)
        return [email.utils.format_datetime(c.date_recue) if c.date_recue else None,
                c.sujet, sender, sender, sender, None, None, None, None, self._message_id]

    def structure(self):
        """BODYSTRUCTURE minimal : on annonce UNE partie texte de la bonne taille.

        Décrire faux la structure interne serait pire que de ne rien dire : le client s'en sert
        pour décider quoi télécharger, et irait chercher des parties qui n'existent pas. Tant qu'on
        ne sait pas la rendre exactement, on annonce le message comme un tout — et `BODY[]` le
        rend à l'octet."""
        return ["TEXT", "PLAIN", ["CHARSET", "UTF-8"], None, None, "8BIT", self.size,
                max(1, (self._c.corps_texte or "").count("\n") + 1)]

    def section_bytes(self, section: str):
        raw = self._store.read(self._blob) if self._blob else None
        if raw is None: return None
        s = (section or "").upper()
        if s in ("", "TEXT") and s != "TEXT": return raw
        head, _, body = raw.partition(b"\r\n\r\n")
        if s == "HEADER": return head + b"\r\n\r\n"
        if s == "TEXT": return body
        if s.startswith("HEADER.FIELDS"):
            fields = {c.strip().lower() for c in s[s.index("(") + 1:s.rindex(")")].split()} if "(" in s else set()
            kept, keep = [], False
            for line in head.split(b"\r\n"):
                if line[:1] in (b" ", b"\t"):                    # une suite de l'en-tête précédent
                    if keep: kept.append(line)
                    continue
                keep = line.split(b":", 1)[0].decode("latin-1", "replace").strip().lower() in fields
                if keep: kept.append(line)
            return b"\r\n".join(kept) + b"\r\n\r\n"
        log.info("section de corps non servie : %r", section)
        return None


class View:
    """La vue servie à une session. Une session = un compte = une connexion à la base.

    Elle garde sa propre session SQLAlchemy SYNCHRONE : le serveur IMAP tourne dans son processus,
    et mélanger une session asynchrone partagée avec des connexions de longue durée est le meilleur
    moyen de bloquer tout le monde derrière un client qui télécharge un gros message."""

    def __init__(self, session, store):
        self.s, self.store = session, store
        self.compte = None     # posé à l'authentification : les drapeaux servis sont les SIENS

    # ── qui es-tu ───────────────────────────────────────────────────────────────────────────────
    def authenticate(self, login: str, password: str):
        from ..api.security import verify_password
        c = self.s.scalar(select(Compte).where(Compte.login == (login or "").strip().lower()))
        if c is None or not c.actif: return None
        if not verify_password(password or "", c.mot_de_passe_empreinte): return None
        self.compte = c
        return c

    # ── que vois-tu ─────────────────────────────────────────────────────────────────────────────
    def _boxes(self, compte):
        """les boîtes du compte, la PRINCIPALE en tête — dans un ordre STABLE.

        Sans ORDER BY, « la première » était celle que PostgreSQL rendait en premier : deux sessions
        pouvaient ne pas s'accorder sur laquelle porte le nom nu `INBOX`, et un compte à deux boîtes
        voyait ses dossiers changer de nom d'une connexion à l'autre. uuid v7 : l'ordre de création."""
        return list(self.s.scalars(select(Boite).join(Acces, Acces.boite_id == Boite.boite_id)
                                   .where(Acces.compte_id == compte.compte_id, Acces.fin.is_(None))
                                   .order_by(Boite.boite_id)))

    def _box_for(self, compte, name: str):
        """(Boite, alias relatif) — à quelle boîte appartient un nom IMAP qu'on va CRÉER.

        Le pendant de `_folders` : la principale porte des noms nus, les autres sont préfixées par
        leur adresse (`contact@exemple.fr/Projets`)."""
        boxes = self._boxes(compte)
        if not boxes: return None, None
        for b in boxes[1:]:
            adresse = self.s.get(Adresse, b.adresse_id).adresse_complete
            if (name or "").lower().startswith(adresse.lower() + "/"):
                return b, name[len(adresse) + 1:]
        return boxes[0], name

    def _folders(self, compte):
        """(nom IMAP, Dossier) pour tout ce que ce compte peut voir, la boîte principale en tête"""
        boxes = self._boxes(compte)
        out = []
        for i, b in enumerate(boxes):
            adresse = self.s.get(Adresse, b.adresse_id).adresse_complete
            from ..services.mailbox import served_name
            for d in self.s.scalars(select(Dossier).where(Dossier.boite_id == b.boite_id).order_by(Dossier.nom)):
                alias = served_name(d)
                # La boîte PRINCIPALE garde le nom nu : IMAP traite « INBOX » à part (RFC 3501
                # § 5.1), et un client qui ne trouve pas d'INBOX refuse souvent de continuer.
                name = alias if i == 0 else "%s/%s" % (adresse, alias)
                out.append((name, d))
        return out

    def mailboxes(self, compte):
        return [self._mailbox(name, d) for name, d in self._folders(compte)]

    def _mailbox(self, name, d):
        uids = [u for (u,) in self.s.execute(
            select(Rattachement.uid_servi).where(Rattachement.dossier_id == d.dossier_id,
                                                 Rattachement.uid_servi.isnot(None))
            .order_by(Rattachement.uid_servi))]
        return Mailbox(name, d.dossier_id, uids, d.uid_validity_servie or 1,
                               d.uid_servi_suivant or 1, d.special_use, d.exit_reason)

    def open_mailbox(self, compte, name):
        for n, d in self._folders(compte):
            if n.lower() == (name or "").lower(): return self._mailbox(n, d)
        return None

    def status(self, compte, name):
        b = self.open_mailbox(compte, name)
        if b is None: return None
        # UNSEEN est le compte de CE client, pas celui de la boîte (D175) : deux personnes sur une
        # boîte partagée n'ont pas le même nombre de non-lus, et annoncer un chiffre commun ferait
        # clignoter l'une pour ce que l'autre a déjà lu.
        from ..services.personal_state import needs_attention_by
        unread = self.s.scalar(select(__import__("sqlalchemy").func.count()).select_from(Rattachement)
                                .where(Rattachement.dossier_id == b.dossier_id,
                                       needs_attention_by(compte.compte_id))) or 0
        return {"MESSAGES": len(b.uids), "RECENT": 0, "UIDNEXT": b.uid_next,
                "UIDVALIDITY": b.uid_validity, "UNSEEN": unread}

    # ── que contient-il ─────────────────────────────────────────────────────────────────────────
    def message(self, mailbox, uid: int):
        r = self.s.scalar(select(Rattachement).where(Rattachement.dossier_id == mailbox.dossier_id,
                                                     Rattachement.uid_servi == uid))
        if r is None: return None
        c = self.s.get(Comm, r.comm_id)
        e = self.s.get(CommEmail, r.comm_id)
        if c is None: return None
        from ..services.personal_state import state_sync
        state = state_sync(self.s, self.compte.compte_id if self.compte else None, r.comm_id, r.boite_id)
        return ServedMessage(uid, c, r, self.store, e.blob_ref if e else None,
                            message_id=e.message_id if e else None, state=state)

    def contains(self, mailbox, uid: int, field: str, needle: str) -> bool:
        m = self.message(mailbox, uid)
        if m is None: return False
        c = m._c
        ou = {"FROM": (c.from_adresse or "") + " " + (c.from_nom or ""), "SUBJECT": c.sujet or "",
              "BODY": c.corps_texte or "", "TEXT": " ".join(filter(None, [c.sujet, c.corps_texte, c.from_adresse]))}
        if field in ("TO", "CC"):
            from ..schema.models import Participant
            roles = [p.adresse for p in self.s.scalars(
                select(Participant).where(Participant.comm_id == c.comm_id, Participant.role == field.lower()))]
            return needle in " ".join(roles).lower()
        return needle in (ou.get(field, "")).lower()

    def release(self):
        """termine la transaction de LECTURE en cours, sans rien perdre — les écritures ont été validées.

        Une session SQLAlchemy ouvre une transaction à la première requête et la garde jusqu'au commit.
        Un client IMAP qui lit puis attend — entre deux commandes, et surtout pendant IDLE, jusqu'à
        29 minutes — laissait donc une connexion « idle in transaction ». C'est elle qui, le 19/09, a
        fait attendre une migration onze minutes en bloquant les lectures. Une lecture finie se
        relâche."""
        if self.s is None: return
        try:
            self.s.rollback()
        except Exception:
            log.exception("relâchement de la transaction en échec")

    def rollback(self):
        """rend la session utilisable après une écriture refusée — appelée par la session IMAP.

        C'est la vue qui tient la session SQLAlchemy, donc c'est elle qui sait l'annuler. Sans ça,
        une seule erreur d'écriture rendait la connexion entière inutilisable jusqu'à reconnexion."""
        self.s.rollback()

    # ── que peut-on écrire ──────────────────────────────────────────────────────────────────────
    def folder_named(self, compte, name):
        """le Dossier derrière un nom IMAP, ou None — la destination d'un MOVE"""
        for n, d in self._folders(compte):
            if n.lower() == (name or "").lower(): return d
        return None

    def move(self, compte, mailbox, uids: list[int], dest_name: str):
        """MOVE — écrit l'ÉTAT du message, et rend [(uid source, uid d'arrivée)].

        Ce n'est pas une copie suivie d'une suppression : c'est UNE écriture, celle de
        `exit_reason`, faite par le même service que le clic du webmail (D183). Rend None si la
        destination n'existe pas, pour que la session réponde `TRYCREATE` plutôt qu'un succès muet.

        LE MESSAGE NE PEUT PAS ÊTRE DANS DEUX BOÎTES DE LA MÊME ADRESSE : la clé du rattachement
        est (message, boîte), et c'est le modèle — un message reçu est dans une et une seule des
        cinq (D175 § 4). Un déplacement est donc le seul geste possible, et le bon."""
        from ..services.mailbox import move_sync
        dest = self.folder_named(compte, dest_name)
        if dest is None: return None
        pairs = []
        for uid in uids:
            r = self.s.scalar(select(Rattachement).where(Rattachement.dossier_id == mailbox.dossier_id,
                                                        Rattachement.uid_servi == uid))
            if r is None: continue
            # L'ÉTAT SUIT LA DESTINATION : une boîte d'état l'impose, un dossier ordinaire le remet
            # à rien — sortir de la corbeille en déplaçant vers INBOX, c'est la même écriture.
            move_sync(self.s, r, dest.exit_reason, compte.compte_id, cible=dest)
            pairs.append((uid, r.uid_servi))
        self.s.commit()
        if pairs: log.info("MOVE de %d message(s) vers « %s » (état %s)",
                             len(pairs), dest_name, dest.exit_reason or "aucun")
        return pairs

    def append(self, compte, name: str, raw: bytes, flags: list[str], when):
        """APPEND — dépose un message dans une boîte aux lettres, et rend (UIDVALIDITY, UID).

        Rend None si la boîte n'existe pas (la session répond TRYCREATE), et un UID None si le message
        était déjà rangé ailleurs dans cette adresse : un rattachement est UNE boîte aux lettres
        (D175 § 4), et le déplacer en douce déferait le rangement de quelqu'un.

        DEUX TRADUCTIONS, comme pour MOVE :

        - **le sens suit la boîte** : déposé dans Envoyés ou Brouillons, c'est un message SORTANT —
          Thunderbird a envoyé par son propre SMTP et range sa copie ; ailleurs, un message reçu ;
        - **un envoyé déposé est un envoi** : on émet `message.envoye`, dont l'abonné copie le message
          dans les Envoyés du FOURNISSEUR (D140c). Sans ça, le téléphone — qui lit le fournisseur —
          ne verrait jamais ce que l'on a envoyé depuis Thunderbird. L'abonné est idempotent : il
          retrouve sa copie par le Message-ID au lieu d'en faire une seconde."""
        dest = self.folder_named(compte, name)
        if dest is None: return None
        from ..ingestion.ingestion import ingest
        from ..services.messages import special_of
        special = None if dest.exit_reason else special_of(dest.alias_imap)
        res = ingest(self.s, self.store, dest.boite_id, raw, dossier_id=dest.dossier_id, date_recue=when,
                     sens="out" if special in ("sent", "drafts") else "in", apply_rules=False)
        if res.get("comm_id") is None:
            log.info("APPEND vers « %s » : ignoré par un module", name); return (dest.uid_validity_servie or 1, None)
        r = self.s.get(Rattachement, (res["comm_id"], dest.boite_id))
        if r is None or r.dossier_id != dest.dossier_id:
            log.info("APPEND vers « %s » : %s est déjà rangé ailleurs dans cette adresse", name, res["comm_id"])
            return (dest.uid_validity_servie or 1, None)
        from ..services import personal_state as personal
        if "\\Seen" in flags: self.s.execute(personal.open_stmt(compte.compte_id, r.comm_id, r.boite_id))
        if "\\Flagged" in flags: self.s.execute(personal.flag_stmt(compte.compte_id, r.comm_id, r.boite_id, True))
        if "\\Answered" in flags: r.repondu_le = r.repondu_le or datetime.now(timezone.utc)
        if special == "sent":
            from ..modules import events
            events.emit(self.s, "message.envoye", {"comm_id": str(r.comm_id), "boite_id": str(r.boite_id), "refuses": []},
                        module="imap")
        self.s.commit()
        self.s.refresh(dest)
        log.info("APPEND dans « %s » : %s, uid %s%s", name, r.comm_id, r.uid_servi,
                 " (nouveau)" if res.get("nouveau") else " (déjà connu)")
        return (dest.uid_validity_servie or 1, r.uid_servi)

    # ── les dossiers (RM3499) : les MÊMES règles que le webmail, dans `services.folders_util` ──────
    def create(self, compte, name: str):
        from ..services import folders_util as f
        if self.folder_named(compte, name) is not None: raise f.FolderRefused("ce dossier existe déjà", "ALREADYEXISTS")
        boite, alias = self._box_for(compte, name)
        if boite is None: raise f.FolderRefused("aucune boîte", "NONEXISTENT")
        f.create_folder_sync(self.s, boite, alias)

    def rename(self, compte, old: str, new: str):
        from ..services import folders_util as f
        d = self.folder_named(compte, old)
        if d is None: raise f.FolderRefused("boîte aux lettres inconnue : %s" % old, "NONEXISTENT")
        boite, alias = self._box_for(compte, new)
        if boite is None or boite.boite_id != d.boite_id:
            raise f.FolderRefused("un dossier ne change pas d'adresse", "CANNOT")
        f.rename_folder_sync(self.s, boite, d, alias)

    def delete(self, compte, name: str):
        from ..services import folders_util as f
        d = self.folder_named(compte, name)
        if d is None: raise f.FolderRefused("boîte aux lettres inconnue : %s" % name, "NONEXISTENT")
        try:
            f.delete_folder_sync(self.s, self.s.get(Boite, d.boite_id), d)
        except PermissionError as e:
            raise f.FolderRefused(str(e), "CANNOT")

    def store_flags(self, compte, mailbox, uids: list[int], to_add: list[str], to_remove: list[str]):
        """STORE — les drapeaux qu'on sait écrire, et rien d'autre.

        `\\Seen` et `\\Flagged` vont sur l'état PERSONNEL du compte connecté (D175) ; `\\Deleted`
        est une TRANSITION vers la corbeille, pas un drapeau qu'on pose à côté — c'est la
        traduction du modèle, et elle est volontaire : un client qui supprime un message doit le
        retrouver dans la corbeille, pas le voir disparaître.

        Un `\\Seen` RETIRÉ ne détruit pas la date d'ouverture : il pose « à revoir » (D175 § 2).
        Le message repasse en gras chez le client comme dans le webmail, et le fait reste écrit."""
        from ..services.mailbox import move_sync
        from ..services import personal_state as personal
        touched = []
        for uid in uids:
            r = self.s.scalar(select(Rattachement).where(Rattachement.dossier_id == mailbox.dossier_id,
                                                        Rattachement.uid_servi == uid))
            if r is None: continue
            for f in to_add:
                if f == "\\Seen":
                    self.s.execute(personal.open_stmt(compte.compte_id, r.comm_id, r.boite_id))
                    personal.unset_marker_sync(self.s, compte.compte_id, r.comm_id, r.boite_id, personal.TO_REVIEW)
                elif f == "\\Flagged":
                    self.s.execute(personal.flag_stmt(compte.compte_id, r.comm_id, r.boite_id, True))
                elif f == "\\Deleted" and r.exit_reason != "deleted":
                    move_sync(self.s, r, "deleted", compte.compte_id)
                elif f == "\\Answered":
                    r.repondu_le = r.repondu_le or datetime.now(timezone.utc)
            for f in to_remove:
                if f == "\\Seen":
                    personal.set_marker_sync(self.s, compte.compte_id, r.comm_id, r.boite_id, personal.TO_REVIEW)
                elif f == "\\Flagged":
                    self.s.execute(personal.flag_stmt(compte.compte_id, r.comm_id, r.boite_id, False))
                elif f == "\\Deleted" and r.exit_reason == "deleted":
                    move_sync(self.s, r, None, compte.compte_id)
            touched.append(uid)
        self.s.commit()
        return touched
