#!/usr/bin/env bash
# Déploiement de Revue de Presse sur le serveur, à partir d'une référence git (branche,
# tag ou commit). À lancer SUR le serveur, en root (PM2 tourne sous root), depuis n'importe
# quel dossier. Aucun secret ici : tout vient du .env de l'appli (cf. ops/deploy/README.md).
#
# Usage : deploy.sh <ref-git>          ex. deploy.sh main   |   deploy.sh v1.4.0   |   deploy.sh 3f2a9c1
#
# Étapes : sauvegarde « predeploy » -> export de la référence -> build du frontend ->
# copie du backend (rsync, jamais .env / venv / fichiers clients) -> dépendances ->
# migrate + collectstatic -> bascule du frontend -> redémarrage PM2 -> contrôle de santé.
# En cas d'échec, le script affiche la marche à suivre pour revenir en arrière.
#
# Réglages (variables d'environnement, facultatives) :
#   APP_DIR          racine de l'appli en production (contient .env, backend/, frontend/dist)
#   REPO_DIR         clone git du dépôt sur le serveur (mis à jour par « git fetch »)
#   GIT_REMOTE       remote à interroger (origin)
#   HEALTH_URL       URL publique du contrôle de santé (127.0.0.1 est refusé par ALLOWED_HOSTS)
#   PM2_APPS         processus PM2 à redémarrer
#   SKIP_BACKUP=1    saute la sauvegarde predeploy (déconseillé)
#   FRONTEND_DIST_TARBALL  archive .tar.gz d'un dist/ déjà construit (serveur sans Node.js)
set -euo pipefail
umask 022

APP_DIR="${APP_DIR:-/home/mirlab-presse/htdocs/presse.mirlab.cloud}"
REPO_DIR="${REPO_DIR:-/home/mirlab-presse/revue-de-presse.git-src}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
HEALTH_URL="${HEALTH_URL:-https://presse.mirlab.cloud/api/health/}"
PM2_APPS="${PM2_APPS:-presse-backend presse-celery-worker presse-celery-beat}"
SKIP_BACKUP="${SKIP_BACKUP:-0}"
FRONTEND_DIST_TARBALL="${FRONTEND_DIST_TARBALL:-}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"

REF="${1:-}"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
RELEASES_DIR="$APP_DIR/.releases"
VENV_PY="$BACKEND_DIR/venv/bin/python"
BUILD_DIR=""
PREVIOUS_REVISION=""
SNAPSHOT=""
STAGE="préparation"
PRODUCTION_TOUCHED=0

log() { printf '%s [deploy] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERREUR : $*" >&2; exit 1; }

rollback_hint() {
  if [[ "$PRODUCTION_TOUCHED" != "1" ]]; then
    log "échec à l'étape « $STAGE » : rien n'a été modifié en production" >&2
    return
  fi
  cat >&2 <<EOF

=== Déploiement interrompu à l'étape : $STAGE ===
Retour arrière (à adapter) :
  1. Code backend précédent : rsync -a --delete --exclude venv/ --exclude mediafiles/ \\
       --exclude staticfiles/ --exclude test_mediafiles/ "${SNAPSHOT:-<aucun instantané>}/" "$BACKEND_DIR/"
  2. Frontend précédent    : [ -d "$FRONTEND_DIR/dist.old" ] && mv "$FRONTEND_DIR/dist" "$FRONTEND_DIR/dist.failed" \\
       && mv "$FRONTEND_DIR/dist.old" "$FRONTEND_DIR/dist"
  3. Si des migrations ont été appliquées et posent problème : restaurer la sauvegarde
     predeploy (ops/backup/restore.md, dossier predeploy/) — ne pas « migrate » à l'envers
     sans avoir lu les migrations concernées.
  4. pm2 restart $PM2_APPS --update-env && pm2 save
  5. Vérifier : curl -fsS $HEALTH_URL
Révision précédente : ${PREVIOUS_REVISION:-inconnue}
EOF
}

cleanup() {
  local status=$?
  if [[ -n "$BUILD_DIR" && -d "$BUILD_DIR" ]]; then
    rm -rf -- "$BUILD_DIR"
  fi
  if [[ $status -ne 0 ]]; then
    rollback_hint
  fi
  exit "$status"
}
trap cleanup EXIT

manage() {
  # Toujours les settings de production, quel que soit l'environnement du shell.
  (cd "$BACKEND_DIR" && DJANGO_SETTINGS_MODULE=config.settings.prod "$VENV_PY" manage.py "$@")
}

check_prerequisites() {
  [[ -n "$REF" ]] || die "usage : $0 <ref-git>   (branche, tag ou commit)"
  [[ -d "$REPO_DIR/.git" ]] || die "clone git introuvable : $REPO_DIR (voir ops/deploy/README.md)"
  [[ -r "$APP_DIR/.env" ]] || die "$APP_DIR/.env introuvable"
  [[ -x "$VENV_PY" ]] || die "environnement Python introuvable : $VENV_PY"
  local tool
  for tool in git rsync tar curl pm2; do
    command -v "$tool" >/dev/null || die "commande manquante : $tool"
  done
  if [[ -z "$FRONTEND_DIST_TARBALL" ]]; then
    command -v npm >/dev/null || die "npm introuvable : installez Node.js 22 ou fournissez FRONTEND_DIST_TARBALL"
  fi
  if ! grep -Eq '^[[:space:]]*(export[[:space:]]+)?DJANGO_SETTINGS_MODULE=config\.settings\.prod' "$APP_DIR/.env"; then
    log "avertissement : le .env ne contient pas DJANGO_SETTINGS_MODULE=config.settings.prod (PM2 doit alors le fournir)"
  fi
}

resolve_ref() {
  STAGE="récupération de $REF"
  git -C "$REPO_DIR" fetch --quiet --tags --prune "$GIT_REMOTE"
  local sha
  # Branche distante d'abord (une branche locale du clone peut être en retard), puis tag / commit.
  sha="$(git -C "$REPO_DIR" rev-parse --verify --quiet "$GIT_REMOTE/$REF^{commit}" \
    || git -C "$REPO_DIR" rev-parse --verify --quiet "$REF^{commit}" || true)"
  [[ -n "$sha" ]] || die "référence git inconnue : $REF"
  printf '%s' "$sha"
}

export_source() {
  local sha="$1"
  STAGE="export du code ($sha)"
  BUILD_DIR="$(mktemp -d /tmp/revue-deploy.XXXXXX)"
  git -C "$REPO_DIR" archive --format=tar "$sha" | tar -x -C "$BUILD_DIR"
  log "code exporté dans $BUILD_DIR"
}

build_frontend() {
  STAGE="build du frontend"
  if [[ -n "$FRONTEND_DIST_TARBALL" ]]; then
    [[ -r "$FRONTEND_DIST_TARBALL" ]] || die "archive introuvable : $FRONTEND_DIST_TARBALL"
    mkdir -p "$BUILD_DIR/frontend/dist"
    tar -xzf "$FRONTEND_DIST_TARBALL" -C "$BUILD_DIR/frontend/dist" --no-same-owner
    log "frontend : dist fourni ($FRONTEND_DIST_TARBALL)"
  else
    log "frontend : npm ci + build"
    (cd "$BUILD_DIR/frontend" && npm ci --no-audit --no-fund && npm run build)
  fi
  [[ -f "$BUILD_DIR/frontend/dist/index.html" ]] || die "frontend/dist/index.html absent après le build"
}

snapshot_backend() {
  STAGE="instantané du backend actuel"
  PREVIOUS_REVISION="$(cat "$BACKEND_DIR/REVISION" 2>/dev/null || echo inconnue)"
  mkdir -p "$RELEASES_DIR"
  SNAPSHOT="$RELEASES_DIR/backend-$(date -u +%Y%m%dT%H%M%SZ)-${PREVIOUS_REVISION:0:12}"
  rsync -a --exclude venv/ --exclude .venv/ --exclude mediafiles/ --exclude staticfiles/ \
    --exclude test_mediafiles/ --exclude __pycache__/ "$BACKEND_DIR/" "$SNAPSHOT/"
  log "instantané du backend précédent ($PREVIOUS_REVISION) : $SNAPSHOT"
  # On garde les KEEP_RELEASES instantanés les plus récents.
  local old
  while IFS= read -r old; do
    rm -rf -- "$old"
  done < <(find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -name 'backend-*' | sort -r | tail -n +"$((KEEP_RELEASES + 1))")
}

sync_backend() {
  local sha="$1"
  STAGE="copie du backend"
  PRODUCTION_TOUCHED=1
  # --delete retire les fichiers supprimés du dépôt ; les dossiers exclus (venv, fichiers
  # clients, statiques) ne sont jamais touchés (pas de --delete-excluded).
  rsync -a --delete \
    --exclude venv/ --exclude .venv/ --exclude mediafiles/ --exclude staticfiles/ \
    --exclude test_mediafiles/ --exclude __pycache__/ --exclude '*.pyc' \
    --exclude .pytest_cache/ --exclude .celery_broker/ --exclude .env --exclude logs/ \
    --exclude 'celerybeat-schedule*' \
    "$BUILD_DIR/backend/" "$BACKEND_DIR/"
  printf '%s\n' "$sha" > "$BACKEND_DIR/REVISION"
  # Scripts d'exploitation (sauvegardes, déploiement) à jour sur le serveur.
  rsync -a --delete "$BUILD_DIR/ops/" "$APP_DIR/ops/"
  chmod +x "$APP_DIR"/ops/*/*.sh
  log "backend copié (révision $sha)"
}

install_backend() {
  STAGE="dépendances Python"
  "$VENV_PY" -m pip install --quiet --disable-pip-version-check -r "$BACKEND_DIR/requirements/prod.txt"
  STAGE="vérifications Django"
  manage check --deploy --fail-level ERROR
  STAGE="migrations"
  manage migrate --noinput
  STAGE="fichiers statiques"
  manage collectstatic --noinput
}

switch_frontend() {
  STAGE="bascule du frontend"
  rm -rf -- "$FRONTEND_DIR/dist.new"
  mkdir -p "$FRONTEND_DIR"
  cp -a "$BUILD_DIR/frontend/dist" "$FRONTEND_DIR/dist.new"
  rm -rf -- "$FRONTEND_DIR/dist.old"
  if [[ -d "$FRONTEND_DIR/dist" ]]; then
    mv "$FRONTEND_DIR/dist" "$FRONTEND_DIR/dist.old"
  fi
  mv "$FRONTEND_DIR/dist.new" "$FRONTEND_DIR/dist"
  log "frontend en ligne (précédent conservé dans dist.old)"
}

restart_services() {
  STAGE="redémarrage PM2"
  # shellcheck disable=SC2086  # liste de noms séparés par des espaces, voulue
  pm2 restart $PM2_APPS --update-env
  pm2 save
}

health_check() {
  STAGE="contrôle de santé"
  local attempt body
  # Le worker peut mettre quelques secondes à répondre au ping après redémarrage.
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if body="$(curl -fsS -m 10 "$HEALTH_URL" 2>/dev/null)"; then
      log "santé : $body"
      return 0
    fi
    log "santé : pas encore OK (essai $attempt/12), nouvel essai dans 5 s"
    sleep 5
  done
  body="$(curl -sS -m 10 "$HEALTH_URL" 2>&1 || true)"
  die "contrôle de santé en échec : $body"
}

main() {
  check_prerequisites
  local sha
  sha="$(resolve_ref)"
  log "déploiement de $REF -> $sha"

  export_source "$sha"

  if [[ "$SKIP_BACKUP" != "1" ]]; then
    STAGE="sauvegarde predeploy"
    # Script installé par le déploiement précédent, sinon celui de la version déployée
    # (premier déploiement avec ce script).
    local backup_script="$APP_DIR/ops/backup/backup.sh"
    [[ -f "$backup_script" ]] || backup_script="$BUILD_DIR/ops/backup/backup.sh"
    APP_DIR="$APP_DIR" bash "$backup_script" predeploy
  fi

  build_frontend
  snapshot_backend
  sync_backend "$sha"
  install_backend
  switch_frontend
  restart_services
  health_check
  STAGE="terminé"
  log "déploiement réussi : $sha (précédent : $PREVIOUS_REVISION)"
}

main
