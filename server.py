#!/usr/bin/env python3
"""Configurateur du macropad MINI KeyBoard (1189:8890) — serveur local.

Sert index.html et pilote ch57x-keyboard-tool :
  GET  /api/state   config enregistrée
  POST /api/upload  enregistre + écrit dans le clavier
  POST /api/led     {"mode": n}
  GET  /api/device  le clavier est-il branché ?
  GET  /api/apps    applications installées (pour l'action « ouvrir une appli »)

Actions Mac : le macropad envoie F13…F18 et Karabiner-Elements transforme ces
touches (uniquement pour ce clavier) en commandes shell.
"""
import json
import os
import shlex
import shutil
import subprocess
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8766
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
YAML = os.path.join(HERE, "config.yaml")
TOOL = shutil.which("ch57x-keyboard-tool") or os.path.expanduser("~/.cargo/bin/ch57x-keyboard-tool")
LOCK = threading.Lock()
KARABINER = os.path.expanduser("~/.config/karabiner/karabiner.json")
RULE_PREFIX = "Macropad — "
VID, PID = 0x1189, 0x8890
# Touche envoyée par chaque emplacement quand il porte une action Mac
FKEYS = {"b0": "f13", "b1": "f14", "b2": "f15", "ccw": "f16", "press": "f17", "cw": "f18"}

DEFAULT = {
    "layers": [{"buttons": ["1", "2", "3"],
                "knob": {"ccw": "volumedown", "press": "mute", "cw": "volumeup"}}],
    "led": 0,
}


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return DEFAULT


def q(s):
    return json.dumps(str(s))  # une chaîne JSON est une chaîne YAML valide


def to_yaml(state):
    actions = state.get("actions", {})
    out = ["orientation: normal", "rows: 1", "columns: 3", "knobs: 1", "layers:"]
    for layer in state["layers"]:
        b = [FKEYS[f"b{i}"] if f"b{i}" in actions else x for i, x in enumerate(layer["buttons"])]
        k = {s: FKEYS[s] if s in actions else v for s, v in layer["knob"].items()}
        out += [
            "  - buttons:",
            f"      - [{', '.join(q(x) for x in b)}]",
            "    knobs:",
            f"      - ccw: {q(k['ccw'])}",
            f"        press: {q(k['press'])}",
            f"        cw: {q(k['cw'])}",
        ]
    return "\n".join(out) + "\n"


def action_manipulator(slot, action):
    t, value = action.get("type"), action.get("value", "")
    m = {
        "type": "basic",
        "from": {"key_code": FKEYS[slot], "modifiers": {"optional": ["any"]}},
        "conditions": [{"type": "device_if", "identifiers": [{"vendor_id": VID, "product_id": PID}]}],
    }
    if t == "app":
        m["to"] = [{"shell_command": f"open -a {shlex.quote(value or 'Claude')}"}]
    elif t == "claude":
        m["to"] = [{"shell_command": "osascript -e 'tell application \"Terminal\"' -e 'activate' "
                                     "-e 'do script \"claude\"' -e 'end tell'"}]
    elif t == "claude_quick":
        # Double appui sur Option = barre de saisie rapide de l'appli Claude
        tap = {"key_code": "left_option", "hold_down_milliseconds": 40}
        m["to"] = [tap, {"key_code": "vk_none", "hold_down_milliseconds": 40}, tap]
    elif t == "dictation":
        # Appui : Terminal au premier plan. Maintenu : Espace enfoncé tant que la touche
        # l'est → la répétition de touche déclenche la dictée de Claude Code (/voice hold).
        m["to"] = [{"shell_command": "open -a Terminal"}]
        m["to_if_held_down"] = [{"key_code": "spacebar"}]
        m["parameters"] = {"basic.to_if_held_down_threshold_milliseconds": 200}
    elif t == "shell":
        m["to"] = [{"shell_command": value}]
    else:
        return None
    return m


def write_karabiner(state):
    """Remplace les règles « Macropad — » du profil actif de Karabiner."""
    try:
        with open(KARABINER) as f:
            cfg = json.load(f)
    except OSError:
        cfg = {"profiles": [{"name": "Default profile", "selected": True}]}
    backup = KARABINER + ".avant-macropad"
    if os.path.exists(KARABINER) and not os.path.exists(backup):
        shutil.copy(KARABINER, backup)
    profile = next((p for p in cfg["profiles"] if p.get("selected")), cfg["profiles"][0])
    rules = profile.setdefault("complex_modifications", {}).setdefault("rules", [])
    rules[:] = [r for r in rules if not r.get("description", "").startswith(RULE_PREFIX)]
    names = {"b0": "touche 1", "b1": "touche 2", "b2": "touche 3",
             "ccw": "molette gauche", "press": "molette appui", "cw": "molette droite"}
    for slot, action in state.get("actions", {}).items():
        m = action_manipulator(slot, action)
        if m:
            rules.append({"description": f"{RULE_PREFIX}{names[slot]}", "manipulators": [m]})
    os.makedirs(os.path.dirname(KARABINER), exist_ok=True)
    with open(KARABINER, "w") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def karabiner_running():
    return subprocess.run(["pgrep", "-qif", "console.user.server"]).returncode == 0


def run(args, stdin=None):
    with LOCK:
        p = subprocess.run([TOOL, *args], input=stdin, capture_output=True, text=True, timeout=30)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


def device_present():
    p = subprocess.run(["hidutil", "list"], capture_output=True, text=True)
    return "0x1189   0x8890" in p.stdout


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
            return self.send_json({"present": device_present()})
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
        if self.path == "/api/upload":
            yaml = to_yaml(body)
            ok, msg = run(["validate"], yaml)
            if not ok:
                return self.send_json({"ok": False, "msg": msg})
            ok, msg = run(["upload"], yaml)
            if ok:
                body["led"] = load_state().get("led", 0)
                with open(STATE, "w") as f:
                    json.dump(body, f, indent=2)
                with open(YAML, "w") as f:
                    f.write(yaml)
                write_karabiner(body)
                msg = msg or "Écrit dans le clavier"
                if body.get("actions") and not karabiner_running():
                    msg += " — ⚠️ Karabiner-Elements n'est pas lancé : les actions Mac ne marcheront pas"
            return self.send_json({"ok": ok, "msg": msg})
        if self.path == "/api/ledshuffle":
            # Le clavier ne reçoit pas de couleur : on lance le défilement puis on fige
            # (mode 1) après un délai aléatoire, ce qui tombe sur une autre couleur.
            import random, time
            ok, msg = run(["led", "2"])
            if ok:
                time.sleep(random.uniform(0.6, 3.5))
                ok, msg = run(["led", "1"])
            return self.send_json({"ok": ok, "msg": msg or "Nouvelle couleur figée"})
        if self.path == "/api/led":
            mode = int(body.get("mode", 0))
            ok, msg = run(["led", str(mode)])
            if ok:
                state = load_state()
                state["led"] = mode
                with open(STATE, "w") as f:
                    json.dump(state, f, indent=2)
            return self.send_json({"ok": ok, "msg": msg or f"Mode LED {mode}"})
        self.send_error(404)


if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Macropad : http://localhost:{PORT}")
    threading.Timer(0.5, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    srv.serve_forever()
