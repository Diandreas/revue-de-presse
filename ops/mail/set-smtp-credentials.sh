#!/usr/bin/env bash
# Enregistre l'identifiant et la clé SMTP (Brevo) dans le .env de l'appli, redémarre les
# processus puis envoie un e-mail de test.
#
# Les deux valeurs sont lues sur l'entrée standard (identifiant puis clé, une par ligne) :
# elles n'apparaissent ni dans la ligne de commande ni dans l'historique du shell.
#
# Depuis un poste Windows (PowerShell) :
#   $login = Read-Host "Identifiant SMTP Brevo"
#   $sec = Read-Host "Cle SMTP Brevo" -AsSecureString
#   $key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
#   "$login`n$key" | ssh -i $HOME\.ssh\hostinger_vps root@147.93.87.67 /home/mirlab-presse/htdocs/presse.mirlab.cloud/ops/mail/set-smtp-credentials.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/home/mirlab-presse/htdocs/presse.mirlab.cloud}"
ENV_FILE="$APP_DIR/.env"
PM2_APPS="${PM2_APPS:-presse-backend presse-celery-worker presse-celery-beat}"

IFS= read -r login || true
IFS= read -r key || true
login="$(printf '%s' "$login" | tr -d '\r[:space:]')"
key="$(printf '%s' "$key" | tr -d '\r[:space:]')"
[[ -n "$login" && -n "$key" ]] || { echo "Identifiant ou clé manquant : rien n'a été modifié." >&2; exit 1; }

cp -p "$ENV_FILE" "$ENV_FILE.bak-$(date +%Y%m%d-%H%M%S)"
tmp="$(mktemp "$ENV_FILE.XXXX")"
grep -vE '^(EMAIL_HOST_USER|EMAIL_HOST_PASSWORD)=' "$ENV_FILE" > "$tmp" || true
printf 'EMAIL_HOST_USER=%s\nEMAIL_HOST_PASSWORD=%s\n' "$login" "$key" >> "$tmp"
chmod --reference="$ENV_FILE" "$tmp"
chown --reference="$ENV_FILE" "$tmp"
mv "$tmp" "$ENV_FILE"
echo "Identifiants SMTP enregistrés."

# shellcheck disable=SC2086
pm2 restart $PM2_APPS --update-env > /dev/null
echo "Processus redémarrés."

to="$(grep -E '^EMAIL_REPLY_TO=' "$ENV_FILE" | tail -n 1 | cut -d= -f2-)"
if [[ -n "$to" ]]; then
  cd "$APP_DIR/backend"
  if DJANGO_SETTINGS_MODULE=config.settings.prod venv/bin/python manage.py sendtestemail "$to"; then
    echo "E-mail de test envoyé à $to."
  else
    echo "Échec de l'e-mail de test (voir le message ci-dessus)." >&2
    exit 1
  fi
fi
