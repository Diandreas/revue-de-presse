#!/usr/bin/env bash
# Sauvegarde de Revue de Presse : base PostgreSQL (pg_dump -Fc), fichiers des clients
# (backend/mediafiles) et .env, réunis dans une archive horodatée, chiffrée avec GPG si
# une phrase de passe est disponible, conservée en rotation 7 jours / 4 semaines /
# 12 mois, puis copiée hors du serveur avec rclone si RCLONE_REMOTE est défini.
#
# Usage : backup.sh [daily|predeploy]      (daily par défaut ; voir ops/backup/restore.md)
#
# Réglages (variables d'environnement, toutes facultatives) :
#   APP_DIR          racine de l'appli (contient .env et backend/)
#   BACKUP_ROOT      dossier local des sauvegardes
#   ENV_FILE         fichier .env à lire (DATABASE_URL) et à sauvegarder
#   MEDIA_DIR        fichiers déposés par les clients
#   PASSPHRASE_FILE  phrase de passe GPG (chiffrement symétrique AES-256) ; absente = archive en clair
#   RCLONE_REMOTE    destination hors serveur, ex. « b2-revue:revue-de-presse-backups »
#   ALLOW_UNENCRYPTED_OFFSITE=1  autorise la copie hors serveur d'une archive non chiffrée (déconseillé)
#   BACKUP_PING_URL  URL de surveillance (healthchecks.io…) appelée en cas de succès, et /fail en cas d'échec
#   KEEP_DAILY / KEEP_WEEKLY / KEEP_MONTHLY / KEEP_PREDEPLOY   rétention locale (7 / 4 / 12 / 5)
set -euo pipefail
umask 077

APP_DIR="${APP_DIR:-/home/mirlab-presse/htdocs/presse.mirlab.cloud}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/revue-de-presse}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
MEDIA_DIR="${MEDIA_DIR:-$APP_DIR/backend/mediafiles}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/root/.config/revue-de-presse/backup.passphrase}"
RCLONE_REMOTE="${RCLONE_REMOTE:-}"
ALLOW_UNENCRYPTED_OFFSITE="${ALLOW_UNENCRYPTED_OFFSITE:-0}"
BACKUP_PING_URL="${BACKUP_PING_URL:-}"
KEEP_DAILY="${KEEP_DAILY:-7}"
KEEP_WEEKLY="${KEEP_WEEKLY:-4}"
KEEP_MONTHLY="${KEEP_MONTHLY:-12}"
KEEP_PREDEPLOY="${KEEP_PREDEPLOY:-5}"

TIER="${1:-daily}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
NAME="revue-de-presse-${STAMP}"
WORK_DIR=""

log() { printf '%s [backup] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERREUR : $*" >&2; exit 1; }

ping_monitor() {
  # $1 : suffixe d'URL (vide = succès, « /fail » = échec). Ne fait jamais échouer le script.
  [[ -n "$BACKUP_PING_URL" ]] || return 0
  curl -fsS -m 10 --retry 3 "${BACKUP_PING_URL}$1" >/dev/null 2>&1 || log "avertissement : ping de surveillance impossible"
}

cleanup() {
  local status=$?
  if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
    rm -rf -- "$WORK_DIR"
  fi
  if [[ $status -ne 0 ]]; then
    ping_monitor "/fail"
  fi
  exit "$status"
}
trap cleanup EXIT

urldecode() {
  local encoded="${1//+/ }"
  printf '%b' "${encoded//%/\\x}"
}

# DATABASE_URL : variable d'environnement, sinon dernière occurrence dans le .env (sans
# « sourcer » le .env, dont les valeurs ne sont pas forcément du shell valide).
read_database_url() {
  if [[ -n "${DATABASE_URL:-}" ]]; then
    printf '%s' "$DATABASE_URL"
    return
  fi
  [[ -r "$ENV_FILE" ]] || die "fichier .env illisible : $ENV_FILE"
  local line value
  line="$(grep -E '^[[:space:]]*(export[[:space:]]+)?DATABASE_URL=' "$ENV_FILE" | tail -n 1 || true)"
  [[ -n "$line" ]] || die "DATABASE_URL absent de $ENV_FILE"
  value="${line#*=}"
  value="${value%$'\r'}"
  value="${value#\"}"; value="${value%\"}"
  value="${value#\'}"; value="${value%\'}"
  printf '%s' "$value"
}

# postgres://user:motdepasse@hote:port/base -> variables PG* : le mot de passe ne passe
# jamais en argument de commande (visible par tous les utilisateurs dans « ps »).
export_pg_env() {
  local url="$1"
  local pattern='^(postgres|postgresql|pgsql|psql)://([^:@/]*)(:([^@/]*))?@([^:/?]+)(:([0-9]+))?/([^?]+)'
  [[ "$url" =~ $pattern ]] || die "DATABASE_URL non reconnue (attendu postgres://utilisateur:motdepasse@hôte:port/base)"
  PGUSER="$(urldecode "${BASH_REMATCH[2]}")"
  PGPASSWORD="$(urldecode "${BASH_REMATCH[4]}")"
  PGHOST="${BASH_REMATCH[5]}"
  PGPORT="${BASH_REMATCH[7]:-5432}"
  PGDATABASE="$(urldecode "${BASH_REMATCH[8]}")"
  export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE
}

# Garde les N archives les plus récentes d'un dossier (noms horodatés => tri alphabétique).
rotate() {
  local dir="$1" keep="$2" file
  [[ -d "$dir" ]] || return 0
  while IFS= read -r file; do
    rm -f -- "$file"
    log "rotation : supprimé $(basename "$file")"
  done < <(find "$dir" -maxdepth 1 -type f -name 'revue-de-presse-*' | sort -r | tail -n +"$((keep + 1))")
}

# Copie sans dupliquer l'espace disque quand c'est possible (même système de fichiers).
promote() {
  local source="$1" dir="$2"
  mkdir -p "$dir"
  ln -f "$source" "$dir/" 2>/dev/null || cp -p "$source" "$dir/"
}

offsite_copy() {
  local archive="$1" tier="$2"
  [[ -n "$RCLONE_REMOTE" ]] || { log "copie hors serveur : RCLONE_REMOTE non défini, ignorée"; return 0; }
  command -v rclone >/dev/null || die "RCLONE_REMOTE est défini mais rclone n'est pas installé"
  if [[ "$archive" != *.gpg && "$ALLOW_UNENCRYPTED_OFFSITE" != "1" ]]; then
    die "archive non chiffrée (elle contient le .env) : copie hors serveur refusée. Créez $PASSPHRASE_FILE."
  fi
  rclone copy --no-traverse "$archive" "$RCLONE_REMOTE/$tier/"
  log "copie hors serveur : $RCLONE_REMOTE/$tier/$(basename "$archive")"
}

# Rétention hors serveur par âge (jamais de « sync » : un dossier local vidé par erreur
# effacerait aussi les copies distantes).
offsite_retention() {
  [[ -n "$RCLONE_REMOTE" ]] || return 0
  rclone delete --min-age "$((KEEP_DAILY + 1))d" "$RCLONE_REMOTE/daily/" || log "avertissement : rétention distante (daily) impossible"
  rclone delete --min-age "$((KEEP_WEEKLY * 7 + 3))d" "$RCLONE_REMOTE/weekly/" || log "avertissement : rétention distante (weekly) impossible"
  rclone delete --min-age "$((KEEP_MONTHLY * 31 + 5))d" "$RCLONE_REMOTE/monthly/" || log "avertissement : rétention distante (monthly) impossible"
  rclone delete --min-age 30d "$RCLONE_REMOTE/predeploy/" || log "avertissement : rétention distante (predeploy) impossible"
}

main() {
  case "$TIER" in
    daily|predeploy) ;;
    *) die "usage : $0 [daily|predeploy]" ;;
  esac
  command -v pg_dump >/dev/null || die "pg_dump introuvable (paquet postgresql-client)"
  command -v pg_restore >/dev/null || die "pg_restore introuvable (paquet postgresql-client)"

  mkdir -p "$BACKUP_ROOT/$TIER"
  # Une seule sauvegarde à la fois (cron + déploiement simultanés).
  if command -v flock >/dev/null; then
    exec 9>"$BACKUP_ROOT/.lock"
    flock -n 9 || die "une autre sauvegarde est en cours"
  fi

  WORK_DIR="$(mktemp -d "$BACKUP_ROOT/.work.XXXXXX")"
  local bundle_dir="$WORK_DIR/$NAME"
  mkdir -p "$bundle_dir"

  local database_url
  database_url="$(read_database_url)"
  export_pg_env "$database_url"
  log "base de données : pg_dump de « $PGDATABASE » sur $PGHOST:$PGPORT"
  pg_dump --format=custom --compress=6 --no-owner --no-privileges --file="$bundle_dir/database.dump"
  # Vérifie que le dump est lisible (catalogue complet) avant de le considérer valide.
  pg_restore --list "$bundle_dir/database.dump" >/dev/null

  if [[ -d "$MEDIA_DIR" ]]; then
    log "fichiers clients : archive de $MEDIA_DIR"
    tar -C "$(dirname "$MEDIA_DIR")" -czf "$bundle_dir/mediafiles.tar.gz" "$(basename "$MEDIA_DIR")"
  else
    log "avertissement : $MEDIA_DIR introuvable, aucun fichier client sauvegardé"
  fi

  if [[ -r "$ENV_FILE" ]]; then
    cp -p "$ENV_FILE" "$bundle_dir/env"
  else
    log "avertissement : $ENV_FILE illisible, .env non sauvegardé"
  fi

  {
    echo "date_utc=$STAMP"
    echo "host=$(hostname)"
    echo "database=$PGDATABASE"
    echo "pg_dump=$(pg_dump --version)"
    if [[ -f "$APP_DIR/backend/REVISION" ]]; then
      echo "revision=$(cat "$APP_DIR/backend/REVISION")"
    fi
  } > "$bundle_dir/MANIFEST"
  (cd "$bundle_dir" && sha256sum -- * > SHA256SUMS)

  local archive="$WORK_DIR/$NAME.tar"
  tar -C "$WORK_DIR" -cf "$archive" "$NAME"
  if [[ -r "$PASSPHRASE_FILE" ]]; then
    command -v gpg >/dev/null || die "gpg introuvable alors que $PASSPHRASE_FILE existe"
    gpg --batch --yes --quiet --pinentry-mode loopback --passphrase-file "$PASSPHRASE_FILE" \
      --symmetric --cipher-algo AES256 --output "$archive.gpg" "$archive"
    rm -f -- "$archive"
    archive="$archive.gpg"
  else
    log "avertissement : $PASSPHRASE_FILE absent, archive NON chiffrée"
  fi

  local stored
  stored="$BACKUP_ROOT/$TIER/$(basename "$archive")"
  mv -- "$archive" "$stored"
  log "archive : $stored ($(du -h "$stored" | cut -f1))"

  offsite_copy "$stored" "$TIER"
  if [[ "$TIER" == "daily" ]]; then
    if [[ "$(date -u +%u)" == "7" ]]; then
      promote "$stored" "$BACKUP_ROOT/weekly"
      offsite_copy "$stored" "weekly"
    fi
    if [[ "$(date -u +%d)" == "01" ]]; then
      promote "$stored" "$BACKUP_ROOT/monthly"
      offsite_copy "$stored" "monthly"
    fi
    rotate "$BACKUP_ROOT/daily" "$KEEP_DAILY"
    rotate "$BACKUP_ROOT/weekly" "$KEEP_WEEKLY"
    rotate "$BACKUP_ROOT/monthly" "$KEEP_MONTHLY"
  else
    rotate "$BACKUP_ROOT/predeploy" "$KEEP_PREDEPLOY"
  fi
  offsite_retention

  ping_monitor ""
  log "sauvegarde terminée"
}

main
