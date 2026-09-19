#!/usr/bin/env bash
# Déploie le POC sur dev.iprospective.net → https://atombox.dev.iprospective.fr/
#
# Rejouable : régénère l'index du CDC (générateur commun, à la racine du dépôt — D156),
# reconstruit la page autonome, joue les tests, puis remplace le contenu servi. Le vhost, lui, n'est créé qu'une fois
# (voir outils/vhost-atombox.conf).
#
#   bash webmail/outils/deploy.sh    (depuis la racine du dépôt, ou n'importe où)
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
HOTE="${ATOMBOX_HOTE:-root@dev.iprospective.net}"   # nom déjà dans known_hosts
CIBLE="${ATOMBOX_CIBLE:-/home/siteadm/atombox/public/dev}"
URL="https://atombox.dev.iprospective.fr/"

cd "$RACINE"
# ---------------------------------------------------------------------------
# GARDE (RM3176) : ne pas mettre en ligne une interface EN AVANCE sur son API.
# Le 15/09, le webmail est parti avec les routes de tags, l'API tournait encore
# sur le code d'avant : l'interface proposait le geste, le serveur répondait 405.
# On compare la date du code serveur au démarrage du service ; si le code est
# plus récent, on le dit — et on s'arrête, sauf --quand-meme.
# Le service tourne sur CE worktree : s'il est en retard sur `dev`, on déploie une interface
# qui parle à un serveur d'avant-hier. Arrivé le 15/09 : RM3197 mergé côté forge, worktree local
# jamais mis à jour, et les branches d'axes restaient vides malgré « c'est corrigé ».
#
# CES DEUX GARDES-LÀ NE SE LÈVENT JAMAIS (RM3253). `--quand-meme` levait aussi celle du retard : le
# 19/09, le site est parti avec le code de trois livraisons plus tôt, sans que rien ne le dise.
# Déployer un worktree en retard, ou un fichier modifié à la main, ce n'est pas « forcer » : c'est
# ne pas savoir ce qu'on met en ligne.
if git -C "$RACINE" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$RACINE" fetch -q origin 2>/dev/null || true
  RETARD=$(git -C "$RACINE" rev-list --count HEAD..origin/dev 2>/dev/null || echo 0)
  if [ "${RETARD:-0}" -gt 0 ]; then
    echo "✗ ce worktree a $RETARD commit(s) de retard sur origin/dev — c'est LUI que le service exécute."
    echo "  → git -C \"$RACINE\" merge --ff-only origin/dev  puis  sudo systemctl restart atombox-api"
    exit 4
  fi
  SALE=$(git -C "$RACINE" status --porcelain --untracked-files=no)
  if [ -n "$SALE" ]; then
    echo "✗ des fichiers SUIVIS sont modifiés dans ce worktree — on déploie ce qui est commité :"
    echo "$SALE" | sed 's/^/    /'
    exit 6
  fi
fi

# Le déploiement régénère l'index du CDC EN PLACE : il le remet comme il l'a trouvé en sortant, sinon
# le fichier diffère du dépôt et le `merge --ff-only` suivant refuse — c'est ainsi que le worktree servi
# est resté trois livraisons en arrière (RM3253).
ENGENDRE="$RACINE/src/poc/cdc-index.js"
ENVOI=""
nettoyer() {
  [ -n "$ENVOI" ] && rm -rf "$ENVOI"
  git -C "$RACINE" checkout -q -- "$ENGENDRE" 2>/dev/null || true
}
trap nettoyer EXIT

SERVEUR_DIR="$(cd "$RACINE/../serveur" 2>/dev/null && pwd || true)"
if [ -n "$SERVEUR_DIR" ] && [ -d "$SERVEUR_DIR/atombox" ] && [ "${1:-}" != "--quand-meme" ]; then
  CODE=$(find "$SERVEUR_DIR/atombox" -name '*.py' -printf '%T@\n' 2>/dev/null | sort -rn | head -1 || true)
  DEMARRE=$(date -d "$(systemctl show atombox-api -p ActiveEnterTimestamp --value 2>/dev/null)" +%s 2>/dev/null || echo 0)
  if [ -n "$CODE" ] && [ "$DEMARRE" != 0 ] && [ "${CODE%.*}" -gt "$DEMARRE" ]; then
    echo "✗ le code serveur est PLUS RÉCENT que l'API qui tourne :"
    echo "    code   : $(date -d @${CODE%.*} '+%F %H:%M')"
    echo "    service: $(date -d @$DEMARRE '+%F %H:%M')"
    echo "  Déployer l'interface maintenant, c'est proposer des gestes que le serveur refusera."
    echo "  → sudo systemctl restart atombox-api atombox-taches atombox-ingestion"
    echo "  (ou $0 --quand-meme, si l'écart est voulu)"
    exit 3
  fi
fi

export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-/run/user/$(id -u)/ssh-agent.sock}"

echo "→ index du CDC"
python3 "$RACINE/../outils/gen-cdc-index.py"

echo "→ feuille de style (scss par module → css/app.css)"
[ -d node_modules ] || npm ci --no-audit --no-fund
npm run -s css

echo "→ pages autonome et produit"
python3 outils/bundle.py
python3 outils/bundle.py dist/prod.html prod

echo "→ tests"
node test/smoke.js  | tail -1
node test/bundle.js | tail -1
node test/prod.js   | tail -1
node test/style.js  | tail -1
node test/pwa.js    | tail -1

# La VERSION servie : commit court + date. Chaque <script src="js/…"> et <link href="css/…">
# reçoit ?v=<version> dans les copies ENVOYÉES (jamais dans les sources : le harnais et le
# bundle lisent des chemins nus) — un navigateur qui a l'ancien index recharge tout le reste.
VERSION="$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M)"
ENVOI="$(mktemp -d)"                     # nettoyé par le trap posé plus haut, avec le fichier engendré
cp -r css src README.md icones manifest.webmanifest hors-ligne.html "$ENVOI"/
# L'APPLICATION INSTALLÉE (RM3251) : sw.js porte la version, pour que CHAQUE livraison change ses
# octets — c'est à ce changement que le téléphone reconnaît un nouveau service worker, qui emporte
# les caches de l'ancien. Un sw.js identique d'une livraison à l'autre ne serait jamais relu.
sed "s/^const VERSION = \"dev\";/const VERSION = \"$VERSION\";/" sw.js > "$ENVOI/sw.js"
grep -q "const VERSION = \"$VERSION\";" "$ENVOI/sw.js" || { echo "✗ sw.js n'a pas reçu la version $VERSION"; exit 5; }
for f in index.html; do
  sed -E "s#(src|href)=\"((src|css)/[^\"?]+)\"#\1=\"\2?v=$VERSION\"#g; s#(<meta name=\"abx-version\" content=\")[^\"]*#\1$VERSION#" "$f" > "$ENVOI/$f"
done
echo "→ version $VERSION : $(grep -c "?v=$VERSION" "$ENVOI/index.html") références estampillées dans index.html"
echo "→ envoi vers $HOTE:$CIBLE"
printf 'User-agent: *\nDisallow: /\n' > /tmp/atombox-robots.txt
ssh -o BatchMode=yes "$HOTE" "mkdir -p '$CIBLE' && cd '$CIBLE' && rm -rf css js src index.html index.prod.html README.md autonome.html robots.txt icones manifest.webmanifest sw.js hors-ligne.html"
tar czf - -C "$ENVOI" index.html README.md css src icones manifest.webmanifest sw.js hors-ligne.html | ssh -o BatchMode=yes "$HOTE" "tar xzf - -C '$CIBLE'"
scp -q dist/index.html "$HOTE:$CIBLE/autonome.html"
# le MODE PRODUIT (D141, D157) : la même page sans rien du POC — poc/poc y est refusé, et sans API il dit « service indisponible »
scp -q dist/prod.html "$HOTE:$CIBLE/prod.html"
scp -q /tmp/atombox-robots.txt "$HOTE:$CIBLE/robots.txt"
ssh -o BatchMode=yes "$HOTE" "chown -R root:siteadm /home/siteadm/atombox && chmod -R a+rX /home/siteadm/atombox"

echo "→ vérification"
for p in "" css/app.css src/noyau/amorcage.js src/noyau/chargeur.js autonome.html prod.html manifest.webmanifest sw.js hors-ligne.html icones/atombox-192.png; do
  printf '   %-16s ' "/${p}"
  curl -s -o /dev/null -w '%{http_code} %{size_download}o\n' "${URL}${p}"
done
echo "✓ en ligne : $URL"
