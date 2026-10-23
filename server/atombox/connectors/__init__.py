"""LES CONNECTEURS (D020, D021, D187) — des DÉCLARATIONS, pas du code.

Un type de connecteur (`dolibarr.json`) publie ses axes, leurs libellés, et au besoin une RÈGLE
D'EN-TÊTE : un motif qui, trouvé dans le Message-ID, l'In-Reply-To ou les References d'un message,
pose un tag. Le moteur ci-dessous est générique ; rien de propre à une application n'y est écrit.

La règle d'en-tête ne vaut que pour les HÔTES de l'instance déclarée (`application.parametres`) :
un correspondant qui utilise lui aussi Dolibarr écrit `dolibarr-inv45@<son hôte>`, et sa facture 45
n'est pas la nôtre (D187 § 3).

Rien n'appelle l'application : AtomBox lit ce qu'il a reçu, et pose ce que la déclaration dit.
"""
from __future__ import annotations
import functools, json, os, re
from datetime import datetime, timezone
from sqlalchemy import select
from ..journal import journal

log = journal("ingestion")
ICI = os.path.dirname(os.path.abspath(__file__))


@functools.lru_cache(maxsize=None)
def declaration(type_connecteur: str) -> dict | None:
    chemin = os.path.join(ICI, re.sub(r"[^a-z0-9_-]", "", (type_connecteur or "").lower()) + ".json")
    if not os.path.isfile(chemin): return None
    return json.load(open(chemin, encoding="utf-8"))


def header_tags(app, message_id: str | None, in_reply_to: str | None, references: str | list | None) -> list[tuple[str, str]]:
    """[(axe, valeur)] que la règle d'en-tête de cette application pose sur ce message"""
    d = declaration(app.type_connecteur)
    regle = (d or {}).get("regle_entete")
    if not regle: return []
    hotes = {h.lower() for h in ((app.parametres or {}).get(regle.get("parametre_hotes", "hotes")) or [])}
    if not hotes: return []                       # pas d'hôte déclaré : aucune reconnaissance (D187 § 3)
    par_code = {v["code"]: axe for axe, v in d["axes"].items() if axe in [a.lower() for a in (app.axes or [])]}
    refs = " ".join(references) if isinstance(references, list) else (references or "")
    out = []
    for m in re.finditer(regle["motif"], " ".join(x for x in (message_id, in_reply_to, refs) if x)):
        axe = par_code.get(m.group("code"))
        if axe and m.group("hote").lower() in hotes and (axe, m.group("id")) not in out:
            out.append((axe, m.group("id")))
    return out


def apply_header_rule(s, comm_id, boite_id, message_id, in_reply_to, references) -> int:
    """Pose, à l'ingestion, les tags que les règles d'en-tête des applications reconnaissent. Une
    application ne s'applique qu'aux boîtes de SA portée. Idempotent : un tag déjà posé reste."""
    from ..applications import mailbox_ids_sync
    from ..schema.models import Application, Axe, CommTag, Tag
    from ..uuid7 import uuid7
    n = 0
    for app in s.scalars(select(Application).where(Application.actif.is_(True))):
        if not (declaration(app.type_connecteur) or {}).get("regle_entete"): continue
        tags = header_tags(app, message_id, in_reply_to, references)
        if not tags or boite_id not in mailbox_ids_sync(s, app): continue
        for nom_axe, valeur in tags:
            axe = s.scalar(select(Axe).where(Axe.nom == nom_axe, Axe.application_id == app.application_id))
            if axe is None: continue
            tag = s.scalar(select(Tag).where(Tag.axe_id == axe.axe_id, Tag.valeur == valeur))
            if tag is None:
                # le libellé n'est pas encore poussé : on montre la clé, l'application le complétera
                tag = Tag(tag_id=uuid7(), axe_id=axe.axe_id, valeur=valeur, libelle=valeur, actif=True); s.add(tag); s.flush()
            if s.get(CommTag, (comm_id, tag.tag_id)) is None:
                s.add(CommTag(comm_id=comm_id, tag_id=tag.tag_id, source=app.type_connecteur,
                              application_id=app.application_id, pose_le=datetime.now(timezone.utc)))
                n += 1
                log.info("règle d'en-tête %s : %s=%s posé sur %s", app.nom, nom_axe, valeur, comm_id)
    return n
