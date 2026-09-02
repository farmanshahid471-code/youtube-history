#!/usr/bin/env bash
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ is required. Install it and run this file again."
  exit 1
fi
if [ ! -d .venv ]; then
  echo "Setting up environment (first run only)..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
python -m playwright install chromium
python auto_player.py "$@"
