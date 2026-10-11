#!/usr/bin/env bash
# Test de restauration (à lancer chaque mois, cf. ops/backup/restore.md) : déchiffre une
# archive, vérifie les sommes SHA-256, restaure la base dans une base JETABLE et compte
# les lignes des tables clés, puis vérifie l'archive des fichiers clients.
# Ne touche jamais à la base de production.
#
# Usage : verify-backup.sh [archive]   (par défaut : la plus récente de $BACKUP_ROOT/daily)
#
#   RESTORE_TEST_DATABASE_URL  base jetable, créée une fois pour toutes, ex.
#                              postgres://revue:motdepasse@127.0.0.1:5432/revue_restore_test
#                              (son contenu est ÉCRASÉ à chaque test)
#   BACKUP_ROOT, PASSPHRASE_FILE : comme backup.sh
set -euo pipefail
umask 077

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/revue-de-presse}"
PASSPHRASE_FILE="${PASSPHRASE_FILE:-/root/.config/revue-de-presse/backup.passphrase}"
RESTORE_TEST_DATABASE_URL="${RESTORE_TEST_DATABASE_URL:-}"
WORK_DIR=""

log() { printf '%s [verify] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERREUR : $*" >&2; exit 1; }

cleanup() {
  if [[ -n "$WORK_DIR" && -d "$WORK_DIR" ]]; then
    rm -rf -- "$WORK_DIR"
  fi
}
trap cleanup EXIT

urldecode() {
  local encoded="${1//+/ }"
  printf '%b' "${encoded//%/\\x}"
}

export_pg_env() {
  local url="$1"
  local pattern='^(postgres|postgresql|pgsql|psql)://([^:@/]*)(:([^@/]*))?@([^:/?]+)(:([0-9]+))?/([^?]+)'
  [[ "$url" =~ $pattern ]] || die "RESTORE_TEST_DATABASE_URL non reconnue"
  PGUSER="$(urldecode "${BASH_REMATCH[2]}")"
  PGPASSWORD="$(urldecode "${BASH_REMATCH[4]}")"
  PGHOST="${BASH_REMATCH[5]}"
  PGPORT="${BASH_REMATCH[7]:-5432}"
  PGDATABASE="$(urldecode "${BASH_REMATCH[8]}")"
  export PGUSER PGPASSWORD PGHOST PGPORT PGDATABASE
}

latest_archive() {
  find "$BACKUP_ROOT/daily" -maxdepth 1 -type f -name 'revue-de-presse-*' | sort -r | head -n 1
}

main() {
  [[ -n "$RESTORE_TEST_DATABASE_URL" ]] || die "définissez RESTORE_TEST_DATABASE_URL (base jetable)"
  local archive="${1:-}"
  if [[ -z "$archive" ]]; then
    archive="$(latest_archive)"
  fi
  [[ -n "$archive" && -f "$archive" ]] || die "aucune archive trouvée"
  log "archive testée : $archive"

  WORK_DIR="$(mktemp -d)"
  local tarball="$WORK_DIR/backup.tar"
  if [[ "$archive" == *.gpg ]]; then
    [[ -r "$PASSPHRASE_FILE" ]] || die "phrase de passe introuvable : $PASSPHRASE_FILE"
    gpg --batch --quiet --pinentry-mode loopback --passphrase-file "$PASSPHRASE_FILE" \
      --decrypt --output "$tarball" "$archive"
  else
    cp -- "$archive" "$tarball"
  fi
  tar -C "$WORK_DIR" -xf "$tarball"

  local bundle
  bundle="$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d -name 'revue-de-presse-*' | head -n 1)"
  [[ -n "$bundle" ]] || die "contenu d'archive inattendu"
  (cd "$bundle" && sha256sum --check --quiet SHA256SUMS) || die "sommes SHA-256 incorrectes"
  log "sommes SHA-256 : OK"
  sed 's/^/  /' "$bundle/MANIFEST"

  export_pg_env "$RESTORE_TEST_DATABASE_URL"
  log "restauration dans la base jetable « $PGDATABASE » (contenu écrasé)"
  pg_restore --clean --if-exists --no-owner --no-privileges --exit-on-error \
    --dbname="$PGDATABASE" "$bundle/database.dump"

  local table count
  for table in accounts_organization accounts_user billing_subscription press_review_pressreviewjob press_review_sourcedocument django_migrations; do
    count="$(psql --no-psqlrc --tuples-only --no-align --command="SELECT count(*) FROM $table")"
    log "  $table : $count ligne(s)"
  done

  if [[ -f "$bundle/mediafiles.tar.gz" ]]; then
    local files
    files="$(tar -tzf "$bundle/mediafiles.tar.gz" | grep -vc '/$' || true)"
    log "fichiers clients : archive lisible, $files fichier(s)"
  else
    log "avertissement : aucune archive de fichiers clients dans cette sauvegarde"
  fi
  if [[ -f "$bundle/env" ]]; then
    log ".env : présent"
  else
    log "avertissement : .env absent de la sauvegarde"
  fi

  log "test de restauration réussi"
}

main "$@"
