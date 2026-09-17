#!/bin/bash
# Installe l'appli Macropad : environnement Python et lancement à l'ouverture de session.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip -q install hidapi pyusb

PLIST="$HOME/Library/LaunchAgents/macropad.plist"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>macropad</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/venv/bin/python</string>
    <string>$DIR/server.py</string>
    <string>--no-browser</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>EnvironmentVariables</key>
  <dict><key>DYLD_FALLBACK_LIBRARY_PATH</key><string>/opt/homebrew/lib</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>$DIR/server.log</string>
</dict>
</plist>
PL
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Macropad tourne en arrière-plan : http://localhost:8766"
