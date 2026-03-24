#!/usr/bin/env bash

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$PROJECT_DIR/lexcheck"
DEFAULT_NODE_BIN="$HOME/.nvm/versions/node/v24.14.0/bin"

if [ -d "$DEFAULT_NODE_BIN" ]; then
  export PATH="$DEFAULT_NODE_BIN:$PATH"
fi

command -v konsole >/dev/null || { echo "konsole not found"; exit 1; }
command -v npm >/dev/null || { echo "npm not found"; exit 1; }

konsole -p tabtitle="Backend" -e bash -ic "
cd \"$APP_DIR/backend\" || exit 1
set +e
./venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
status=\$?
echo
echo \"Backend stopped with code \$status\"
exec bash
" &

konsole -p tabtitle="Frontend" -e bash -ic "
cd \"$APP_DIR/frontend\" || exit 1
set +e
npm run dev
status=\$?
echo
echo \"Frontend stopped with code \$status\"
exec bash
" &

echo "App is starting..."
echo "Open: http://localhost:3000"
