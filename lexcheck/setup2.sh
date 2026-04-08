#!/bin/bash
# LexCheck UZ - One-command setup
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
DB_NAME="${DB_NAME:-lexai}"

echo "═══════════════════════════════════════════"
echo "   LexCheck UZ — Setup Script"
echo "═══════════════════════════════════════════"

# Check dependencies
command -v python3 >/dev/null || { echo "❌ Python 3 not found"; exit 1; }
command -v psql    >/dev/null || { echo "❌ PostgreSQL not found. Install: https://www.postgresql.org/download/"; exit 1; }
command -v node    >/dev/null || { echo "❌ Node.js not found. Install: https://nodejs.org/"; exit 1; }

# ── 1. Create DB ──────────────────────────────────────────────────────────────
echo ""
echo "1️⃣  Setting up PostgreSQL database..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 \
|| sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;"
if sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'laws'" | grep -q 1; then
  echo "   ✅ Database '$DB_NAME' already has tables"
else
  echo "   ℹ️  Database '$DB_NAME' created, but no laws were imported automatically"
  echo "   ℹ️  Restore a real backup with: ./scripts/db_import.sh backups/<file>.dump"
fi
# ── 2. Backend ────────────────────────────────────────────────────────────────
echo ""
echo "2️⃣  Setting up Python backend..."
cd "$BACKEND_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -r "$ROOT_DIR/requirements.txt" -q

if [ ! -f .env ]; then
  cp .env.example .env
  echo "   ⚠️  Created .env — check DATABASE_URL / Ollama settings before first run"
fi
cd "$SCRIPT_DIR"
echo "   ✅ Backend ready"

# ── 3. Frontend ───────────────────────────────────────────────────────────────
echo ""
echo "3️⃣  Setting up React frontend..."
cd "$FRONTEND_DIR"
npm install -q
cd "$SCRIPT_DIR"
echo "   ✅ Frontend ready"

echo ""
echo "═══════════════════════════════════════════"
echo "   ✅ Setup complete!"
echo "═══════════════════════════════════════════"
echo ""
echo "To start the app:"
echo ""
echo "  From project root:"
echo "    ./run.sh"
echo ""
echo "Then open: http://localhost:3000"
echo ""
echo "To export the database for another person:"
echo "  ./scripts/db_export.sh"
echo ""
echo "To restore a backup on another machine:"
echo "  ./scripts/db_import.sh backups/lexai_YYYYMMDD_HHMMSS.dump"
echo ""
echo "To use Ollama (free, local):"
echo "  1. Install: https://ollama.com"
echo "  2. Run: ollama pull qwen2.5:7b"
echo "  3. In backend/.env set LLM_PROVIDER=ollama"
