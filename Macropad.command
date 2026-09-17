#!/bin/bash
# Double-clic : ouvre la page (lance le serveur s'il ne tourne pas déjà).
cd "$(dirname "$0")"
if ! curl -s -m 1 http://localhost:8766/ >/dev/null; then
  DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib nohup ./venv/bin/python server.py --no-browser >server.log 2>&1 &
  sleep 1.5
fi
open http://localhost:8766
