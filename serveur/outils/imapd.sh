#!/bin/bash
# Conduire le serveur IMAP d'AtomBox (D180, RM3322) — démarrer, arrêter, voir.
#
#   bash outils/imapd.sh start     # en tâche de fond, journal dans un fichier
#   bash outils/imapd.sh fg        # au premier plan, journal à l'écran (Ctrl-C pour sortir)
#   bash outils/imapd.sh stop
#   bash outils/imapd.sh restart
#   bash outils/imapd.sh status
#   bash outils/imapd.sh logs      # suit le journal
#
# POURQUOI CE SCRIPT EXISTE. Lancer le serveur « à la main » a laissé traîner une instance qui
# tournait encore du code d'avant un correctif : on la croyait morte, elle répondait toujours, et
# le défaut corrigé semblait persister. Trois garde-fous en découlent :
#
#   1. UN SEUL SERVEUR À LA FOIS. `start` refuse si le port écoute déjà, et dit QUI l'occupe ;
#   2. ON NE TUE QUE LE SIEN. Le PID est relu dans /proc avant d'envoyer quoi que ce soit : un PID
#      se réutilise, et tuer le mauvais processus est pire que de laisser vivre le bon ;
#   3. `status` DIT LA VÉRITÉ, y compris quand elle est désagréable — port occupé par un inconnu,
#      fichier de PID périmé, code plus récent que le processus qui tourne.
#
# Les réglages viennent de /etc/atombox/env, et se surchargent par l'environnement :
#   ATOMBOX_IMAPD_LISTEN (défaut 127.0.0.1 — EN CONTENEUR, c'est la boucle locale DU CONTENEUR :
#                         un client sur la machine hôte ne voit rien, il faut l'adresse du conteneur)
#   ATOMBOX_IMAPD_PORT   (défaut 1143 — pas 143 : un Dovecot tourne peut-être déjà)
set -uo pipefail

ICI="$(cd "$(dirname "$0")" && pwd)"
SERVEUR="$(cd "$ICI/.." && pwd)"
ENV_FICHIER="${ATOMBOX_ENV:-/etc/atombox/env}"
ETAT="${XDG_RUNTIME_DIR:-/tmp}/atombox-imapd"
PIDF="$ETAT/imapd.pid"
LOGF="$ETAT/imapd.log"
MODULE="atombox.imap.serveur"

mkdir -p "$ETAT"

# Les réglages du service, sans écraser ce que l'appelant a déjà posé.
if [ -f "$ENV_FICHIER" ]; then
  avant_listen="${ATOMBOX_IMAPD_LISTEN:-}"; avant_port="${ATOMBOX_IMAPD_PORT:-}"
  set -a; . "$ENV_FICHIER"; set +a
  [ -n "$avant_listen" ] && ATOMBOX_IMAPD_LISTEN="$avant_listen"
  [ -n "$avant_port" ] && ATOMBOX_IMAPD_PORT="$avant_port"
fi
HOTE="${ATOMBOX_IMAPD_LISTEN:-${ATOMBOX_IMAPD_ECOUTE:-127.0.0.1}}"   # ECOUTE : nom d'hier (D181)
PORT="${ATOMBOX_IMAPD_PORT:-1143}"
PYTHON="$SERVEUR/.venv/bin/python"

# --- est-ce BIEN notre serveur ? -----------------------------------------------------------------
# Un PID se réutilise. Avant de signaler quoi que ce soit, on relit la ligne de commande du
# processus : si elle ne porte pas notre module, ce n'est pas lui, et on n'y touche pas.
est_le_notre() {
  local pid="$1"
  [ -n "$pid" ] && [ -d "/proc/$pid" ] || return 1
  # Le groupe porte la redirection d'erreur : le processus peut mourir ENTRE le test ci-dessus et
  # cette lecture, et c'est le shell — pas `tr` — qui se plaint alors du fichier disparu.
  { tr '\0' ' ' < "/proc/$pid/cmdline"; } 2>/dev/null | grep -q "$MODULE"
}

pid_enregistre() {
  [ -f "$PIDF" ] || return 1
  local pid; pid="$(cat "$PIDF" 2>/dev/null)"
  est_le_notre "$pid" || return 1
  echo "$pid"
}

qui_ecoute() { ss -ltnp 2>/dev/null | awk -v a="$HOTE:$PORT" '$4 == a {print; exit}'; }

# --- les actions ---------------------------------------------------------------------------------
statut() {
  local pid; pid="$(pid_enregistre || true)"
  if [ -n "$pid" ]; then
    # `ps -o etime` calcule depuis le démarrage de la machine : sur un conteneur dont l'horloge a
    # été avancée, il rend des milliers de jours. On affiche l'heure de départ, qui ne se calcule pas.
    echo "✓ serveur IMAP vivant — pid $pid, lancé $(ps -o lstart= -p "$pid" 2>/dev/null | sed 's/^ *//')"
    echo "  écoute demandée : $HOTE:$PORT"
    # Le code a-t-il bougé depuis le démarrage ? C'est LA question qui a coûté du temps.
    # On compare la date des sources à celle du répertoire /proc du processus, qui est l'instant
    # exact de son démarrage. C'est LA question qui a coûté du temps : « pourquoi le correctif
    # n'a-t-il rien changé ? » — parce que le serveur tournait encore l'ancien code.
    local recent
    recent="$(find "$SERVEUR/atombox" -name '*.py' -newer "/proc/$pid" -print -quit 2>/dev/null)"
    [ -n "$recent" ] && echo "  ⚠ le code a changé depuis le lancement ($(basename "$recent")…) — « restart » pour le prendre"
  elif [ -f "$PIDF" ]; then
    echo "· fichier de pid périmé ($PIDF) — le processus n'existe plus, je le retire"; rm -f "$PIDF"
  else
    echo "· aucun serveur lancé par ce script"
  fi
  local occupant; occupant="$(qui_ecoute)"
  if [ -n "$occupant" ]; then
    [ -n "$pid" ] || echo "  ⚠ mais $HOTE:$PORT est OCCUPÉ par quelqu'un d'autre :"
    echo "  $occupant"
  else
    echo "  $HOTE:$PORT libre"
  fi
  echo "  journal : $LOGF"
}

demarrer() {
  local pid; pid="$(pid_enregistre || true)"
  if [ -n "$pid" ]; then echo "· déjà vivant (pid $pid) — rien à faire"; return 0; fi
  if [ -n "$(qui_ecoute)" ]; then
    echo "✗ $HOTE:$PORT est déjà occupé, et ce n'est pas nous :"
    echo "  $(qui_ecoute)"
    echo "  → « stop » n'y touchera pas : on ne tue que ses propres processus."
    return 1
  fi
  [ -x "$PYTHON" ] || { echo "✗ pas d'environnement Python : $PYTHON"; return 1; }
  # `</dev/null` n'est PAS un détail : sans lui, le processus de fond garde l'entrée standard du
  # terminal, le tuyau ne se ferme jamais, et le shell appelant paraît FIGÉ alors que le serveur
  # tourne très bien. C'est arrivé au premier essai de ce script.
  #
  # Et c'est `nohup`, pas `setsid` : nohup REMPLACE le processus, donc `$!` est bien le pid du
  # serveur. setsid peut se dédoubler, et l'on enregistrerait alors le pid de l'enveloppe — un
  # fichier de pid qui désigne un processus mort, c'est un serveur qu'on ne sait plus arrêter.
  # PAS DE SOUS-SHELL. Dans `( cmd & echo $! )`, le `$!` ne remonte pas comme on l'attend et le
  # fichier de pid restait VIDE — donc un serveur lancé qu'on ne savait plus arrêter, c'est-à-dire
  # exactement l'orphelin que ce script devait empêcher. On lance depuis le shell courant, et
  # `disown` retire le travail de sa table pour qu'il ne le retienne pas en sortant.
  cd "$SERVEUR" || return 1
  ATOMBOX_IMAPD_LISTEN="$HOTE" ATOMBOX_IMAPD_PORT="$PORT" \
    nohup "$PYTHON" -m "$MODULE" </dev/null >>"$LOGF" 2>&1 &
  echo $! > "$PIDF"
  disown 2>/dev/null || true
  sleep 1
  if pid_enregistre >/dev/null; then
    echo "✓ démarré (pid $(cat "$PIDF")) sur $HOTE:$PORT"
  else
    echo "✗ n'a pas tenu une seconde. Fin du journal :"; tail -n 12 "$LOGF"; rm -f "$PIDF"; return 1
  fi
}

arreter() {
  local pid; pid="$(pid_enregistre || true)"
  if [ -z "$pid" ]; then
    [ -f "$PIDF" ] && rm -f "$PIDF"
    echo "· rien à arrêter"
    [ -n "$(qui_ecoute)" ] && { echo "  ⚠ $HOTE:$PORT reste occupé par un processus qui n'est pas le nôtre :"; echo "  $(qui_ecoute)"; }
    return 0
  fi
  kill "$pid" 2>/dev/null
  for _ in $(seq 20); do est_le_notre "$pid" || break; sleep 0.25; done
  if est_le_notre "$pid"; then
    echo "· il résiste, on insiste"; kill -9 "$pid" 2>/dev/null; sleep 0.5
  fi
  rm -f "$PIDF"
  est_le_notre "$pid" && { echo "✗ toujours vivant (pid $pid)"; return 1; }
  echo "✓ arrêté (pid $pid)"
}

case "${1:-status}" in
  start)   demarrer ;;
  stop)    arreter ;;
  restart) arreter; demarrer ;;
  status)  statut ;;
  logs)    echo "— $LOGF (Ctrl-C pour sortir) —"; tail -n 40 -f "$LOGF" ;;
  fg)      # au premier plan : on ne pose PAS de fichier de pid, il meurt avec le terminal
           [ -n "$(qui_ecoute)" ] && { echo "✗ $HOTE:$PORT déjà occupé :"; echo "  $(qui_ecoute)"; exit 1; }
           echo "— IMAP sur $HOTE:$PORT, Ctrl-C pour sortir —"
           cd "$SERVEUR" && exec env ATOMBOX_IMAPD_LISTEN="$HOTE" ATOMBOX_IMAPD_PORT="$PORT" "$PYTHON" -m "$MODULE" ;;
  *)       echo "usage : $0 [start|stop|restart|status|logs|fg]"; exit 2 ;;
esac
