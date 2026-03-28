#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$PROJECT_DIR/lexcheck"
DEFAULT_NODE_BIN="$HOME/.nvm/versions/node/v24.14.0/bin"

# Подключаем Node если есть
if [ -d "$DEFAULT_NODE_BIN" ]; then
  export PATH="$DEFAULT_NODE_BIN:$PATH"
fi

command -v npm >/dev/null || { echo "npm not found"; exit 1; }
command -v python >/dev/null || { echo "python not found"; exit 1; }

echo "Starting backend..."
(
  cd "$APP_DIR/backend" || exit 1
  ./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
) &

BACKEND_PID=$!

echo "Starting frontend..."
(
  cd "$APP_DIR/frontend" || exit 1
  npm run dev
) &

FRONTEND_PID=$!

echo "App is starting..."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://127.0.0.1:8000"

# Ждём завершения
wait $BACKEND_PID $FRONTEND_PID