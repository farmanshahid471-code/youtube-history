#!/usr/bin/env bash
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi
"$PY" launch_chrome_debug.py "$@"
echo
echo "Done. Keep this Chrome window open, then press START BOT in the dashboard"
echo "and turn ON 'Attach to running Chrome (CDP)'."
echo
read -r -p "Press Enter to close..."
