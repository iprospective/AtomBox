#!/bin/bash
# Rendre l'API d'AtomBox joignable depuis le vhost PUBLIC (RM2937, autorisé par Mathieu le 14/09/2026).
#
# L'API tourne dans le conteneur de dev ; le vhost public est sur une autre machine, qui ne servait
# jusqu'ici que des fichiers. Deux pièces :
#   1. un tunnel SSH INVERSE : le port 8010 du serveur public pointe sur l'API du conteneur. Il
#      n'écoute que sur 127.0.0.1 — seul Apache y accède, jamais internet en direct ;
#   2. un ProxyPass /api/ dans le vhost, avec ProxyPreserveHost (sans lui, le lien de
#      réinitialisation pointerait sur 127.0.0.1) et X-Forwarded-Proto.
#
# CE QUE ÇA CHANGE, ET QU'IL FAUT VOULOIR : le formulaire de connexion devient joignable depuis
# internet, avec de vrais emails derrière. Posé avant d'ouvrir : mots de passe hachés, jetons de
# session à durée limitée, limitation des tentatives (10/quart d'heure sur la connexion, 5 sur la
# réinitialisation). Ce qui manque encore : la limitation ne survit pas au redémarrage du service,
# et il n'y a pas de second facteur (F130, V1).
#
#   bash exposer-api-publique.sh --verifier   # constater, sans rien changer
#   bash exposer-api-publique.sh --proxy      # le ProxyPass côté serveur (ssh root, pas de sudo)
#   bash exposer-api-publique.sh --tunnel     # le tunnel, tout de suite, en tâche de fond
#   bash exposer-api-publique.sh --permanent  # le tunnel en service systemd (demande sudo)
#   bash exposer-api-publique.sh --retirer    # referme la porte des deux côtés
set -uo pipefail

HOTE="${ATOMBOX_HOTE:-root@dev.iprospective.net}"
VHOST="${ATOMBOX_VHOST:-/etc/apache2/sites-enabled/atombox.conf}"
URL="${ATOMBOX_URL:-https://atombox.dev.iprospective.fr}"
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

verifier() {
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
         -d '{"utilisateur":"?","mot_de_passe":"?"}' http://127.0.0.1:8010/api/v1/session || echo 000)
  echo "  API locale (127.0.0.1:8010)        $([ "$code" = 401 ] && echo "✓ (401)" || echo "✗ (HTTP $code)")"
  pgrep -f "^(/usr/bin/)?ssh .*-R 127\.0\.0\.1:8010" >/dev/null && echo "  tunnel                             ✓ ouvert" \
    || echo "  tunnel                             ✗ fermé"
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' \
         -d '{"utilisateur":"?","mot_de_passe":"?"}' "$URL/api/v1/session" || echo 000)
  case "$code" in
    401|429) echo "  API par le vhost public            ✓ (HTTP $code — elle répond et refuse)" ;;
    404)     echo "  API par le vhost public            ✗ (404 — pas de proxy, le vhost sert les fichiers seuls)" ;;
    *)       echo "  API par le vhost public            ✗ (HTTP $code)" ;;
  esac
}

proxy() {
  ssh -o BatchMode=yes "$HOTE" "bash -s" <<'DISTANT'
set -e
VHOST=/etc/apache2/sites-enabled/atombox.conf
test -f "$VHOST.avant-api" || cp "$VHOST" "$VHOST.avant-api"
if grep -q 'ProxyPass */api/' "$VHOST"; then echo "  proxy déjà en place"; else
python3 - "$VHOST" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1]); t = p.read_text()
bloc = """
# L'API vit dans le conteneur de dev, jointe par un tunnel SSH inverse (127.0.0.1:8010).
# ProxyPreserveHost : sans lui, le lien de reinitialisation pointerait sur 127.0.0.1.
ProxyPreserveHost On
ProxyPass        /api/ http://127.0.0.1:8010/api/ retry=0 timeout=30
ProxyPassReverse /api/ http://127.0.0.1:8010/api/
RequestHeader set X-Forwarded-Proto "https"
"""
i = t.rindex("</Virtualhost>")
p.write_text(t[:i] + bloc + t[i:])
print("  vhost complété")
PY
fi
a2enmod headers >/dev/null 2>&1 || true
apache2ctl configtest && systemctl reload apache2 && echo "  apache rechargé"
DISTANT
}

tunnel() {
  pgrep -f "^(/usr/bin/)?ssh .*-R 127\.0\.0\.1:8010" >/dev/null && { echo "  tunnel déjà ouvert"; return 0; }
  ssh -f -N -o BatchMode=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
      -o ServerAliveCountMax=3 -R 127.0.0.1:8010:127.0.0.1:8010 "$HOTE" \
    && echo "  tunnel ouvert" || { echo "  ✗ le tunnel a refusé de s'ouvrir"; return 1; }
}

case "${1:---verifier}" in
  --verifier)  echo "== état =="; verifier ;;
  --proxy)     echo "-- proxy ($HOTE)"; proxy; verifier ;;
  --tunnel)    echo "-- tunnel"; tunnel; verifier ;;
  --permanent) echo "-- tunnel en service systemd (sudo)"
               sudo install -m 0644 "$ICI/atombox-tunnel.service" /etc/systemd/system/atombox-tunnel.service \
                 && sudo systemctl daemon-reload && sudo systemctl enable --now atombox-tunnel && verifier ;;
  --retirer)   echo "-- on referme"
               pkill -f "^(/usr/bin/)?ssh .*-R 127\.0\.0\.1:8010" 2>/dev/null || true
               sudo systemctl disable --now atombox-tunnel 2>/dev/null || true
               ssh -o BatchMode=yes "$HOTE" "test -f '$VHOST.avant-api' && cp '$VHOST.avant-api' '$VHOST' && apache2ctl configtest && systemctl reload apache2 && echo '  vhost restauré'"
               verifier ;;
  *) echo "usage : $0 [--verifier|--proxy|--tunnel|--permanent|--retirer]"; exit 2 ;;
esac
