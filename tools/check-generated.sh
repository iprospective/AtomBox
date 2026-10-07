#!/bin/bash
# Ce qui est ENGENDRÉ est-il à jour ? (RM3187)
#
# Le schéma, les modèles et le contrat d'API sont engendrés du dictionnaire, qui vit dans le dépôt
# de DONNÉES du projet — absent de l'intégration continue. Ce contrôle tourne donc là où le
# dictionnaire existe : sur le poste, avant le push (hook `pre-push`, posé par --installer).
#
# Il n'a de valeur que parce que la génération est REPRODUCTIBLE : plus aucun horodatage dans les
# fichiers engendrés, sinon deux exécutions donneraient deux fichiers et ce contrôle crierait
# toujours, donc ne serait plus lu.
set -uo pipefail
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE"

if [ "${1:-}" = "--install" ]; then
  mkdir -p .git/hooks 2>/dev/null || true
  TARGET="$(git rev-parse --git-path hooks)/pre-push"
  # Le hook vit dans le dépôt PARTAGÉ par tous les worktrees : il ne doit donc pas pointer celui
  # où on l'installe, sinon pousser depuis une branche de ticket vérifierait l'arbre du voisin —
  # le même piège que le venv en editable (RM3165). On résout le worktree d'où l'on pousse.
  cat > "$TARGET" <<'HOOK'
#!/bin/bash
racine="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -x "$racine/tools/check-generated.sh" ]; then exec "$racine/tools/check-generated.sh"; fi
# UN CONTRÔLE QUI DISPARAÎT DOIT SE VOIR. L'ancienne version sortait 0 quand le script manquait :
# renommer le script (ce qui est arrivé — `outils/verifier-engendre.sh` est devenu
# `tools/check-generated.sh`) désarmait donc le hook en silence, et le dépôt partait pousser un
# schéma désynchronisé sans que rien ne bronche.
echo "✗ pre-push : $racine/tools/check-generated.sh est introuvable — le hook est périmé." >&2
echo "  Réinstalle-le : bash tools/check-generated.sh --install" >&2
exit 1
HOOK
  chmod +x "$TARGET"
  echo "✓ hook pre-push posé : $TARGET"
  exit 0
fi

# Le dictionnaire vit dans le dépôt de DONNÉES, atteint en remontant l'arborescence — comme le
# font les générateurs eux-mêmes. Dans un worktree de ticket, il est deux niveaux plus haut :
# chercher seulement à côté aurait rendu ce contrôle muet là où on travaille vraiment.
DICT=""
d="$RACINE"
while [ "$d" != "/" ]; do
  [ -d "$d/.mmi-pm/docs/dict" ] && { DICT="$d/.mmi-pm/docs/dict"; break; }
  d="$(dirname "$d")"
done
if [ -z "$DICT" ]; then
  echo "↷ dictionnaire introuvable au-dessus de $RACINE : contrôle de fraîcheur ignoré, et il le DIT."
  exit 0
fi

avant=$(md5sum serveur/atombox/schema/schema.sql serveur/atombox/schema/models.py \
                serveur/atombox/api/contract.py serveur/atombox/schema/manifest.json 2>/dev/null | md5sum)
python3 tools/gen-schema.py >/dev/null && python3 tools/gen-models.py >/dev/null || {
  echo "✗ la génération a échoué"; exit 1; }
apres=$(md5sum serveur/atombox/schema/schema.sql serveur/atombox/schema/models.py \
                serveur/atombox/api/contract.py serveur/atombox/schema/manifest.json 2>/dev/null | md5sum)

if [ "$avant" != "$apres" ]; then
  echo "✗ le schéma, les modèles ou le contrat ne correspondent PAS au dictionnaire."
  echo "  Le dictionnaire est la source (F114, D154) : régénérer et committer."
  echo "    python3 tools/gen-schema.py && python3 tools/gen-models.py"
  git --no-pager diff --stat -- serveur/atombox/schema serveur/atombox/api/contract.py
  exit 1
fi
echo "✓ schéma, modèles et contrat sont à jour avec le dictionnaire"
