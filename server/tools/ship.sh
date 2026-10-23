#!/usr/bin/env bash
# LIVRE ATOMBOX sur une machine dédiée (RM3516) — depuis le poste de développement, par SSH.
#
#   bash server/tools/ship.sh <réf git> <hôte ssh> [options d'install-host.sh…]
#   bash server/tools/ship.sh origin/dev mmi --postgresql --vhost atombox.exemple.fr
#
# La machine cible n'a besoin d'AUCUN accès à la forge : le code part d'ici (`git archive` de la
# référence, jamais de l'arbre de travail — ce qui n'est pas commité ne part pas), avec le
# dictionnaire du CDC qui l'accompagne (l'API refuse les routes qu'il ne décrit pas).
# La livraison est nommée par la date et le commit ; install-host.sh bascule `current` sur elle.
set -euo pipefail
REF="${1:?référence git (origin/dev, un tag…)}"; HOTE="${2:?hôte ssh}"; shift 2
ICI="$(cd "$(dirname "$0")" && pwd)"; DEPOT="$(git -C "$ICI" rev-parse --show-toplevel)"
SHA="$(git -C "$DEPOT" rev-parse --short "$REF^{commit}")"
NOM="$(date +%Y%m%d-%H%M)-$SHA"
DICT=""; d="$DEPOT"
while [ "$d" != / ]; do [ -f "$d/.mmi-pm/docs/dict/routes.yml" ] && { DICT="$d/.mmi-pm/docs/dict"; break; }; d="$(dirname "$d")"; done
[ -n "$DICT" ] || { echo "dictionnaire du CDC introuvable (.mmi-pm/docs/dict)"; exit 1; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
git -C "$DEPOT" archive --format=tar "$REF" server webmail | tar -x -C "$T"
mkdir -p "$T/cdc"; cp -r "$DICT" "$T/cdc/dict"
echo "-- livraison $NOM ($REF) → $HOTE:/opt/atombox/releases/$NOM"
tar -C "$T" -cz . | ssh -o BatchMode=yes "$HOTE" "install -d -m 755 /opt/atombox/releases/$NOM && tar -xz -C /opt/atombox/releases/$NOM"
ssh -o BatchMode=yes "$HOTE" "bash /opt/atombox/releases/$NOM/server/tools/install-host.sh $*"
