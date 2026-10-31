#!/usr/bin/env bash
# One-time setup: Python venv, backend deps, frontend deps, database.
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-$(command -v python3.12 || command -v python3)}
command -v node >/dev/null || { echo "Node.js 20+ is required (https://nodejs.org)"; exit 1; }
command -v ffmpeg >/dev/null || echo "Note: ffmpeg not found - welcome videos will not render (macOS: brew install ffmpeg)."
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm install --silent)
[ -f .env ] || cp .env.example .env
(cd backend && ../.venv/bin/python -m app.seed)
echo "Setup complete. Edit .env, then run: ./scripts/dev.sh"
