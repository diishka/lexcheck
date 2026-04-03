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
[ -x "$APP_DIR/backend/venv/bin/python" ] || { echo "backend venv not found: run ./lexcheck/setup.sh"; exit 1; }
[ -d "$APP_DIR/frontend/node_modules" ] || { echo "frontend dependencies not found: run ./lexcheck/setup.sh"; exit 1; }

BACKEND_PID=""
FRONTEND_PID=""

stop_process() {
  local pid="${1:-}"
  if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
    return
  fi

  if command -v pkill >/dev/null 2>&1; then
    pkill -TERM -P "$pid" 2>/dev/null || true
  fi
  kill -TERM "$pid" 2>/dev/null || true
}

cleanup() {
  local exit_code="${1:-0}"
  trap - INT TERM

  stop_process "$FRONTEND_PID"
  stop_process "$BACKEND_PID"
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true

  exit "$exit_code"
}

trap 'cleanup 130' INT TERM

echo "Starting backend..."
(
  cd "$APP_DIR/backend" || exit 1
  exec ./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
) &

BACKEND_PID=$!

echo "Starting frontend..."
(
  cd "$APP_DIR/frontend" || exit 1
  exec npm run dev
) &

FRONTEND_PID=$!

echo "App is starting..."
echo "Frontend: http://localhost:3000"
echo "Backend:  http://127.0.0.1:8000"

# Ждём, пока один из процессов завершится, потом аккуратно останавливаем второй.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
cleanup $?
