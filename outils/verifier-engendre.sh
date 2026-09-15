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

if [ "${1:-}" = "--installer" ]; then
  mkdir -p .git/hooks 2>/dev/null || true
  CIBLE="$(git rev-parse --git-path hooks)/pre-push"
  # Le hook vit dans le dépôt PARTAGÉ par tous les worktrees : il ne doit donc pas pointer celui
  # où on l'installe, sinon pousser depuis une branche de ticket vérifierait l'arbre du voisin —
  # le même piège que le venv en editable (RM3165). On résout le worktree d'où l'on pousse.
  cat > "$CIBLE" <<'HOOK'
#!/bin/bash
racine="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -x "$racine/outils/verifier-engendre.sh" ] && exec "$racine/outils/verifier-engendre.sh"
exit 0
HOOK
  chmod +x "$CIBLE"
  echo "✓ hook pre-push posé : $CIBLE"
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

avant=$(md5sum serveur/atombox/schema/schema.sql serveur/atombox/schema/modeles.py \
                serveur/atombox/api/contrat.py serveur/atombox/schema/manifest.json 2>/dev/null | md5sum)
python3 outils/gen-schema.py >/dev/null && python3 outils/gen-modeles.py >/dev/null || {
  echo "✗ la génération a échoué"; exit 1; }
apres=$(md5sum serveur/atombox/schema/schema.sql serveur/atombox/schema/modeles.py \
                serveur/atombox/api/contrat.py serveur/atombox/schema/manifest.json 2>/dev/null | md5sum)

if [ "$avant" != "$apres" ]; then
  echo "✗ le schéma, les modèles ou le contrat ne correspondent PAS au dictionnaire."
  echo "  Le dictionnaire est la source (F114, D154) : régénérer et committer."
  echo "    python3 outils/gen-schema.py && python3 outils/gen-modeles.py"
  git --no-pager diff --stat -- serveur/atombox/schema serveur/atombox/api/contrat.py
  exit 1
fi
echo "✓ schéma, modèles et contrat sont à jour avec le dictionnaire"
