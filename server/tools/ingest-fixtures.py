#!/usr/bin/env python3
"""LES MESSAGES DE LA DÉMO versés dans une boîte AtomBox (RM3520 — devcamp Dolibarr).

Les .eml viennent de tools/fixtures-eml.js (le corpus du POC et les documents du Dolibarr de démo). Chacun passe par
l'INGESTION normale (`ingest`) : magasin en squelette (RM3631), identité, fil, et surtout les règles des applications
— l'en-tête (« dolibarr-pro<id>@<hôte> » → tag du document, D187) et l'adresse (le tiers, D189). Reçus : boîte de
réception, avec les règles de l'utilisateur ; envoyés : « Envoyés », déposés tels quels.

Tout message de démo porte « X-AtomBox-Demo: abxpoc » ; `--remove` les retrouve par là et les efface, avec tout ce
qui leur appartient (lignes qui pointent vers eux : découvertes dans le schéma, pas listées à la main).
Ces messages n'existent QUE dans AtomBox (pas chez le fournisseur) : la relève ne les touche pas.

    python3 tools/ingest-fixtures.py --dir DIR --mailbox test@iprospective.eu [--dry-run]
    python3 tools/ingest-fixtures.py --remove --mailbox test@iprospective.eu [--dry-run]
"""
from __future__ import annotations

import argparse
import email.utils
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, text

MARQUE = "abxpoc"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir"); ap.add_argument("--mailbox", required=True)
    ap.add_argument("--remove", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from atombox import settings
    from atombox.db import session
    from atombox.schema.models import Adresse, Boite, CommEmail, Dossier
    from atombox.store import Store
    s = session()
    boite = s.scalar(select(Boite).join(Adresse, Adresse.adresse_id == Boite.adresse_id).where(Adresse.adresse_complete == a.mailbox))
    if boite is None:
        sys.exit(f"boîte inconnue : {a.mailbox}")
    marques = [cid for cid, h in s.execute(select(CommEmail.comm_id, CommEmail.headers)).all() if f"X-AtomBox-Demo: {MARQUE}" in (h or "")]

    if a.remove:
        print(("(à blanc) " if a.dry_run else "") + f"{len(marques)} message(s) de démo marqué(s) « {MARQUE} »")
        if a.dry_run or not marques:
            return 0
        fks = s.execute(text("""SELECT tc.table_name, kcu.column_name FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name = 'comm' AND ccu.column_name = 'comm_id'""")).all()
        ids = [str(c) for c in marques]
        # d'abord ce qui pointe vers eux (sauf la table elle-même : comm.thread_id), puis eux
        for table, col in fks:
            if table == "comm":
                continue
            s.execute(text(f'DELETE FROM "{table}" WHERE "{col}" = ANY(CAST(:ids AS uuid[]))'), {"ids": ids})
        s.execute(text('UPDATE comm SET thread_id = comm_id WHERE thread_id = ANY(CAST(:ids AS uuid[])) AND NOT comm_id = ANY(CAST(:ids AS uuid[]))'), {"ids": ids})
        s.execute(text('DELETE FROM comm WHERE comm_id = ANY(CAST(:ids AS uuid[]))'), {"ids": ids})
        s.commit()
        print(f"✓ {len(ids)} message(s) de démo retiré(s) (les fichiers du magasin restent : ramasse-miettes)")
        return 0

    from atombox.ingestion.ingestion import ingest
    from atombox.services.messages import short_folder_id
    ds = list(s.scalars(select(Dossier).where(Dossier.boite_id == boite.boite_id)))
    inbox = next((d for d in ds if (d.alias_imap or "").upper() == "INBOX"), None)
    sent = next((d for d in ds if short_folder_id(d) == "sent"), None)
    if inbox is None or sent is None:
        sys.exit("boîte de réception ou « Envoyés » introuvable dans la boîte")
    man = json.loads((Path(a.dir) / "manifeste.json").read_text(encoding="utf-8"))
    if a.dry_run:
        n_in = sum(1 for m in man["messages"] if m["sens"] == "in")
        print(f"(à blanc) {len(man['messages'])} message(s) : {n_in} reçus → {inbox.alias_imap}, "
              f"{len(man['messages']) - n_in} envoyés → {sent.alias_imap} ; {len(marques)} déjà marqué(s)")
        return 0
    store = Store(settings.read("ATOMBOX_STORE", "./magasin"))
    neufs = deja = 0
    for i, m in enumerate(man["messages"], 1):
        raw = (Path(a.dir) / m["fichier"]).read_bytes()
        quand = datetime.fromisoformat(m["date"].replace("Z", "+00:00"))
        r = ingest(s, store, boite.boite_id, raw, dossier_id=(inbox if m["sens"] == "in" else sent).dossier_id,
                   date_recue=quand, sens=m["sens"], apply_rules=(m["sens"] == "in"))
        neufs += bool(r.get("nouveau")); deja += not r.get("nouveau")
        if i % 500 == 0:
            print(f"  … {i}/{len(man['messages'])}", flush=True)
    print(f"✓ {neufs} message(s) versé(s), {deja} déjà là — boîte {a.mailbox}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
