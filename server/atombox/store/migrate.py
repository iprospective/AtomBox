"""LA MIGRATION DE L'EXISTANT EN SQUELETTE (RM3631 — D208, D209).

Avant RM3631, un message est écrit DEUX fois en entier : sous l'UUID de sa comm, et sous l'empreinte de
son brut. Ses pièces, elles, sont déjà dans les blobs. La migration réécrit chaque message en squelette,
message par message :

  1. le brut est relu et son empreinte comparée à celle enregistrée (un message abîmé n'est pas touché) ;
  2. il est réécrit en squelette — la reconstitution est VÉRIFIÉE à l'octet avant de rendre (`write_message`) ;
  3. seulement alors le second exemplaire (sous l'empreinte) est effacé, s'il ne sert à rien d'autre
     (une pièce jointe peut être exactement un message : elle garde alors son fichier).

Sans `--apply`, rien n'est écrit : le gain est MESURÉ (taille compressée du squelette, pièces absentes).

    DATABASE_URL=… ATOMBOX_STORE=… python3 -m atombox.store.migrate            # à blanc : le gain
    DATABASE_URL=… ATOMBOX_STORE=… python3 -m atombox.store.migrate --apply    # pour de vrai
"""
from __future__ import annotations

import argparse
import os

from sqlalchemy import select

from ..journal import journal
from . import skeleton as Sq
from .store import Store, fingerprint

log = journal("store")


def _size(store: Store, ident) -> int:
    try: return os.path.getsize(store.path(ident))
    except (OSError, ValueError): return 0


def migrate(s, store: Store, apply: bool = False, limit: int | None = None) -> dict:
    """rend le bilan : {messages, migres, deja, ignores, avant, apres, bruts_gardes}"""
    from ..ingestion.ingestion import blob_row
    from ..schema.models import Blob, CommEmail, PieceJointe
    report = {"messages": 0, "migres": 0, "deja": 0, "ignores": [], "avant": 0, "apres": 0, "bruts_gardes": 0}
    q = select(CommEmail.comm_id, CommEmail.blob_ref).order_by(CommEmail.comm_id)
    for comm_id, blob_ref in s.execute(q).all():
        if limit is not None and report["messages"] >= limit: break
        report["messages"] += 1
        cid = str(comm_id)
        source = cid if store.exists(cid) else (blob_ref if blob_ref and store.exists(blob_ref) else None)
        if source is None:
            report["ignores"].append((cid, "introuvable au magasin")); continue
        data = store.read(source)
        if Sq.read_container(data) is not None:
            report["deja"] += 1; continue
        if fingerprint(data) != blob_ref:
            report["ignores"].append((cid, "empreinte différente de celle enregistrée")); continue
        double = blob_ref if (store.exists(blob_ref) and not s.scalar(select(PieceJointe.piece_jointe_id).where(PieceJointe.blob_ref == blob_ref).limit(1))) else None
        before = _size(store, cid) + (_size(store, double) if double else 0)
        report["avant"] += before
        if not apply:
            sq, segs = Sq.decompose(data)
            man = {"h": blob_ref, "segments": [dict(g["params"], o=g["o"], b=fingerprint(g["content"])) for g in segs]}
            after = len(store._c.compress(Sq.container(sq, man)))
            after += sum(len(store._c.compress(g["content"])) for g in segs if not store.exists(fingerprint(g["content"])))
            report["apres"] += after
            continue
        w = store.write_message(cid, data, replace=True)       # vérifié à l'octet avant de rendre
        if store.read_message(cid) != data:                   # ceinture et bretelles : rien n'est effacé sans ça
            report["ignores"].append((cid, "relecture infidèle")); continue
        for e, info in w["blobs"]: blob_row(s, e, info)
        b = s.get(Blob, blob_ref)
        if b is not None: b.compression, b.taille_stockee = w["compression"], w["taille_stockee"]
        s.commit()
        added = sum(i["taille_stockee"] for _, i in w["blobs"] if i.get("nouveau"))
        if double: os.unlink(store.path(double))
        report["apres"] += _size(store, cid) + added
        report["migres"] += 1
        if w["brut_garde"]:
            report["bruts_gardes"] += 1
            log.warning("message %s : migré brut gardé — la reconstitution n'était pas fidèle", cid)
    log.info("migration en squelette%s : %d message(s), %d migré(s), %d déjà, %d ignoré(s), %d → %d octets",
             "" if apply else " (à blanc)", report["messages"], report["migres"], report["deja"], len(report["ignores"]),
             report["avant"], report["apres"])
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description="Réécrire les messages existants en squelette (RM3631).")
    p.add_argument("--apply", action="store_true", help="écrire pour de vrai (sans : le gain est mesuré, rien n'est touché)")
    p.add_argument("--limit", type=int, default=None, help="au plus N messages")
    a = p.parse_args(argv)
    from ..db import session as open_session
    from .. import settings
    r = migrate(open_session(), Store(settings.read("ATOMBOX_STORE", "./magasin")), apply=a.apply, limit=a.limit)
    gain = r["avant"] - r["apres"]
    print("%s%d message(s) : %d migré(s), %d déjà en squelette, %d ignoré(s), %d brut(s) gardé(s)"
          % ("" if a.apply else "(à blanc) ", r["messages"], r["migres"], r["deja"], len(r["ignores"]), r["bruts_gardes"]))
    print("magasin : %.1f Mo → %.1f Mo (gain %.1f Mo, %.0f %%)" % (r["avant"] / 1e6, r["apres"] / 1e6, gain / 1e6,
                                                                 100 * gain / r["avant"] if r["avant"] else 0))
    for cid, why in r["ignores"][:20]: print("  ignoré %s : %s" % (cid, why))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
