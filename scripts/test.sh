#!/bin/zsh
cd "$(dirname "$0")/../backend" && ../.venv/bin/python -m pytest -q "$@"
