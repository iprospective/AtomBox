#!/usr/bin/env bash
# LE CONTENEUR DEV SUR SON PROPRE COURRIER (RM3528) — à lancer en root, sur dev.
#
#   sudo bash server/tools/dev-mail-local.sh            # montre ce qui sera fait, ne change rien
#   sudo bash server/tools/dev-mail-local.sh --apply    # le fait (chaque fichier touché est sauvegardé)
#
# AVANT : l'AtomBox de dev relève ET envoie chez mail.iprospective.fr — la production, les vraies
# boîtes. APRÈS : tout reste dans le conteneur.
#   1. Postfix : le port de SOUMISSION 587 (STARTTLS + authentification obligatoires) — sans lui,
#      Thunderbird n'a nulle part où envoyer ; le 25 reste pour la livraison et la boucle locale ;
#   2. les boîtes locales mathieu@ et test@iprospective.eu, dans la base « postfix » (celle que
#      lisent Postfix et Dovecot), et leurs dossiers, recréés d'après ceux qu'AtomBox connaît ;
#   3. le piège à courrier (virtual-regexp) laisse arriver @iprospective.eu dans ces boîtes ; tout
#      le reste continue de tomber chez mathieu@iprospective.fr — rien ne sort du conteneur ;
#   4. un compte MASTER dans ce Dovecot (à nous) : AtomBox relève sans mot de passe par boîte ;
#   5. AtomBox : relève sur 127.0.0.1:143, envoi sur 127.0.0.1:25 ; /etc/atombox/boxes (mots de
#      passe de PRODUCTION) est mis de côté, pas effacé ;
#   6. les données AtomBox sont GARDÉES (arbitré) ; seul le lien aux UID de la production est effacé
#      — sinon les UID du Dovecot local, qui désignent d'autres messages, recevraient les états et
#      les déplacements des anciens.
# Les secrets tirés ici vont dans /root/.secrets/dev-mail-local.env (600), jamais à l'écran.
set -euo pipefail
APPLY=0; [ "${1:-}" = --apply ] && APPLY=1
[ "$(id -u)" = 0 ] || { echo "à lancer avec sudo"; exit 1; }
[ "$(hostname)" = dev ] || { echo "ce script ne vise que le conteneur dev (hostname = $(hostname))"; exit 1; }
BOITES="mathieu@iprospective.eu test@iprospective.eu"; DOMAINE=iprospective.eu
MASTER=atombox-master; SECRETS=/root/.secrets/dev-mail-local.env
STAMP=$(date +%Y%m%d-%H%M%S)
faire() { if [ "$APPLY" = 1 ]; then echo "   ✓ $*"; else echo "   (à faire) $*"; fi; }
sauver() { [ -e "$1" ] && [ "$APPLY" = 1 ] && cp -a "$1" "$1.avant-rm3528-$STAMP" || true; }
q() { mysql -N postfix -e "$1"; }
# INSÉRER SANS CONNAÎTRE LE SCHÉMA : les colonnes données, plus toute colonne OBLIGATOIRE sans valeur
# par défaut, remplie d'une valeur neutre selon son type (vide, 0, maintenant). Le schéma de la base
# « postfix » varie d'une version de PostfixAdmin à l'autre — `domain.transport` l'a montré.
inserer() {   # inserer TABLE "col1,col2" "val1,val2"   (valeurs déjà en SQL)
  local t="$1" cols="$2" vals="$3" c ty
  while read -r c ty; do
    case ",$cols," in *",$c,"*) continue ;; esac
    case "$ty" in
      *int*|decimal|float|double|tinyint|bit) cols="$cols,$c"; vals="$vals,0" ;;
      date|datetime|timestamp) cols="$cols,$c"; vals="$vals,now()" ;;
      *) cols="$cols,$c"; vals="$vals,''" ;;
    esac
  done < <(q "select column_name, data_type from information_schema.columns where table_schema='postfix' and table_name='$t' and is_nullable='NO' and column_default is null and extra not like '%auto_increment%'")
  q "insert into $t ($cols) values ($vals)"
}

echo "-- 0. secrets"
if [ ! -f "$SECRETS" ]; then
  faire "tirer le mot de passe du master et des boîtes locales → $SECRETS"
  if [ "$APPLY" = 1 ]; then install -d -m 700 /root/.secrets
    ( umask 077; { echo "MASTER_PASS=$(openssl rand -hex 16)"; echo "BOX_PASS=$(openssl rand -base64 15 | tr -d '/+=')"; } > "$SECRETS" ); fi
fi
[ -f "$SECRETS" ] && . "$SECRETS"

echo "-- 1. Postfix : soumission 587"
if grep -qE '^submission\s+inet' /etc/postfix/master.cf; then echo "   déjà déclarée"; else
  faire "ajouter le service submission à master.cf"
  if [ "$APPLY" = 1 ]; then sauver /etc/postfix/master.cf; cat >> /etc/postfix/master.cf <<'CF'
# RM3528 — la soumission : chiffrement et authentification obligatoires (Dovecot SASL)
submission inet n       -       y       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject
CF
  fi
fi

echo "-- 2. boîtes locales (base postfix)"
q "select domain from domain where domain='$DOMAINE'" | grep -q . && echo "   domaine $DOMAINE : présent" || {
  faire "déclarer le domaine $DOMAINE"
  [ "$APPLY" = 1 ] && inserer domain "domain,description,backupmx,active,created,modified" "'$DOMAINE','RM3528 — boîtes de dev d''AtomBox',0,1,now(),now()"; }
for b in $BOITES; do
  if q "select username from mailbox where username='$b'" | grep -q .; then echo "   $b : présente"; else
    faire "créer la boîte $b"
    if [ "$APPLY" = 1 ]; then
      h=$(printf '%s' "$BOX_PASS" | openssl passwd -6 -stdin)
      inserer mailbox "username,password,name,maildir,quota,local_part,domain,active,created,modified" "'$b','$h','$b','$DOMAINE/${b%@*}/',0,'${b%@*}','$DOMAINE',1,now(),now()"
    fi
  fi
done

echo "-- 3. piège à courrier : @$DOMAINE arrive dans ses boîtes"
if grep -q 'iprospective\\.eu' /etc/postfix/virtual-regexp; then echo "   déjà en place"; else
  faire "ajouter /^(.+@iprospective\\.eu)\$/ \$1 AVANT la règle attrape-tout"
  if [ "$APPLY" = 1 ]; then sauver /etc/postfix/virtual-regexp
    { echo '# RM3528 — les boîtes de dev d'"'"'AtomBox reçoivent ce qui leur est adressé (avant l'"'"'attrape-tout)'
      echo '/^(.+@iprospective\.eu)$/	$1'; cat "/etc/postfix/virtual-regexp"; } > /etc/postfix/virtual-regexp.new
    mv /etc/postfix/virtual-regexp.new /etc/postfix/virtual-regexp; fi
fi

echo "-- 4. Dovecot : compte master"
if [ -f /etc/dovecot/conf.d/90-atombox-master.conf ]; then echo "   déjà en place"; else
  faire "créer /etc/dovecot/master-users et conf.d/90-atombox-master.conf"
  if [ "$APPLY" = 1 ]; then
    ( umask 027; printf '%s:%s\n' "$MASTER" "$(printf '%s' "$MASTER_PASS" | openssl passwd -6 -stdin)" > /etc/dovecot/master-users )
    chown root:dovecot /etc/dovecot/master-users
    cat > /etc/dovecot/conf.d/90-atombox-master.conf <<'CF'
# RM3528 — le compte master d'AtomBox (dev) : « boîte*atombox-master » ouvre une boîte locale
auth_master_user_separator = *
passdb {
  driver = passwd-file
  master = yes
  args = /etc/dovecot/master-users
  # la boîte visée doit exister et être active (userdb)
  pass = yes
}
CF
  fi
fi

echo "-- 5. AtomBox : relève et envoi en local"
SVC="atombox-api atombox-ingestion atombox-tasks atombox-imapd"
faire "arrêter $SVC"; [ "$APPLY" = 1 ] && systemctl stop $SVC
faire "/etc/atombox/env : IMAP 127.0.0.1:143 en clair (boucle locale), master $MASTER ; SMTP 127.0.0.1:25 sans authentification"
if [ "$APPLY" = 1 ]; then sauver /etc/atombox/env
  # les noms d'hier ET d'aujourd'hui sont retirés (settings lit le nouveau d'abord, l'ancien ensuite)
  sed -i -E '/^ATOMBOX_(IMAP_(HOTE|HOST|PORT|TLS|MASTER|MOT_DE_PASSE|PASSWORD)|SMTP_(HOTE|HOST|PORT|TLS|UTILISATEUR|USER|MOT_DE_PASSE|PASSWORD))=/d' /etc/atombox/env
  cat >> /etc/atombox/env <<ENV
# --- RM3528 : le courrier de dev reste dans le conteneur (sauvegarde : env.avant-rm3528-$STAMP) ---
ATOMBOX_IMAP_HOST=127.0.0.1
ATOMBOX_IMAP_PORT=143
ATOMBOX_IMAP_TLS=aucun
ATOMBOX_IMAP_MASTER=$MASTER
ATOMBOX_IMAP_PASSWORD=$MASTER_PASS
ATOMBOX_SMTP_HOST=127.0.0.1
ATOMBOX_SMTP_PORT=25
ATOMBOX_SMTP_TLS=aucun
ATOMBOX_SMTP_USER=
ATOMBOX_SMTP_PASSWORD=
ENV
fi
if [ -f /etc/atombox/boxes ]; then faire "mettre de côté /etc/atombox/boxes (mots de passe de production) → boxes.prod-avant-rm3528"
  [ "$APPLY" = 1 ] && mv /etc/atombox/boxes "/etc/atombox/boxes.prod-avant-rm3528-$STAMP"; fi

echo "-- 6. AtomBox : oublier les UID de la production (les messages restent)"
SQL_IDS="select b.boite_id from boite b join adresse a using(adresse_id) where a.adresse_complete in ($(printf "'%s'," $BOITES | sed 's/,$//'))"
n=$(runuser -u mathieu -- psql -d atombox -tAc "select count(*) from rattachement where uid_imap is not null and boite_id in ($SQL_IDS)")
faire "effacer uid_imap sur $n place(s), et l'état de relève (uid_validity, uid_suivant) de leurs dossiers"
[ "$APPLY" = 1 ] && runuser -u mathieu -- psql -d atombox -q -v ON_ERROR_STOP=1 <<SQL
BEGIN;
UPDATE rattachement SET uid_imap = NULL WHERE boite_id IN ($SQL_IDS);
UPDATE dossier SET uid_validity = NULL, uid_suivant = NULL WHERE boite_id IN ($SQL_IDS);
COMMIT;
SQL

echo "-- 7. recharger, puis recréer les dossiers locaux d'après AtomBox"
if [ "$APPLY" = 1 ]; then
  postfix check && systemctl reload postfix
  doveconf -n >/dev/null && systemctl reload dovecot; sleep 1
  SEP=$(doveconf -h namespace/inbox/separator 2>/dev/null); SEP=${SEP:-.}
  for b in $BOITES; do
    runuser -u mathieu -- psql -d atombox -tAc "select d.alias_imap from dossier d join boite bo using(boite_id) join adresse a on a.adresse_id=bo.adresse_id where a.adresse_complete='$b' and d.alias_imap <> 'INBOX'" \
      | while read -r alias; do [ -n "$alias" ] && doveadm mailbox create -s -u "$b" "${alias//\//$SEP}" 2>/dev/null || true; done
    echo "   $b : $(doveadm mailbox list -u "$b" | paste -sd' ')"
  done
  systemctl start $SVC; sleep 3
  for s in $SVC; do printf '   %-18s %s\n' "$s" "$(systemctl is-active "$s")"; done
  echo "-- contrôle : le master ouvre une boîte locale"
  python3 - "$MASTER_PASS" <<'PY'
import imaplib, sys
c = imaplib.IMAP4("127.0.0.1", 143); c.login("test@iprospective.eu*atombox-master", sys.argv[1]); print("   master → test@ :", c.select("INBOX")[0]); c.logout()
PY
else
  echo "   (rien n'a été changé — relancer avec --apply)"
fi
