"""LE MODULE D'ÉMISSION — @evenement("message.a_envoyer") : au moins une fois, hors processus (D161)."""
from __future__ import annotations
import os, uuid
from datetime import datetime, timezone
from sqlalchemy import select
from ..journal import journal
from ..magasin import Magasin
from ..controleurs.envois import EnvoisControleur
from ..modules import Module, evenement
from ..modules import evenements
from ..schema.modeles import Adresse, Boite, Comm, Envoi, EnvoiDestinataire, Identite
from ..uuid7 import uuid7
from ..ingestion.ingestion import adresse as adresse_de
from .smtp import remettre

log = journal("apps")

class ModuleEmission(Module):
    nom = "emission"; version = "0.1"; description = "remise au relais SMTP (F109, D114), envoi et destinataires, suivi et relance (D099)"; interne = True
    controleurs = [EnvoisControleur]

    @evenement("message.a_envoyer")
    def envoyer(self, ctx):
        s = ctx["session"]; charge = ctx["charge"]
        comm_id = uuid.UUID(charge["comm_id"]); boite_id = uuid.UUID(charge["boite_id"]); dest = list(charge.get("destinataires") or [])
        comm = s.get(Comm, comm_id); boite = s.get(Boite, boite_id)
        if not comm or not boite: raise RuntimeError("message ou boîte introuvable : %s" % comm_id)
        expediteur = s.get(Adresse, boite.adresse_id).adresse_complete
        identite = s.scalar(select(Identite).where(Identite.boite_id == boite_id).order_by(Identite.par_defaut.desc()).limit(1))
        if identite is None:
            identite = Identite(identite_id=uuid7(), boite_id=boite_id, nom_affiche=comm.from_nom or expediteur, adresse_id=boite.adresse_id, au_nom_de=False, par_defaut=True)
            s.add(identite); s.flush()
        magasin = Magasin(os.environ.get("ATOMBOX_MAGASIN", "./magasin"))
        octets = magasin.lire(str(comm_id))
        envoi = s.scalar(select(Envoi).where(Envoi.comm_id == comm_id))
        if envoi is None:
            envoi = Envoi(envoi_id=uuid7(), comm_id=comm_id, identite_id=identite.identite_id, retour_enveloppe=expediteur)
            s.add(envoi); s.flush()
            for d in dest:
                s.add(EnvoiDestinataire(envoi_id=envoi.envoi_id, adresse_id=adresse_de(s, d).adresse_id, etat="prepare", mis_a_jour_le=datetime.now(timezone.utc)))
            s.flush()
        if not dest: raise RuntimeError("aucun destinataire pour %s" % comm_id)
        resultat = remettre(octets, envoi.retour_enveloppe, dest)          # lève si le relais est injoignable → tentative suivante (D161)
        envoi.remis_le = datetime.now(timezone.utc)
        for ed in s.scalars(select(EnvoiDestinataire).where(EnvoiDestinataire.envoi_id == envoi.envoi_id)):
            a = s.get(Adresse, ed.adresse_id).adresse_complete
            if a in resultat["refuses"]:
                r = resultat["refuses"][a]
                ed.etat = "rejete"                      # 5xx du relais : refusé pour CE destinataire (D099)
                ed.code = ("%s %s" % (r[0], r[1].decode("utf-8", "replace") if isinstance(r[1], bytes) else r[1]))[:200] if isinstance(r, tuple) else str(r)[:200]
            else: ed.etat = "remis"
            ed.mis_a_jour_le = datetime.now(timezone.utc)
        evenements.emettre(s, "message.envoye", {"comm_id": str(comm_id), "boite_id": str(boite_id), "refuses": list(resultat["refuses"])}, module=self.nom)
        log.info("envoi %s de %s remis (%d destinataire(s))", envoi.envoi_id, expediteur, len(dest))
