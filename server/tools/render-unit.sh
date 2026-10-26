#!/usr/bin/env bash
# REND UNE UNITÉ systemd d'AtomBox : le modèle sur l'entrée standard, l'unité sur la sortie.
#
#   render-unit.sh SERVEUR [UTILISATEUR] [VENV] < atombox-api.service
#
# UN SEUL RENDU pour les trois scripts qui posent ou comparent des unités (deploy-apache.sh,
# deploy.sh, install-host.sh) : deux rendus finissent par diverger, et le déployeur compare alors
# une unité installée à un rendu qui n'est pas celui qui l'a produite.
# Sans UTILISATEUR ni VENV, le rendu est celui du conteneur dev (mathieu, SERVEUR/.venv).
set -euo pipefail
SRV="${1:?serveur}"; QUI="${2:-mathieu}"; VENV="${3:-$SRV/.venv}"
sed -e "s#__VENV__#$VENV#g" -e "s#__SERVER__#$SRV#g" -e "s#__USER__#$QUI#g"
