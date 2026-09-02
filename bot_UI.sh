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
echo ""
echo "======================================================================"
echo "  Starting YouTube History Bot Web UI Control Panel..."
echo "  Opening dashboard in browser: http://localhost:5000"
echo "======================================================================"
echo ""
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:5000 &
elif command -v open >/dev/null 2>&1; then
  open http://localhost:5000 &
fi
python bot_ui.py "$@"
