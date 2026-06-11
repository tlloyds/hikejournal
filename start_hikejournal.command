#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x "./.venv/bin/streamlit" ]; then
  echo "Missing Streamlit virtualenv at ./.venv"
  echo "Create it first, then install requirements."
  exit 1
fi

exec ./.venv/bin/streamlit run app.py --server.port 8505
