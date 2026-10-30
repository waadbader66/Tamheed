#!/bin/bash
# Wipes demo data (database + generated files) and re-seeds the fictional company. Stop dev.sh first.
cd "$(dirname "$0")/.."
rm -rf data/storage/employees data/tamheed.db data/tamheed.db-*
(cd backend && ../.venv/bin/python -m app.seed --reset)
echo "Demo data reset."
