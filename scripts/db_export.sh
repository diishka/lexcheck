#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-lexai}"
DB_USER="${DB_USER:-postgres}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="${1:-$BACKUP_DIR/${DB_NAME}_${STAMP}.dump}"
TMP_FILE="${OUT_FILE}.tmp"

mkdir -p "$BACKUP_DIR"

echo "Exporting PostgreSQL database '$DB_NAME'..."
rm -f "$TMP_FILE"
pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --host="$DB_HOST" \
  --port="$DB_PORT" \
  --username="$DB_USER" \
  --file="$TMP_FILE" \
  "$DB_NAME"

mv "$TMP_FILE" "$OUT_FILE"

echo "Backup created:"
echo "  $OUT_FILE"
