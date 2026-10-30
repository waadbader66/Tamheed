#!/bin/zsh
# Starts backend (http://127.0.0.1:8710) and frontend (http://localhost:5710). Ctrl+C stops both.
cd "$(dirname "$0")/.."
(cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8710) &
BACK=$!
trap "kill $BACK 2>/dev/null" EXIT INT TERM
cd frontend && npx vite --port 5710 --host 0.0.0.0  # reachable from phones on the same Wi-Fi
