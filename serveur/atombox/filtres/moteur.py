"""LE MOTEUR (F016 — D074) — il remplace Sieve, et il compte ce que Sieve ne comptait pas.

Une règle : un **prédicat** (des critères, en ET ou en OU), une **action**, un **ordre** explicite.
Les règles s'évaluent dans l'ordre ; `arreter` interrompt la chaîne, comme le `stop` de Sieve. Un
prédicat sans action est un dossier virtuel (D075, D143) : le moteur l'ignore.

Ce que Sieve ne fait pas et qu'on fait (chapitre 14, D075 § 1) : **compter les déclenchements**.
Une règle qui n'a jamais rien attrapé est visible, et c'est ce qui a permis de trouver, dans le
script de production, un `allof` saisi à la place d'un `anyof` — muet depuis des années.

En V0 le prédicat ne porte que sur ce qui existe sans axe métier (D146) : expéditeur, sujet,
destinataire, dossier d'origine, taille, pièces jointes, en-tête de liste.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone
from ..journal import journal

log = journal("filtres")

# --- ce sur quoi une règle peut porter, et comment on l'extrait d'une analyse (F001)
CHAMPS = {
    "from":        lambda a, ctx: a.from_adresse or "",
    "from_nom":    lambda a, ctx: a.from_nom or "",
    "sujet":       lambda a, ctx: a.sujet or "",
    "destinataire": lambda a, ctx: " ".join(adr for role, _, adr, _ in a.participants if role in ("to", "cc")),
    "corps":       lambda a, ctx: a.corps_texte or "",
    "liste":       lambda a, ctx: a.list_id or "",
    "nature":      lambda a, ctx: a.nature or "",
    "dossier":     lambda a, ctx: (ctx or {}).get("dossier") or "",
    "taille":      lambda a, ctx: a.taille,
    "pieces":      lambda a, ctx: len(a.pieces),
}

def _texte(v) -> str: return v if isinstance(v, str) else str(v)

OPERATEURS = {
    "contient":     lambda v, x: _texte(x).lower() in _texte(v).lower(),
    "ne_contient_pas": lambda v, x: _texte(x).lower() not in _texte(v).lower(),
    "est":          lambda v, x: _texte(v).strip().lower() == _texte(x).strip().lower(),
    "commence_par": lambda v, x: _texte(v).lower().startswith(_texte(x).lower()),
    "finit_par":    lambda v, x: _texte(v).lower().endswith(_texte(x).lower()),
    "correspond_a": lambda v, x: bool(re.search(_texte(x), _texte(v), re.I)),   # expression régulière
    "superieur_a":  lambda v, x: _nombre(v) > _nombre(x),
    "inferieur_a":  lambda v, x: _nombre(v) < _nombre(x),
    "existe":       lambda v, x: bool(v),
}

def _nombre(v) -> float:
    try: return float(v)
    except (TypeError, ValueError): return 0.0

# --- ce qu'une règle peut faire. Chaque action rend un patch de rattachement (ou une consigne).
ACTIONS = ("classer", "marquer_lu", "drapeau", "statut", "corbeille", "indesirable", "arreter", "ignorer")

def evaluer(predicat: dict, analyse, ctx: dict | None = None) -> bool:
    """Un prédicat : {mode: et|ou, criteres: [{champ, operateur, valeur}]}. Un critère dont le
    champ est inconnu est FAUX et journalisé — jamais vrai par défaut : une règle qu'on ne
    comprend pas ne doit pas attraper du courrier."""
    criteres = (predicat or {}).get("criteres") or []
    if not criteres: return False
    mode = (predicat or {}).get("mode", "et").lower()
    resultats = []
    for c in criteres:
        champ, op = c.get("champ"), c.get("operateur", "contient")
        if champ not in CHAMPS or op not in OPERATEURS:
            log.warning("critère ignoré (champ %r, opérateur %r inconnus)", champ, op); resultats.append(False); continue
        try: resultats.append(bool(OPERATEURS[op](CHAMPS[champ](analyse, ctx), c.get("valeur"))))
        except Exception as e:
            log.warning("critère %s %s en échec : %s", champ, op, e); resultats.append(False)
    return all(resultats) if mode == "et" else any(resultats)

def filtres_de(session, boite_id, compte_id=None) -> list:
    """Les règles applicables, dans leur ordre (D074) : celles de la boîte, puis du compte.
    Un prédicat SANS action est un dossier virtuel (D075) : il ne filtre rien."""
    from sqlalchemy import select, or_
    from ..schema.modeles import Filtre
    q = (select(Filtre).where(Filtre.actif.is_(True), Filtre.action.isnot(None))
         .order_by(Filtre.ordre))
    portees = [("boite", boite_id)] + ([("compte", compte_id)] if compte_id else [])
    return [f for f in session.scalars(q) if (f.portee_type, f.portee_id) in portees]

def appliquer(session, filtres: list, analyse, ctx: dict | None = None) -> dict:
    """Passe les règles dans l'ordre. Rend ce qu'il faut faire du message :
    {patch: {...}, dossier: <alias|None>, ignorer: bool, regles: [noms]}.
    Compte les déclenchements (D075 § 1) — c'est ce compteur qui rend une règle muette visible."""
    resultat = {"patch": {}, "dossier": None, "ignorer": False, "regles": []}
    maintenant = datetime.now(timezone.utc)
    for f in filtres:
        if f.fenetre_debut and maintenant < f.fenetre_debut: continue
        if f.fenetre_fin and maintenant > f.fenetre_fin: continue
        if not evaluer(f.predicat, analyse, ctx): continue
        f.nb_declenchements = (f.nb_declenchements or 0) + 1
        f.dernier_declenchement = maintenant
        resultat["regles"].append(f.nom)
        action = f.action or {}
        nom = action.get("type")
        if nom == "classer":      resultat["dossier"] = action.get("dossier")
        elif nom == "marquer_lu": resultat["patch"]["lu"] = True
        elif nom == "drapeau":    resultat["patch"]["drapeau"] = True
        elif nom == "statut":     resultat["patch"]["statut"] = action.get("statut", "a_faire")
        elif nom == "corbeille":  resultat["dossier"] = "Trash"
        elif nom == "indesirable": resultat["dossier"] = "Junk"
        elif nom == "ignorer":    resultat["ignorer"] = True
        elif nom == "arreter":    pass
        else:
            # une action inconnue est peut-être celle d'un module (D160, point filtre.action)
            from ..modules.accroches import accroches
            ctx2 = accroches.emettre("filtre.action", action=action, analyse=analyse, resultat=resultat, filtre=f)
            if not ctx2.get("traitee"):
                log.warning("règle « %s » : action inconnue %r — ignorée", f.nom, nom)
        log.info("règle « %s » déclenchée (%d fois au total)", f.nom, f.nb_declenchements)
        if nom == "arreter" or action.get("arreter"): break
    return resultat
