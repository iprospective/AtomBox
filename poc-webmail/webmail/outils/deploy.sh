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
export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-/run/user/$(id -u)/ssh-agent.sock}"

echo "→ index du CDC"
python3 "$RACINE/../outils/gen-cdc-index.py"

echo "→ pages autonome et produit"
python3 outils/bundle.py
python3 outils/bundle.py dist/prod.html prod

echo "→ tests"
node test/smoke.js  | tail -1
node test/bundle.js | tail -1
node test/prod.js   | tail -1

# La VERSION servie : commit court + date. Chaque <script src="js/…"> et <link href="css/…">
# reçoit ?v=<version> dans les copies ENVOYÉES (jamais dans les sources : le harnais et le
# bundle lisent des chemins nus) — un navigateur qui a l'ancien index recharge tout le reste.
VERSION="$(git rev-parse --short HEAD)-$(date +%Y%m%d%H%M)"
ENVOI="$(mktemp -d)"; trap 'rm -rf "$ENVOI"' EXIT
cp -r css js README.md "$ENVOI"/
for f in index.html; do
  sed -E "s#(src|href)=\"((js|css)/[^\"?]+)\"#\1=\"\2?v=$VERSION\"#g; s#(<meta name=\"abx-version\" content=\")[^\"]*#\1$VERSION#" "$f" > "$ENVOI/$f"
done
echo "→ version $VERSION : $(grep -c "?v=$VERSION" "$ENVOI/index.html") références estampillées dans index.html"
echo "→ envoi vers $HOTE:$CIBLE"
printf 'User-agent: *\nDisallow: /\n' > /tmp/atombox-robots.txt
ssh -o BatchMode=yes "$HOTE" "mkdir -p '$CIBLE' && cd '$CIBLE' && rm -rf css js index.html index.prod.html README.md autonome.html robots.txt"
tar czf - -C "$ENVOI" index.html README.md css js | ssh -o BatchMode=yes "$HOTE" "tar xzf - -C '$CIBLE'"
scp -q dist/index.html "$HOTE:$CIBLE/autonome.html"
# le MODE PRODUIT (D141, D157) : la même page sans rien du POC — poc/poc y est refusé, et sans API il dit « service indisponible »
scp -q dist/prod.html "$HOTE:$CIBLE/prod.html"
scp -q /tmp/atombox-robots.txt "$HOTE:$CIBLE/robots.txt"
ssh -o BatchMode=yes "$HOTE" "chown -R root:siteadm /home/siteadm/atombox && chmod -R a+rX /home/siteadm/atombox"

echo "→ vérification"
for p in "" css/app.css js/app.js js/core/chargeur.js autonome.html prod.html; do
  printf '   %-16s ' "/${p}"
  curl -s -o /dev/null -w '%{http_code} %{size_download}o\n' "${URL}${p}"
done
echo "✓ en ligne : $URL"
