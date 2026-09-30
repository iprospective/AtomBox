"""LES DONNÉES QUE LE PRODUIT APPORTE AVEC LUI — pas de la configuration, du vocabulaire.

Aujourd'hui : les deux marqueurs livrés d'office (D178). L'interface s'appuie dessus PAR LEUR CODE
(`to_review` pour le gras de la liste, `snooze` pour « me le rappeler le… »), donc ils ne sont pas
optionnels : sans eux, le geste existe et ne fait rien.

POURQUOI UN FICHIER ET PAS UN INSERT DANS LA MIGRATION, ou l'inverse : les deux en ont besoin, et
pour des raisons différentes. Une base MIGRÉE les reçoit de la migration, qui doit rester autonome
et rejouable. Une base CRÉÉE de `schema.sql` — les tests, une instance neuve — ne reçoit aucune
donnée, parce que `schema.sql` est un DDL engendré du dictionnaire et rien d'autre. D'où une seule
table de vérité, ici, que les deux chemins lisent.
"""
from __future__ import annotations
from ..journal import journal

log = journal("schema")

# UUID FIGÉS. Un identifiant engendré à chaque installation rendrait deux instances incomparables :
# le même marqueur n'aurait pas la même clé, et toute donnée transportée d'une à l'autre (un export,
# une base de recette copiée) pointerait dans le vide. Le code est unique, l'uuid l'est aussi.
BUILTIN_MARKERS = [
    {"marker_id": "01a0f000-0000-7000-8000-000000000001", "code": "to_review",
     "libelle": "À revoir", "scope": "personal", "value_type": "presence"},
    {"marker_id": "01a0f000-0000-7000-8000-000000000002", "code": "snooze",
     "libelle": "Mise en sommeil", "scope": "personal", "value_type": "moment"},
]


def seed_builtins(s) -> int:
    """pose ce qui manque, en session SYNCHRONE — idempotent, on peut l'appeler à chaque démarrage"""
    import uuid as _uuid
    from sqlalchemy import select
    from .modeles import Marker
    poses = 0
    for m in BUILTIN_MARKERS:
        if s.scalar(select(Marker).where(Marker.code == m["code"])) is not None:
            continue
        s.add(Marker(marker_id=_uuid.UUID(m["marker_id"]), code=m["code"], libelle=m["libelle"],
                     scope=m["scope"], value_type=m["value_type"], actif=True, integre=True))
        poses += 1
    if poses:
        s.commit()
        log.info("marqueurs intégrés posés : %d (D178)", poses)
    return poses
