#!/bin/bash
# Double-clic : lance le configurateur du macropad et ouvre la page.
cd "$(dirname "$0")"
if curl -s -m 1 http://localhost:8766/ >/dev/null; then
  open http://localhost:8766
else
  exec /usr/bin/env python3 server.py
fi
