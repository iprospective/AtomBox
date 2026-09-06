#!/usr/bin/env bash
# Déploie AtomBox derrière Apache dans le conteneur dev : le vhost atombox.dev.lxc (reverse proxy vers
# l'API uvicorn sur 127.0.0.1:8010, qui sert aussi le webmail), le fichier d'environnement, les trois
# unités systemd (api, ingestion, taches). Idempotent : relancé, il met à jour et recharge.
#
#   sudo bash serveur/outils/deployer-apache.sh            # tout : apache + systemd (api démarrée ; ingestion et taches installées, pas démarrées)
#   sudo bash serveur/outils/deployer-apache.sh --apache   # seulement le vhost
#   sudo bash serveur/outils/deployer-apache.sh --systemd  # seulement les unités
#
# Ce que ce script NE fait PAS : créer le rôle PostgreSQL et la base, migrer le schéma, amorcer un
# compte — ce sont des gestes de données, pas d'infrastructure (voir serveur/README.md).
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"; SERVEUR="$(cd "$ICI/.." && pwd)"
NOM="${ATOMBOX_VHOST:-atombox.dev.lxc}"; PORT="${ATOMBOX_PORT:-8010}"
QUOI="${1:-tout}"
[ "$(id -u)" = 0 ] || { echo "à lancer avec sudo (écriture dans /etc/apache2, /etc/systemd, /etc/atombox)"; exit 1; }

if [ "$QUOI" = tout ] || [ "$QUOI" = --apache ]; then
  echo "→ apache : modules"
  for m in proxy proxy_http headers; do a2query -q -m "$m" 2>/dev/null || a2enmod -q "$m"; done
  echo "→ apache : vhost $NOM → 127.0.0.1:$PORT"
  sed -e "s/atombox.dev.lxc/$NOM/g" -e "s/127.0.0.1:8010/127.0.0.1:$PORT/g" "$ICI/atombox.dev.lxc.conf" > "/etc/apache2/sites-available/$NOM.conf"
  a2ensite -q "$NOM.conf"
  apache2ctl configtest 2>&1 | grep -v "^Syntax OK" || true
  systemctl reload apache2
  echo "   http://$NOM/  (depuis l'hôte : *.lxc est résolu par dnsmasq ; sinon ajouter « $(hostname -I | awk '{print $1}') $NOM » dans /etc/hosts de l'hôte)"
fi

if [ "$QUOI" = tout ] || [ "$QUOI" = --systemd ]; then
  echo "→ environnement : /etc/atombox/env"
  install -d -m 750 -o root -g mathieu /etc/atombox
  [ -f /etc/atombox/env ] || install -m 640 -o root -g mathieu "$ICI/atombox.env.exemple" /etc/atombox/env
  install -d -m 750 -o mathieu -g mathieu /var/lib/atombox/magasin /var/log/atombox
  echo "→ systemd : atombox-api, atombox-ingestion, atombox-taches"
  for u in api ingestion taches; do
    sed -e "s#__SERVEUR__#$SERVEUR#g" -e "s/--port 8010/--port $PORT/" "$ICI/atombox-$u.service" > "/etc/systemd/system/atombox-$u.service"
  done
  systemctl daemon-reload
  systemctl enable -q atombox-api atombox-ingestion atombox-taches
  systemctl restart atombox-api
  sleep 1; systemctl is-active atombox-api >/dev/null && echo "   atombox-api : active (port $PORT)" || { echo "   atombox-api : ÉCHEC — journalctl -u atombox-api -n 30"; exit 1; }
  echo "   ingestion et taches : installées, à démarrer quand /etc/atombox/env est rempli : systemctl start atombox-ingestion atombox-taches"
fi
echo "✓ terminé"
