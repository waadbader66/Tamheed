#!/usr/bin/env bash
# Production: build the website once, then serve website + API from ONE port (default 8000).
# Put it behind HTTPS (e.g. a reverse proxy or your host's TLS) and set COOKIE_SECURE=1 and APP_BASE_URL in .env.
set -e
cd "$(dirname "$0")/.."
(cd frontend && npm install --silent && npx vite build)
cd backend && exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
