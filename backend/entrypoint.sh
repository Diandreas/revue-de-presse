#!/bin/sh
set -e

POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-revue}"

echo "En attente de Postgres sur ${POSTGRES_HOST}:${POSTGRES_PORT}..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" > /dev/null 2>&1; do
  sleep 1
done
echo "Postgres est prêt."

if [ "$RUN_MIGRATIONS" = "1" ]; then
  echo "Application des migrations..."
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput --clear || true
fi

exec "$@"
