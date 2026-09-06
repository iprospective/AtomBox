"""LES DOSSIERS VIRTUELS PERSONNELS (D143) et LES RÉGLAGES DU COMPTE (D106 nature personnel, D144)."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from ..schema.modeles import Compte, Filtre
from ..uuid7 import uuid7
from ..journal import journal

log = journal("api")

CLES = ("epingles", "ordre_axes", "tri_axes", "theme")
AXES_V0 = ("dossier", "from", "sujet")     # sans axe métier en V0 (D146) : le prédicat porte sur ça

async def creer_virtuel(s: AsyncSession, compte: Compte, label: str, criteres: list[dict]) -> dict | None:
    criteres = [{"axe": c["axe"], **({"val": c["val"].strip()} if c.get("val") and c["val"].strip() else {})} for c in criteres or [] if c and c.get("axe")]
    label = (label or "").strip()
    if not label or not criteres: return None
    n = await s.scalar(select(Filtre).where(Filtre.portee_type == "compte", Filtre.portee_id == compte.compte_id).order_by(Filtre.ordre.desc()).limit(1))
    f = Filtre(filtre_id=uuid7(), portee_type="compte", portee_id=compte.compte_id, nom=label, ordre=(n.ordre + 1) if n else 1,
               predicat={"criteres": criteres}, action=None, actif=True, retroactif=False, nb_declenchements=0, cree_par=compte.compte_id)
    s.add(f); await s.commit()
    return {"id": "perso:" + str(f.filtre_id), "label": f.nom, "criteres": criteres}

async def supprimer_virtuel(s: AsyncSession, compte: Compte, id_: str) -> bool:
    import uuid
    try: fid = uuid.UUID(id_.split(":", 1)[1] if id_.startswith("perso:") else id_)
    except ValueError: return False
    f = await s.get(Filtre, fid)
    if not f or f.portee_type != "compte" or f.portee_id != compte.compte_id: return False
    await s.delete(f)
    log.debug("dossier virtuel %s supprimé par %s", f.nom, compte.login)
    prefs = dict(compte.preferences or {})
    if id_ in prefs.get("epingles", []): prefs["epingles"] = [e for e in prefs["epingles"] if e != id_]; compte.preferences = prefs; flag_modified(compte, "preferences")
    await s.commit()
    return True

async def regler(s: AsyncSession, compte: Compte, cle: str, valeur) -> dict | None:
    if cle not in CLES: return None
    prefs = dict(compte.preferences or {}); prefs[cle] = valeur; compte.preferences = prefs; flag_modified(compte, "preferences")
    await s.commit()
    return {"cle": cle, "valeur": valeur, "portee": "compte"}

def parametres(compte: Compte) -> dict:
    return {"portee": "compte", "parametres": {k: v for k, v in (compte.preferences or {}).items() if k in CLES}}
