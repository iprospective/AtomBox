#!/usr/bin/env bash
# Pose un certificat AUTO-SIGNÉ pour le serveur IMAP d'AtomBox (RM3499) — TLS implicite, port 1993.
#
#   bash server/tools/make-imapd-cert.sh                      # les adresses de cette machine
#   bash server/tools/make-imapd-cert.sh imap.exemple.fr      # + des noms ou des IP en plus
#   bash server/tools/make-imapd-cert.sh --force              # remplacer un certificat existant
#
# Le certificat et la clé vont dans ~/.config/atombox/imapd/ — pas dans le dépôt (une clé privée ne
# se versionne pas), pas dans /etc/atombox (l'utilisateur des services ne peut pas y écrire). C'est
# l'endroit où vit déjà la clé du tunnel (RM3267), lu par les unités qui tournent sous ce compte.
#
# POURQUOI L'EMPREINTE EST AFFICHÉE. Un certificat auto-signé chiffre, mais il ne prouve rien :
# Thunderbird demande d'ajouter une exception, et quiconque se place entre lui et le serveur peut
# présenter le sien. La seule chose qui distingue le vrai d'un faux, c'est son EMPREINTE. Compare-la
# à celle de la boîte de dialogue avant d'accepter — une fois ; ensuite le client s'en souvient, et
# c'est lui qui refusera un certificat qui aurait changé.
set -euo pipefail

DIR="${ATOMBOX_IMAPD_CERT_DIR:-$HOME/.config/atombox/imapd}"
CERT="$DIR/imapd.crt"; KEY="$DIR/imapd.key"
FORCE=0; EXTRA=()
for a in "$@"; do
  case "$a" in
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) EXTRA+=("$a") ;;
  esac
done

command -v openssl >/dev/null || { echo "✗ openssl absent"; exit 1; }
if [ -f "$CERT" ] && [ "$FORCE" = 0 ]; then
  echo "✗ un certificat existe déjà : $CERT"
  echo "  Le remplacer fera refuser la connexion par chaque client qui a accepté l'ancien — il"
  echo "  faudra y ré-accepter l'exception. Si c'est voulu : --force"
  exit 2
fi

# Les noms que le certificat couvre : sans le BON nom dans le SAN, Thunderbird signale une
# discordance EN PLUS du caractère auto-signé, et l'on apprend à cliquer sans lire.
SAN="DNS:localhost,IP:127.0.0.1,DNS:$(hostname)"
for ip in $(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1); do
  SAN="$SAN,IP:$ip"
done
[ -n "${ATOMBOX_VHOST:-}" ] && SAN="$SAN,DNS:$ATOMBOX_VHOST"
for e in "${EXTRA[@]+"${EXTRA[@]}"}"; do
  if [[ "$e" =~ ^[0-9.]+$ ]]; then SAN="$SAN,IP:$e"; else SAN="$SAN,DNS:$e"; fi
done

install -d -m 700 "$DIR"
umask 077
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 \
  -keyout "$KEY.tmp" -out "$CERT.tmp" \
  -subj "/CN=AtomBox IMAP ($(hostname))" \
  -addext "subjectAltName=$SAN" \
  -addext "basicConstraints=critical,CA:FALSE" \
  -addext "keyUsage=critical,digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth" 2>/dev/null

# UN CERTIFICAT DE SERVEUR N'EST PAS UNE AUTORITÉ. Sans `CA:FALSE` explicite, `openssl req -x509`
# applique la section `v3_ca` de sa configuration et pose `CA:TRUE` — un certificat qui se présente
# comme une autorité de certification. OpenSSL et Python l'acceptent en serveur ; Thunderbird (NSS,
# mozilla::pkix) le REFUSE (CA_CERT_USED_AS_END_ENTITY), et sa demande d'exception tournait dans le
# vide sans rien dire. Constaté le 21/10. On le vérifie donc sur le fichier produit, pas sur
# l'intention de la commande.
if ! openssl x509 -in "$CERT.tmp" -noout -text | grep -q 'CA:FALSE'; then
  rm -f "$KEY.tmp" "$CERT.tmp"
  echo "✗ le certificat produit n'a pas CA:FALSE — Thunderbird le refuserait. Rien n'a été remplacé."
  exit 3
fi
mv "$KEY.tmp" "$KEY"; mv "$CERT.tmp" "$CERT"
chmod 600 "$KEY"; chmod 644 "$CERT"

echo "✓ certificat auto-signé posé"
echo "  certificat  $CERT"
echo "  clé         $KEY   (600 : lisible par ce compte seul)"
echo "  couvre      ${SAN//,/ }"
echo "  expire      $(openssl x509 -in "$CERT" -noout -enddate | cut -d= -f2)"
echo "  empreinte   $(openssl x509 -in "$CERT" -noout -fingerprint -sha256 | cut -d= -f2)"
echo
echo "  À poser dans /etc/atombox/env (puis redémarrer atombox-imapd) :"
echo "    ATOMBOX_IMAPD_CERT=$CERT"
echo "    ATOMBOX_IMAPD_KEY=$KEY"
echo "    ATOMBOX_IMAPD_PORT=1993"
echo
echo "  Dans Thunderbird : serveur entrant IMAP, port 1993, sécurité « SSL/TLS »."
echo "  Compare l'empreinte ci-dessus à celle de la demande d'exception AVANT d'accepter."
