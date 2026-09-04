#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Python virtual environment is missing. Run first: .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi
exec .venv/bin/python pymermaid_app.py
