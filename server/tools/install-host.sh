#!/usr/bin/env bash
# INSTALLE OU MET À JOUR ATOMBOX sur une machine dédiée (RM3516) — en root, depuis une LIVRAISON
# décompressée (server/, webmail/, cdc/dict/), telle que ship.sh la dépose.
#
#   bash /opt/atombox/releases/<ref>/server/tools/install-host.sh [--postgresql] [--vhost atombox.exemple.fr]
#
# Idempotent : relancé sur une nouvelle livraison, il bascule `current`, réinstalle le paquet,
# migre la base et redémarre les services.
#
# Ce qu'il fait — et qui diffère du conteneur dev :
#   - un utilisateur SYSTÈME `atombox`, rien sous /home ni /zfs ;
#   - Python 3.12 par uv, ISOLÉ dans /opt/atombox (la distribution peut n'avoir que 3.10) ;
#   - les unités rendues par render-unit.sh, plus un drop-in qui ouvre 143/993 sans root ;
#   - le dictionnaire du CDC livré avec le code (CDC_DIR) : l'API refuse toute route absente de
#     routes.yml, et sans lui elle ne démarre pas.
# Ce qu'il ne fait PAS : les secrets (/etc/atombox/env et /etc/atombox/boxes restent à remplir),
# le compte de connexion (atombox.bootstrap, avec son mot de passe), le certificat.
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"; R="$(cd "$ICI/../.." && pwd)"
U="${ATOMBOX_USER:-atombox}"; BASE="${ATOMBOX_HOME:-/opt/atombox}"
PY="${ATOMBOX_PYTHON:-3.12}"; UV_VERSION="${UV_VERSION:-0.5.11}"; PORT="${ATOMBOX_PORT:-8010}"
PG=0; VHOST=""
while [ $# -gt 0 ]; do case "$1" in
  --postgresql) PG=1 ;; --vhost) VHOST="$2"; shift ;; *) echo "option inconnue : $1"; exit 2 ;;
esac; shift; done
[ "$(id -u)" = 0 ] || { echo "à lancer en root"; exit 1; }
[ -f "$R/server/pyproject.toml" ] && [ -f "$R/cdc/dict/routes.yml" ] && [ -f "$R/webmail/index.html" ] \
  || { echo "livraison incomplète sous $R (server/, webmail/, cdc/dict/ attendus)"; exit 1; }
log() { echo "-- $*"; }
cd /          # postgres et atombox n'ont pas le droit d'entrer dans le dossier courant de root
run_as() { runuser -u "$U" -- "$@"; }

# 1. l'utilisateur et les dossiers
id "$U" >/dev/null 2>&1 || { useradd --system --home-dir "$BASE" --shell /usr/sbin/nologin "$U"; log "utilisateur $U créé"; }
install -d -m 755 -o root -g root "$BASE" "$BASE/releases" "$BASE/bin"
install -d -m 750 -o "$U" -g "$U" /var/lib/atombox /var/lib/atombox/magasin /var/log/atombox
install -d -m 750 -o root -g "$U" /etc/atombox /etc/atombox/tls

# 2. Python, isolé : uv (binaire vérifié par sa somme), puis l'interpréteur dans /opt/atombox/python
if [ ! -x "$BASE/bin/uv" ] || ! "$BASE/bin/uv" --version | grep -q " $UV_VERSION"; then
  t=$(mktemp -d); a=uv-x86_64-unknown-linux-gnu.tar.gz
  curl -fsSL -o "$t/$a" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$a"
  curl -fsSL -o "$t/$a.sha256" "https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$a.sha256"
  ( cd "$t" && sha256sum -c "$a.sha256" >/dev/null ) || { echo "somme de contrôle de uv INVALIDE"; rm -rf "$t"; exit 1; }
  tar -xzf "$t/$a" -C "$t"; install -m 755 "$t"/uv-x86_64-unknown-linux-gnu/uv "$BASE/bin/uv"; rm -rf "$t"
  log "uv $UV_VERSION installé"
fi
export UV_PYTHON_INSTALL_DIR="$BASE/python" UV_CACHE_DIR="$BASE/.cache/uv"
"$BASE/bin/uv" python install -q "$PY"
[ -x "$BASE/venv/bin/python" ] || { "$BASE/bin/uv" venv -q --python "$PY" "$BASE/venv"; log "venv créé ($PY)"; }

# 3. la livraison devient `current`, et le paquet s'installe depuis elle
# LISIBLE par atombox, modifiable par root seul. Le mode vient de l'archive : le dossier temporaire
# de ship.sh est en 700, et tar le reporte sur la livraison — atombox ne pouvait rien lire.
chown -R root:root "$R"; chmod -R u+rwX,go+rX,go-w "$R"
ln -sfn "$R" "$BASE/current.new" && mv -Tf "$BASE/current.new" "$BASE/current"
"$BASE/bin/uv" pip install -q --python "$BASE/venv/bin/python" -e "$BASE/current/server"
log "code servi : $(basename "$R")"

# 4. PostgreSQL et la base — l'authentification « peer » : l'utilisateur atombox EST le rôle atombox
if [ "$PG" = 1 ] && ! command -v psql >/dev/null; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -q postgresql >/dev/null; log "PostgreSQL installé"
fi
command -v psql >/dev/null || { echo "PostgreSQL absent : relancer avec --postgresql"; exit 1; }
runuser -u postgres -- psql -tAc "select 1 from pg_roles where rolname='$U'" | grep -q 1 \
  || { runuser -u postgres -- createuser "$U"; log "rôle $U créé"; }
runuser -u postgres -- psql -tAc "select 1 from pg_database where datname='atombox'" | grep -q 1 \
  || { runuser -u postgres -- createdb -O "$U" atombox; log "base atombox créée"; }

# 5. l'environnement : posé une fois, jamais écrasé (il porte les secrets)
if [ ! -f /etc/atombox/env ]; then
  sed -e "s#^ATOMBOX_STORE=.*#ATOMBOX_STORE=/var/lib/atombox/magasin#" \
      -e "s#^ATOMBOX_IMAPD_LISTEN=.*#ATOMBOX_IMAPD_LISTEN=0.0.0.0#" \
      -e "s#^ATOMBOX_IMAPD_PORT=.*#ATOMBOX_IMAPD_PORT=993#" \
      "$R/server/tools/atombox.env.example" > /etc/atombox/env
  cat >> /etc/atombox/env <<ENV

# --- posé par install-host.sh ---------------------------------------------------------------------
CDC_DIR=$BASE/current/cdc
ATOMBOX_WEBMAIL=$BASE/current/webmail
ATOMBOX_IMAPD_CERT=/etc/atombox/tls/fullchain.pem
ATOMBOX_IMAPD_KEY=/etc/atombox/tls/privkey.pem
ENV
  chown root:"$U" /etc/atombox/env; chmod 640 /etc/atombox/env; log "/etc/atombox/env posé — À COMPLÉTER (relève, relais)"
fi
[ -f /etc/atombox/boxes ] || install -m 640 -o root -g "$U" /dev/null /etc/atombox/boxes

# 6. le schéma
# seule DATABASE_URL compte pour migrer ; charger tout le fichier dans une ligne de commande
# casserait sur la première valeur à espaces
DSN="$(sed -n 's/^DATABASE_URL=//p' /etc/atombox/env | tail -1)"
( cd "$BASE/current/server" && run_as env DATABASE_URL="${DSN:-postgresql:///atombox}" ATOMBOX_LOGS=/var/log/atombox \
    "$BASE/venv/bin/python" -m alembic upgrade head ) 2>&1 | tail -2 | sed 's/^/   /'
log "base à $(runuser -u "$U" -- psql -d atombox -tAc 'select version_num from alembic_version')"

# 7. les unités : le rendu commun, et 143/993 sans root pour le serveur IMAP
for u in api ingestion tasks imapd; do
  "$R/server/tools/render-unit.sh" "$BASE/current/server" "$U" "$BASE/venv" < "$R/server/tools/atombox-$u.service" \
    | sed -e "s/--port 8010/--port $PORT/" > "/etc/systemd/system/atombox-$u.service"
done
install -d /etc/systemd/system/atombox-imapd.service.d
printf '[Service]\nAmbientCapabilities=CAP_NET_BIND_SERVICE\nCapabilityBoundingSet=CAP_NET_BIND_SERVICE\n' \
  > /etc/systemd/system/atombox-imapd.service.d/ports.conf
systemctl daemon-reload
systemctl enable -q atombox-api atombox-ingestion atombox-tasks atombox-imapd
systemctl restart atombox-api atombox-tasks
grep -qE '^ATOMBOX_IMAP_HOST=.+' /etc/atombox/env && systemctl restart atombox-ingestion \
  || log "relève NON démarrée : ATOMBOX_IMAP_HOST vide dans /etc/atombox/env"
[ -s /etc/atombox/tls/fullchain.pem ] && systemctl restart atombox-imapd \
  || log "serveur IMAP NON démarré : pas de certificat dans /etc/atombox/tls (voir --vhost et certbot)"

# 8. le vhost (HTTP ; certbot le passe en HTTPS) et le crochet qui livre le certificat à l'IMAP
if [ -n "$VHOST" ]; then
  for m in proxy proxy_http headers; do a2query -q -m "$m" 2>/dev/null || a2enmod -q "$m"; done
  sed -e "s/atombox.dev.lxc/$VHOST/g" -e "s/127.0.0.1:8010/127.0.0.1:$PORT/g" "$R/server/tools/atombox.dev.lxc.conf" \
    > "/etc/apache2/sites-available/$VHOST.conf"
  a2ensite -q "$VHOST.conf"; apache2ctl configtest 2>&1 | grep -v "^Syntax OK" || true; systemctl reload apache2
  install -d /etc/letsencrypt/renewal-hooks/deploy
  cat > /etc/letsencrypt/renewal-hooks/deploy/atombox-imapd.sh <<HOOK
#!/bin/sh
# managed-by: atombox install-host.sh — le certificat de $VHOST, lisible par $U, pour le serveur IMAP
[ -n "\$RENEWED_LINEAGE" ] && [ "\$(basename "\$RENEWED_LINEAGE")" = "$VHOST" ] || exit 0
install -m 640 -o root -g $U "\$RENEWED_LINEAGE/fullchain.pem" /etc/atombox/tls/fullchain.pem
install -m 640 -o root -g $U "\$RENEWED_LINEAGE/privkey.pem" /etc/atombox/tls/privkey.pem
systemctl restart atombox-imapd
HOOK
  chmod 755 /etc/letsencrypt/renewal-hooks/deploy/atombox-imapd.sh
  log "vhost $VHOST (HTTP) ; certificat : certbot --apache -d $VHOST (le crochet le livre à l'IMAP)"
fi

# 9. mesuré, pas supposé
sleep 2
for s in api ingestion tasks imapd; do printf '   atombox-%-10s %s\n' "$s" "$(systemctl is-active atombox-$s || true)"; done
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/api/v1/referentiels" || true)
[ "$code" = 401 ] && log "API vivante (401 sans jeton, comme attendu)" || { echo "API : réponse $code — journalctl -u atombox-api -n 30"; exit 1; }
