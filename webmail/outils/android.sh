#!/usr/bin/env bash
# L'APPLICATION ANDROID (RM3252, F144, D172) — une Trusted Web Activity : elle ouvre le webmail en
# plein écran, par le moteur de Chrome. Le site se met à jour sans republier l'application.
#
#   bash webmail/outils/android.sh            # régénère le projet et construit l'APK signé
#
# La CLÉ DE SIGNATURE ne vit pas dans le dépôt : ~/.config/atombox/android-signing.keystore, et son
# mot de passe dans ~/.config/atombox/android.env (chmod 600). La perdre, c'est ne plus jamais
# pouvoir mettre l'application à jour sur les téléphones qui l'ont — elle se sauvegarde comme un
# secret de production, pas comme un fichier de projet.
#
# Le projet Android lui-même (app/, gradle/, gradlew…) est ENGENDRÉ : il n'est pas versionné. Ce
# qui l'est : twa-manifest.json, et .well-known/assetlinks.json qui prouve que ce site et cette
# application vont ensemble.
set -euo pipefail

RACINE="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$HOME/.config/atombox/android.env"
[ -f "$CONF" ] || { echo "✗ $CONF absent : la clé de signature n'existe pas encore."; exit 2; }
# shellcheck disable=SC1090
. "$CONF"
JDK="${ATOMBOX_JDK:-/usr/lib/jvm/java-17-openjdk-amd64}"
cd "$RACINE/android"

echo "→ projet Android (bubblewrap update)"
npx --yes @bubblewrap/cli@latest update --skipVersionUpgrade

# `bubblewrap build` refuse le SDK installé ici (« The provided androidSdk isn't correct ») : on
# appelle donc Gradle, zipalign et apksigner directement — ce que bubblewrap ferait.
echo "→ construction (gradle)"
export JAVA_HOME="$JDK" ANDROID_HOME="${ATOMBOX_ANDROID_SDK:-/opt/android-sdk}"
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew -q assembleRelease

BT="$(ls -d "$ANDROID_HOME"/build-tools/* | sort -V | tail -1)"
echo "→ alignement et signature ($(basename "$BT"))"
"$BT/zipalign" -p -f 4 app/build/outputs/apk/release/app-release-unsigned.apk aligne.apk
"$BT/apksigner" sign --ks "$ATOMBOX_ANDROID_KEYSTORE" --ks-key-alias "${ATOMBOX_ANDROID_ALIAS:-atombox}" \
  --ks-pass "pass:$ATOMBOX_ANDROID_PASSWORD" --key-pass "pass:$ATOMBOX_ANDROID_PASSWORD" --out atombox.apk aligne.apk
rm -f aligne.apk

# LA vérification qui compte : une application signée par une autre clé que celle déclarée par le
# site s'ouvre avec une BARRE D'ADRESSE, sans rien dire. On la fait ici, pas sur le téléphone.
SIGNEE=$("$BT/apksigner" verify --print-certs atombox.apk | grep -i "certificate SHA-256 digest" | head -1 | sed 's/.*: *//' | tr 'A-F' 'a-f')
DECLAREE=$(python3 -c "import json;print(json.load(open('../.well-known/assetlinks.json'))[0]['target']['sha256_cert_fingerprints'][0].replace(':','').lower())")
if [ "$SIGNEE" != "$DECLAREE" ]; then
  echo "✗ l'application est signée par une clé que le site ne déclare PAS :"
  echo "    signée   : $SIGNEE"
  echo "    déclarée : $DECLAREE  (.well-known/assetlinks.json)"
  echo "  → l'application s'ouvrirait avec une barre d'adresse. Mettre assetlinks.json à jour, puis redéployer."
  exit 3
fi
echo "   empreinte de signature = celle déclarée par le site ✓"
echo "✓ à installer sur le téléphone : webmail/android/atombox.apk ($(du -h atombox.apk | cut -f1))"
