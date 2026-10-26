#!/bin/bash
# Déployer le SERVEUR AtomBox sur l'environnement servi — code, migrations, services.
#
#   bash server/tools/deploy.sh --verifier     # constater, ne rien changer
#   bash server/tools/deploy.sh                # déployer
#   bash server/tools/deploy.sh --cible <dir>  # déployer un AUTRE worktree que le sien
#
# POURQUOI CE SCRIPT EXISTE, et c'est une histoire à ne pas répéter. Le 30/09, la mise en production
# de deux migrations a été lancée à la main, étape par étape, et n'a RIEN fait — en n'affichant que
# des succès. Trois pièges se sont additionnés, et chacun est silencieux :
#
#   1. `git merge --ff-only origin/dev` SANS FETCH. La référence locale `origin/dev` était périmée
#      (le fetch avait échoué pendant une panne du rebond SSH), donc le merge a répondu « Already up
#      to date » — un message de succès pour un non-événement ;
#   2. `alembic upgrade head` sur du code d'avant. « head » est la dernière migration QUE LE CODE
#      CONTIENT : sur l'ancien code, head valait 0010, la base était à 0010, donc rien à faire,
#      code de sortie 0 ;
#   3. `imapd.sh start` a démarré un serveur sur 127.0.0.1 pendant qu'un autre, lancé à la main la
#      veille, tenait 10.0.3.11 — l'adresse que le client interroge. Le client a donc continué de
#      parler à l'ancien code.
#
# LA RÈGLE QUI EN SORT, et que ce script applique partout : **un déploiement mesure son effet, il
# n'annonce pas son intention.** Chaque étape compare l'avant et l'après, et l'absence de changement
# là où on en attendait un est une ERREUR, pas un succès.
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CIBLE="$(cd "$ICI/../.." && pwd)"          # la racine du dépôt où vit ce script
BRANCHE="${ATOMBOX_BRANCH:-dev}"
SERVICES="atombox-api atombox-ingestion atombox-tasks"
# LE SERVEUR IMAP AUSSI, DÈS QU'IL A UNE UNITÉ. Tant qu'il se lance à la main, il survit aux
# déploiements en gardant le code de son démarrage, et le client continue de lui parler : on croit
# avoir déployé et l'on a déployé à côté (30/09). Avec l'unité, il s'arrête et repart comme les
# autres, et `imapd.sh` redevient ce qu'il devrait être — un outil de mise au point.
[ -f /etc/systemd/system/atombox-imapd.service ] && SERVICES="$SERVICES atombox-imapd"
MODE="deployer"

while [ $# -gt 0 ]; do
  case "$1" in
    --verifier) MODE="verifier" ;;
    --cible) CIBLE="$(cd "$2" && pwd)" || exit 2; shift ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "argument inconnu : $1"; exit 2 ;;
  esac
  shift
done

SRV="$CIBLE/server"
PY="$SRV/.venv/bin/python"
DSN="$(grep -m1 '^DATABASE_URL=' /etc/atombox/env 2>/dev/null | cut -d= -f2- | tr -d "\"'")"

rouge() { echo "✗ $*"; }
vert()  { echo "✓ $*"; }
info()  { echo "  $*"; }

# --- ce que la base dit d'elle-même --------------------------------------------------------------
revision_base() { psql "$DSN" -tAc 'select version_num from alembic_version' 2>/dev/null | tr -d ' '; }

# La dernière migration QUE LE CODE CONTIENT — lue sur les fichiers, pas demandée à alembic : c'est
# le piège nº 2, et le demander à alembic donnerait la même réponse fausse pour la même raison.
revision_code() {
  ls "$SRV/atombox/schema/migrations/versions"/[0-9]*_*.py 2>/dev/null \
    | sed 's#.*/##; s/_.*//' | sort | tail -1
}

etat() {
  local h; h="$(git -C "$CIBLE" rev-parse --short HEAD 2>/dev/null)"
  local o; o="$(git -C "$CIBLE" rev-parse --short "origin/$BRANCHE" 2>/dev/null)"
  local retard; retard="$(git -C "$CIBLE" rev-list --count "HEAD..origin/$BRANCHE" 2>/dev/null || echo '?')"
  info "worktree servi     $CIBLE"
  info "code               HEAD=$h   origin/$BRANCHE=$o   retard=$retard commit(s)"
  info "migrations         base=$(revision_base)   code=$(revision_code)"
  info "services           $(systemctl is-active $SERVICES 2>/dev/null | tr '\n' ' ')"
  # `imapd.sh status` de la CIBLE, pas le nôtre : c'est lui qui tourne là-bas, et c'est son avis
  # sur ses propres serveurs qui compte — y compris ceux lancés hors de lui.
  bash "$SRV/tools/imapd.sh" status 2>/dev/null | sed 's/^/  imap  /'
  # « il tourne » ne veut pas dire « on peut lui parler ». Un serveur sur 127.0.0.1 dans un
  # conteneur est invisible depuis la machine hôte, et rien dans son état ne le laisse voir.
  # Le port vient de l'environnement des services : il est 1993 avec TLS, 1143 sans.
  local port; port="$(grep -m1 '^ATOMBOX_IMAPD_PORT=' /etc/atombox/env 2>/dev/null | cut -d= -f2 | tr -d "\"' ")"
  port="${port:-1143}"
  local tls="clair"; grep -q '^ATOMBOX_IMAPD_CERT=.' /etc/atombox/env 2>/dev/null && tls="TLS"
  info "imap               port $port, $tls"
  local mienne; mienne="$(ip -4 addr show 2>/dev/null | grep -oE 'inet 10\.[0-9.]+|inet 192\.168\.[0-9.]+' | head -1 | awk '{print $2}')"
  if [ -n "$mienne" ] && ! ss -ltn 2>/dev/null | grep -qE "(0\.0\.0\.0|\*|$mienne):$port\b"; then
    info "⚠ le serveur IMAP n'écoute pas $mienne:$port : un client sur la machine hôte ne peut pas"
    info "  s'y connecter. ATOMBOX_IMAPD_LISTEN=$mienne dans /etc/atombox/env — avec un certificat."
  fi
}

UNITES_EN_ATTENTE="$CIBLE/.units-pending"
unites_perimees() {
  local u rendu installe ecarts=""
  rm -rf "$UNITES_EN_ATTENTE"; mkdir -p "$UNITES_EN_ATTENTE"
  for u in $(git -C "$CIBLE" ls-tree --name-only "origin/$BRANCHE" server/tools/ 2>/dev/null \
               | sed -n 's#^server/tools/\(atombox-[a-z]*\)\.service$#\1#p'); do
    [ "$u" = atombox-tunnel ] && continue          # posée à part, avec sa clé (RM3267)
    rendu="$UNITES_EN_ATTENTE/$u.service"
    # LE MÊME RENDU que celui qui pose les unités (render-unit.sh), pris dans la version à servir
    git -C "$CIBLE" show "origin/$BRANCHE:server/tools/$u.service" \
      | bash <(git -C "$CIBLE" show "origin/$BRANCHE:server/tools/render-unit.sh" 2>/dev/null || echo 'sed "s#__SERVER__#$1#g"') "$SRV" > "$rendu"
    installe="/etc/systemd/system/$u.service"
    # on compare ce qui S'EXÉCUTE, pas les commentaires : une phrase reformulée ne vaut pas une réinstallation
    if [ ! -f "$installe" ] || ! diff -q <(grep -v '^#' "$rendu") <(grep -v '^#' "$installe") >/dev/null; then
      ecarts="$ecarts $u"
    fi
  done
  # et celles qui n'existent PLUS dans le code, mais tournent encore
  for u in atombox-taches; do
    [ -f "/etc/systemd/system/$u.service" ] && ecarts="$ecarts $u(obsolète)"
  done
  echo "$ecarts"
}
if [ "$MODE" = "verifier" ]; then
  echo "== état, sans rien changer =="
  etat
  e="$(unites_perimees)"; rm -rf "$UNITES_EN_ATTENTE"
  [ -z "$e" ] && info "unités systemd      alignées sur origin/$BRANCHE" \
              || info "unités systemd      ⚠ à réinstaller :$e (le déploiement refusera d'avancer)"
  exit 0
fi

# --- 0. LES MOYENS D'ABORD ----------------------------------------------------------------------
# VÉRIFIER CE QU'ON SAIT FAIRE AVANT DE COMMENCER. Le premier essai a avancé le code de huit
# commits, PUIS s'est arrêté sur un sudo qui réclamait un mot de passe — laissant le worktree servi
# sur le code neuf et la base sur l'ancien schéma. Un demi-déploiement est pire qu'un refus : les
# services continuaient de tourner sur du code chargé en mémoire, et le moindre redémarrage les
# aurait fait échouer à chaque requête.
#
# Un script qui modifie l'état doit donc s'assurer de pouvoir aller AU BOUT avant de faire le
# premier pas.
echo "-- 0. les moyens"
# ON TESTE LA COMMANDE QU'ON VA LANCER, pas un blanc-seing. `sudo -n true` exige NOPASSWD sur
# TOUT : il répondait donc « mot de passe requis » alors qu'une règle autorisait précisément les
# trois gestes dont on a besoin. Un contrôle plus large que le besoin refuse ce qui est permis.
if ! sudo -n -l /usr/bin/systemctl stop $SERVICES >/dev/null 2>&1; then
  rouge "sudo réclame un mot de passe pour « systemctl stop $SERVICES »."
  info "Rien n'a été touché. Deux façons d'avancer :"
  info ""
  info "  1. lancer ce script dans un VRAI terminal (le mot de passe une fois) :"
  info "       cd $CIBLE && bash server/tools/deploy.sh"
  info ""
  info "  2. ou autoriser ces trois gestes SANS mot de passe — trois commandes exactes, pas un"
  info "     blanc-seing —, ce qui rend le déploiement jouable par l'outillage. La liste de"
  info "     services doit correspondre EXACTEMENT, dans le même ordre, sinon sudo refuse :"
  info "       sudo tee /etc/sudoers.d/atombox <<'EOF'"
  info "       $USER ALL=(root) NOPASSWD: /usr/bin/systemctl stop $SERVICES"
  info "       $USER ALL=(root) NOPASSWD: /usr/bin/systemctl start $SERVICES"
  info "       $USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart $SERVICES"
  info "       EOF"
  info "       sudo chmod 0440 /etc/sudoers.d/atombox"
  info ""
  info "  (La seconde est une modification de la machine : c'est une décision, pas une commodité.)"
  exit 2
fi
vert "sudo disponible sans mot de passe"

# --- 1. LE FETCH, ET IL DOIT RÉUSSIR ------------------------------------------------------------
# C'est la cause nº 1 du déploiement fantôme. Un fetch qui échoue laisse `origin/dev` sur une valeur
# d'hier, et tout le reste de la procédure devient un théâtre. On refuse de continuer.
echo "-- 1. la référence distante"
if ! git -C "$CIBLE" fetch -q origin "$BRANCHE" 2>/tmp/atombox-fetch.$$; then
  rouge "le fetch de origin/$BRANCHE a ÉCHOUÉ — on s'arrête ici."
  sed 's/^/    /' /tmp/atombox-fetch.$$ | tail -4; rm -f /tmp/atombox-fetch.$$
  info "Sans fetch, « git merge --ff-only origin/$BRANCHE » répond « Already up to date » sur une"
  info "référence périmée, et le déploiement ne déploie rien en annonçant un succès."
  info "Transport : l'alias « gitlab: » passe par un rebond SSH. S'il est coupé, poser le repli"
  info "HTTPS+jeton (cf. CLAUDE.md des workspaces) ou passer la réécriture à git en ligne."
  exit 3
fi
rm -f /tmp/atombox-fetch.$$
vert "origin/$BRANCHE = $(git -C "$CIBLE" rev-parse --short "origin/$BRANCHE")"

# --- 1 bis. LES UNITÉS INSTALLÉES SONT-ELLES CELLES DU CODE QU'ON VA SERVIR ? -----------------
# Une unité systemd vit à deux endroits : le dépôt, et /etc/systemd/system. Le déploiement ne réinstalle
# pas les unités (il lui faudrait des droits qu'on ne lui donne pas), donc rien ne les gardait
# alignées. Le jour où un module ou un dossier change de nom (RM3351 : `serveur/` → `server/`,
# `atombox.imap.serveur` → `.server`, `atombox-taches` → `atombox-tasks`), les unités posées
# désignent un chemin qui n'existe plus : arrêter les services réussit, les REDÉMARRER échoue, et
# le déploiement laisse tout à l'arrêt.
#
# On compare donc AVANT de toucher au code, sur la version qu'on s'apprête à servir (lue dans
# origin/$BRANCHE, pas sur le disque), et on refuse d'avancer si elles diffèrent.
echo "-- 1 bis. les unités systemd"
ECARTS="$(unites_perimees)"
if [ -n "$ECARTS" ]; then
  rouge "les unités installées ne correspondent pas au code à servir :$ECARTS"
  info "Rien n'a été touché — ni le code, ni les services. Pour les aligner (une fois) :"
  info ""
  info "  sudo install -m 644 $UNITES_EN_ATTENTE/*.service /etc/systemd/system/"
  case "$ECARTS" in *obsolète*)
    info "  sudo systemctl disable --now atombox-taches && sudo rm /etc/systemd/system/atombox-taches.service" ;; esac
  info "  sudo systemctl daemon-reload && sudo systemctl enable atombox-api atombox-ingestion atombox-tasks atombox-imapd"
  info ""
  info "Les fichiers rendus sont dans $UNITES_EN_ATTENTE : ce sont ceux du code de origin/$BRANCHE,"
  info "avec le chemin de ce worktree. Relance ensuite ce script."
  exit 8
fi
rm -rf "$UNITES_EN_ATTENTE"
vert "les unités installées sont celles du code à servir"

# --- 2. le code ---------------------------------------------------------------------------------
echo "-- 2. le code servi"
AVANT_CODE="$(git -C "$CIBLE" rev-parse HEAD)"
RETARD="$(git -C "$CIBLE" rev-list --count "HEAD..origin/$BRANCHE")"
SALE="$(git -C "$CIBLE" status --porcelain --untracked-files=no)"
if [ -n "$SALE" ]; then
  rouge "le worktree servi a des modifications non commitées — on ne déploie pas ce qu'on ne sait pas nommer :"
  echo "$SALE" | sed 's/^/    /'
  exit 4
fi
if [ "$RETARD" -gt 0 ]; then
  git -C "$CIBLE" merge --ff-only "origin/$BRANCHE" >/dev/null || { rouge "le fast-forward a échoué"; exit 4; }
  APRES_CODE="$(git -C "$CIBLE" rev-parse HEAD)"
  [ "$APRES_CODE" != "$AVANT_CODE" ] || { rouge "HEAD n'a pas bougé alors que $RETARD commit(s) l'attendaient"; exit 4; }
  vert "code avancé de $RETARD commit(s) → $(git -C "$CIBLE" rev-parse --short HEAD)"
  CODE_A_BOUGE=1
else
  info "code déjà à jour (et la référence vient d'un fetch réussi, donc c'est vrai)"
  CODE_A_BOUGE=0
fi

# --- 3. y a-t-il quelque chose à faire ? --------------------------------------------------------
BASE_AVANT="$(revision_base)"
CODE_HEAD="$(revision_code)"
echo "-- 3. les migrations"
info "base à $BASE_AVANT, le code en porte jusqu'à $CODE_HEAD"
# « RIEN À FAIRE » SUPPOSE QUE ÇA TOURNE. Un déploiement interrompu laisse le code et la base à jour
# mais les services ARRÊTÉS ; le relancer répondait « rien à déployer » et les y laissait.
INACTIFS=""
for s in $SERVICES; do systemctl is-active --quiet "$s" || INACTIFS="$INACTIFS $s"; done
if [ "$CODE_A_BOUGE" = 0 ] && [ "$BASE_AVANT" = "$CODE_HEAD" ] && [ -z "$INACTIFS" ]; then
  vert "rien à déployer : le code est à jour, la base à sa dernière migration, les services tournent."
  exit 0
fi
[ -z "$INACTIFS" ] || info "services à l'arrêt :$INACTIFS — on va au bout pour les redémarrer"

# --- 4. arrêter, migrer, VÉRIFIER ---------------------------------------------------------------
# À CHAUD, JAMAIS. Le 19/09, une migration a attendu 11 minutes derrière des connexions
# « idle in transaction » en bloquant les lectures le temps de son attente. Services arrêtés, les
# mêmes migrations prennent moins d'une seconde.
echo "-- 4. arrêt des services"
sudo systemctl stop $SERVICES || { rouge "l'arrêt des services a échoué"; exit 5; }
bash "$SRV/tools/imapd.sh" stop-tous | sed 's/^/    /'
# Les deux noms du module (cf. imapd.sh) : un serveur lancé avant la bascule porte l'ancien.
RESTE="$(pgrep -f '[p]ython.* -m atombox\.imap\.serveu?r' | paste -sd, -)"
[ -z "$RESTE" ] || { rouge "des serveurs IMAP tournent encore (pid $RESTE) — on ne migre pas sous eux"; exit 5; }
vert "services arrêtés, aucun serveur IMAP en vie"

# --- 4 bis. LE VENV SUIT LE DOSSIER --------------------------------------------------------------
# Le venv n'est pas versionné : quand `serveur/` est devenu `server/`, git a déplacé le code et laissé
# le venv derrière lui, dans un dossier qui ne contient plus que lui. On le déplace — services
# arrêtés, puisqu'ils l'exécutaient — et on refait l'installation éditable, qui inscrit le CHEMIN
# du code : sans elle, le venv continuerait d'importer `serveur/atombox`, qui n'existe plus.
if [ ! -x "$PY" ] && [ -x "$CIBLE/serveur/.venv/bin/python" ]; then
  echo "-- 4 bis. le venv suit le dossier server/"
  mv "$CIBLE/serveur/.venv" "$SRV/.venv" || { rouge "déplacement du venv impossible — services ARRÊTÉS"; exit 6; }
  "$PY" -m pip install -q --no-deps -e "$SRV" 2>&1 | tail -3 | sed 's/^/    /'
  rm -rf "$CIBLE/serveur"/{atombox.egg-info,.pytest_cache} 2>/dev/null
  find "$CIBLE/serveur" -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
  find "$CIBLE/serveur" -depth -type d -empty -delete 2>/dev/null
fi
VU="$(cd / && "$PY" -c 'import atombox; print(atombox.__file__)' 2>/dev/null)"
case "$VU" in
  "$SRV"/*) vert "le venv importe le code servi ($SRV)" ;;
  *) rouge "le venv importe « ${VU:-rien} », pas $SRV — services ARRÊTÉS, rien n'est migré."
     info "Réparer : $PY -m pip install -e $SRV"; exit 6 ;;
esac

if [ "$BASE_AVANT" != "$CODE_HEAD" ]; then
  echo "-- 5. migration $BASE_AVANT → $CODE_HEAD"
  ( cd "$SRV" && DATABASE_URL="$DSN" "$PY" -m alembic upgrade head ) 2>&1 | tail -6 | sed 's/^/    /'
  BASE_APRES="$(revision_base)"
  if [ "$BASE_APRES" != "$CODE_HEAD" ]; then
    rouge "la base est à $BASE_APRES, on attendait $CODE_HEAD — les services restent ARRÊTÉS."
    info "Rien n'a été redémarré exprès : un service qui tourne sur un schéma qu'il ne connaît pas"
    info "écrit des erreurs à chaque requête, et l'on perd la trace de la cause."
    exit 6
  fi
  vert "base migrée : $BASE_AVANT → $BASE_APRES"
else
  info "aucune migration en attente"
fi

echo "-- 6. redémarrage"
sudo systemctl start $SERVICES || { rouge "le redémarrage a échoué — les services sont arrêtés"; exit 7; }
# Le serveur IMAP par `imapd.sh` SEULEMENT s'il n'a pas d'unité : sinon systemd vient de le démarrer,
# et en lancer un second à côté recrée l'orphelin que tout ceci corrige.
if [ ! -f /etc/systemd/system/atombox-imapd.service ]; then
  bash "$SRV/tools/imapd.sh" start | sed 's/^/    /'
  info "⚠ le serveur IMAP n'a pas d'unité systemd : il vient d'être lancé par imapd.sh, donc il ne"
  info "  repartira pas tout seul au prochain démarrage de la machine. Pour l'installer :"
  info "     $SRV/tools/render-unit.sh $SRV < $SRV/tools/atombox-imapd.service | sudo tee \\"
  info "       /etc/systemd/system/atombox-imapd.service >/dev/null"
  info "     sudo systemctl daemon-reload && sudo systemctl enable --now atombox-imapd"
fi

echo "-- 7. ce qui tourne VRAIMENT, mesuré"
etat
for s in $SERVICES; do
  systemctl is-active --quiet "$s" || { rouge "$s n'est pas actif après redémarrage"; exit 7; }
done
vert "déployé, et vérifié."
