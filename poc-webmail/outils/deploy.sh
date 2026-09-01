#!/usr/bin/env bash
# Déploie le POC sur dev.iprospective.net → https://atombox.dev.iprospective.fr/
#
# Rejouable : régénère l'index du CDC, reconstruit la page autonome, joue les
# tests, puis remplace le contenu servi. Le vhost, lui, n'est créé qu'une fois
# (voir outils/vhost-atombox.conf).
#
#   bash outils/deploy.sh
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
HOTE="${ATOMBOX_HOTE:-root@dev.iprospective.net}"   # nom déjà dans known_hosts
CIBLE="${ATOMBOX_CIBLE:-/home/siteadm/atombox/public/dev}"
URL="https://atombox.dev.iprospective.fr/"

cd "$RACINE"
export SSH_AUTH_SOCK="${SSH_AUTH_SOCK:-/run/user/$(id -u)/ssh-agent.sock}"

echo "→ index du CDC"
python3 outils/gen-cdc-index.py

echo "→ page autonome"
python3 outils/bundle.py

echo "→ tests"
node test/smoke.js  | tail -1
node test/bundle.js | tail -1

echo "→ envoi vers $HOTE:$CIBLE"
printf 'User-agent: *\nDisallow: /\n' > /tmp/atombox-robots.txt
ssh -o BatchMode=yes "$HOTE" "mkdir -p '$CIBLE' && cd '$CIBLE' && rm -rf css js index.html README.md autonome.html robots.txt"
tar czf - index.html README.md css js | ssh -o BatchMode=yes "$HOTE" "tar xzf - -C '$CIBLE'"
scp -q dist/index.html "$HOTE:$CIBLE/autonome.html"
scp -q /tmp/atombox-robots.txt "$HOTE:$CIBLE/robots.txt"
ssh -o BatchMode=yes "$HOTE" "chown -R root:siteadm /home/siteadm/atombox && chmod -R a+rX /home/siteadm/atombox"

echo "→ vérification"
for p in "" css/app.css js/app.js autonome.html; do
  printf '   %-16s ' "/${p}"
  curl -s -o /dev/null -w '%{http_code} %{size_download}o\n' "${URL}${p}"
done
echo "✓ en ligne : $URL"
