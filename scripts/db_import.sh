#!/usr/bin/env bash

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <backup-file> [db-name]"
  exit 1
fi

BACKUP_FILE="$1"
DB_NAME="${2:-${DB_NAME:-lexai}}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

echo "Ensuring database '$DB_NAME' exists..."
if ! psql --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1; then
  createdb --host="$DB_HOST" --port="$DB_PORT" --username="$DB_USER" "$DB_NAME"
fi

case "$BACKUP_FILE" in
  *.dump)
    echo "Restoring custom dump into '$DB_NAME'..."
    pg_restore \
      --clean \
      --if-exists \
      --no-owner \
      --no-privileges \
      --host="$DB_HOST" \
      --port="$DB_PORT" \
      --username="$DB_USER" \
      --dbname="$DB_NAME" \
      "$BACKUP_FILE"
    ;;
  *.sql)
    echo "Restoring SQL file into '$DB_NAME'..."
    psql \
      --host="$DB_HOST" \
      --port="$DB_PORT" \
      --username="$DB_USER" \
      --dbname="$DB_NAME" \
      --file="$BACKUP_FILE"
    ;;
  *)
    echo "Unsupported backup format: $BACKUP_FILE"
    echo "Use .dump or .sql"
    exit 1
    ;;
esac

echo "Restore complete."
