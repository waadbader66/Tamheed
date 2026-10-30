#!/bin/zsh
# One-time setup: Python venv, backend deps, frontend deps, database.
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12}
[ -x "$PY" ] || PY=python3
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm install --silent)
[ -f .env ] || cp .env.example .env
(cd backend && ../.venv/bin/python -m app.seed)
echo "Setup complete. Edit .env, then run: ./scripts/dev.sh"
