#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x "./.venv/bin/uvicorn" ]; then
  echo "Installing the mobile companion API dependencies..."
  ./.venv/bin/pip install -r requirements.txt
fi

echo "HikeJournal mobile API is starting on port 8506."
echo "Keep this window open while using the Android app on your home network."
exec ./.venv/bin/uvicorn mobile_api:app --host 0.0.0.0 --port 8506
