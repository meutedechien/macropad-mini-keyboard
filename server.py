#!/usr/bin/env python3
"""Configurateur du macropad 3 touches + molette (CH552G, firmware MacroPad RGB).

Sert index.html et règle le clavier en direct par son canal HID constructeur :
  GET  /api/state   réglages enregistrés
  POST /api/live    applique les réglages tout de suite (+ aperçu de l'appui)
  POST /api/save    enregistre dans le clavier et dans state.json
  POST /api/upload  met à jour le firmware (passe le clavier en bootloader et flashe)
  GET  /api/device  état du clavier : absent, ancien (firmware sans canal), direct, bootloader
  GET  /api/apps    applications installées (pour l'action « ouvrir une appli »)

À lancer avec venv/bin/python (hidapi et pyusb).

Actions Mac : le clavier prévient l'appli par le canal constructeur, et l'appli
ouvre l'application ou lance la commande. L'appli doit donc tourner en
arrière-plan (install.sh l'ajoute à l'ouverture de session). Option : --no-browser.
"""
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8766
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
FIRMWARE_DIR = os.path.join(HERE, "firmware")
VENV_PY = os.path.join(HERE, "venv", "bin", "python")
sys.path.insert(0, FIRMWARE_DIR)
import configure                            # noqa: E402  encodage du bloc de réglages
import live                                 # noqa: E402  canal HID en direct
LOCK = threading.Lock()
VID, PID = 0x1189, 0x8890
# Ordre des entrées dans le firmware
SLOTS = ["b0", "b1", "b2", "ccw", "press", "cw"]
# Comment chaque action Mac est codée dans le firmware
ACTION_CODES = {"app": "mac", "terminal": "mac", "shell": "mac"}

DEFAULT = {
    "layers": [{"buttons": ["1", "2", "3"],
                "knob": {"ccw": "volumedown", "press": "mute", "cw": "volumeup"}}],
    "leds": [{"repos": {"effet": "fixe", "couleur": "#ff2000"},
              "appui": {"effet": "comme_repos", "couleur": "#ff2000"}},
             {"repos": {"effet": "fixe", "couleur": "#0040ff"},
              "appui": {"effet": "comme_repos", "couleur": "#0040ff"}},
             {"repos": {"effet": "fixe", "couleur": "#00c83c"},
              "appui": {"effet": "clignote", "couleur": "#00c83c"}}],
    "luminosite": 90,
    "vitesse": 5,
}


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return DEFAULT


def firmware_config(state):
    """Traduit l'état de l'appli en macropad.json pour firmware/configure.py."""
    actions = state.get("actions", {})
    layer = state["layers"][0]
    values = {"touche1": ("b0", layer["buttons"][0]), "touche2": ("b1", layer["buttons"][1]),
              "touche3": ("b2", layer["buttons"][2]), "molette_gauche": ("ccw", layer["knob"]["ccw"]),
              "molette_appui": ("press", layer["knob"]["press"]),
              "molette_droite": ("cw", layer["knob"]["cw"])}
    entrees = {}
    for name, (slot, value) in values.items():
        v = ACTION_CODES[actions[slot]["type"]] if slot in actions else value
        if "," in v:
            raise ValueError(f"{name} : une seule frappe par touche avec ce firmware")
        if "click" in v or "wheel" in v:
            raise ValueError(f"{name} : les actions souris ne sont pas gérées par ce firmware")
        entrees[name] = v
    return {"entrees": entrees, "leds": state.get("leds", DEFAULT["leds"]),
            "luminosite": state.get("luminosite", 90), "vitesse": state.get("vitesse", 5)}


def run_action(slot):
    """Exécute l'action Mac d'une entrée (appelé à l'appui)."""
    action = load_state().get("actions", {}).get(slot)
    if not action:
        return
    t, value = action.get("type"), action.get("value", "")
    if t == "app" and value:
        cmd = ["open", "-a", value]
    elif t == "terminal" and value:
        script = value.replace("\\", "\\\\").replace('"', '\\"')
        cmd = ["osascript", "-e", 'tell application "Terminal"', "-e", "activate",
               "-e", f'do script "{script}"', "-e", "end tell"]
    elif t == "shell" and value:
        cmd = ["/bin/sh", "-c", value]
    else:
        return
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def on_event(index, pressed):
    if pressed and index < len(SLOTS):
        run_action(SLOTS[index])


def flash(config):
    """Écrit firmware/macropad.json puis lance configure.py --flash (clavier en bootloader)."""
    with open(os.path.join(FIRMWARE_DIR, "macropad.json"), "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    env = dict(os.environ, DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib")
    with LOCK:
        p = subprocess.run([VENV_PY, "configure.py", "--flash"], cwd=FIRMWARE_DIR, env=env,
                           capture_output=True, text=True, timeout=60)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def device_state():
    p = subprocess.run(["ioreg", "-p", "IOUSB", "-l", "-w0"], capture_output=True, text=True)
    if '"idVendor" = 17224' in p.stdout:
        return "bootloader"
    if '"idVendor" = 4489' in p.stdout:
        return "direct" if live.available() else "ancien"
    return "absent"


def block_for(state):
    return configure.build(firmware_config(state))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/api/state":
            return self.send_json(load_state())
        if self.path == "/api/device":
            return self.send_json({"state": device_state()})
        if self.path == "/api/apps":
            apps = set()
            for d in ("/Applications", "/System/Applications", "/System/Applications/Utilities",
                      os.path.expanduser("~/Applications")):
                try:
                    apps.update(n[:-4] for n in os.listdir(d) if n.endswith(".app"))
                except OSError:
                    pass
            return self.send_json(sorted(apps, key=str.lower))
        if self.path in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/live":
            try:
                live.apply(block_for(body["state"]), int(body.get("preview", 0)))
                return self.send_json({"ok": True})
            except (ValueError, OSError) as e:
                return self.send_json({"ok": False, "msg": str(e)})
        if self.path == "/api/save":
            try:
                block = block_for(body)
            except ValueError as e:
                return self.send_json({"ok": False, "msg": str(e)})
            with open(STATE, "w") as f:
                json.dump(body, f, indent=2, ensure_ascii=False)
            try:
                live.save(block)
            except OSError as e:
                return self.send_json({"ok": False, "msg": f"Réglages gardés sur le Mac, mais pas sur le clavier : {e}"})
            return self.send_json({"ok": True, "msg": "Enregistré dans le clavier."})
        if self.path == "/api/upload":
            try:
                config = firmware_config(body)
            except ValueError as e:
                return self.send_json({"ok": False, "msg": str(e)})
            dev = device_state()
            if dev == "direct":                 # le firmware sait passer seul en bootloader
                try:
                    live.reboot_to_bootloader()
                    for _ in range(40):
                        time.sleep(0.25)
                        if device_state() == "bootloader":
                            break
                except OSError:
                    pass
            if device_state() != "bootloader":
                return self.send_json({"ok": False, "waiting": True, "msg": "Pour mettre à jour : "
                    "maintiens la touche 1 puis appuie sur la molette 2 secondes (LED blanches), "
                    "ou rebranche le clavier en maintenant la touche 1. L'envoi partira tout seul."})
            ok, out = flash(config)
            msg = "Firmware mis à jour : le clavier redémarre." if ok else \
                  "Échec du flash : " + (out.splitlines()[-1] if out else "erreur inconnue")
            return self.send_json({"ok": ok, "msg": msg})
        self.send_error(404)


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Macropad : http://localhost:{PORT}")
    threading.Thread(target=live.listen, args=(on_event,), daemon=True).start()
    if "--no-browser" not in sys.argv:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    srv.serve_forever()
