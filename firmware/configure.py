#!/usr/bin/env python3
"""Applique une configuration JSON au firmware MacroPad RGB, puis le flashe.

usage : configure.py [macropad.json] [--flash]

Le firmware contient un bloc de 55 octets commençant par « MPCF ». Ce script le
réécrit dans une copie du binaire (macropad_rgb_config.bin). Avec --flash, il
l'envoie au clavier, qui doit être en bootloader : touche 1 + appui molette pendant
2 secondes (ou touche 1 maintenue au branchement).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIRMWARE = os.path.join(HERE, "macropad_rgb.bin")
OUTPUT = os.path.join(HERE, "macropad_rgb_config.bin")

SLOTS = ["touche1", "touche2", "touche3", "molette_gauche", "molette_appui", "molette_droite"]
EFFECTS = {"eteinte": 0, "fixe": 1, "respiration": 2, "clignote": 3, "flash": 4,
           "arc-en-ciel": 5, "comme_repos": 6}
MODIFIERS = {"ctrl": 0x01, "shift": 0x02, "alt": 0x04, "opt": 0x04, "cmd": 0x08, "win": 0x08}
MEDIA = {"play": 0xCD, "next": 0xB5, "prev": 0xB6, "previous": 0xB6, "stop": 0xB7,
         "mute": 0xE2, "volumeup": 0xE9, "volumedown": 0xEA, "calculator": 0x192,
         "screenlock": 0x19E, "favorites": 0x182}
KEYS = {
    **{chr(c): 0x04 + c - ord("a") for c in range(ord("a"), ord("z") + 1)},
    **{str(n): 0x1E + n - 1 for n in range(1, 10)}, "0": 0x27,
    **{f"f{n}": 0x3A + n - 1 for n in range(1, 13)},
    **{f"f{n}": 0x68 + n - 13 for n in range(13, 25)},
    "enter": 0x28, "escape": 0x29, "backspace": 0x2A, "tab": 0x2B, "space": 0x2C,
    "minus": 0x2D, "equal": 0x2E, "right": 0x4F, "left": 0x50, "down": 0x51, "up": 0x52,
    "home": 0x4A, "pageup": 0x4B, "delete": 0x4C, "end": 0x4D, "pagedown": 0x4E,
    "leftbracket": 0x2F, "rightbracket": 0x30, "backslash": 0x31, "nonushash": 0x32,
    "semicolon": 0x33, "quote": 0x34, "grave": 0x35, "comma": 0x36, "dot": 0x37, "slash": 0x38,
    "capslock": 0x39, "printscreen": 0x46, "scrolllock": 0x47, "pause": 0x48, "insert": 0x49,
    "numlock": 0x53, "numpadslash": 0x54, "numpadasterisk": 0x55, "numpadminus": 0x56,
    "numpadplus": 0x57, "numpadenter": 0x58,
    **{f"numpad{n}": 0x59 + n - 1 for n in range(1, 10)}, "numpad0": 0x62, "numpaddot": 0x63,
    "nonusbackslash": 0x64, "application": 0x65, "power": 0x66, "numpadequal": 0x67,
}


def parse_key(value):
    *mods, key = value.lower().split("-")
    mask = 0
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError(f"modificateur inconnu : {m}")
        mask |= MODIFIERS[m]
    if key not in KEYS:
        raise ValueError(f"touche inconnue : {key}")
    return mask, KEYS[key]


def encode_input(value):
    """Une entrée → 4 octets (type, modificateurs, code poids faible, poids fort).

    « »               rien
    « volumeup »      touche multimédia
    « cmd-shift-c »   touche clavier maintenue
    « double:alt »    double appui sur un modificateur
    « mac »           action Mac, faite par l'appli
    « mac+space »     action Mac, puis touche maintenue 250 ms plus tard
    """
    if not value:
        return [0, 0, 0, 0]
    if value in MEDIA:
        code = MEDIA[value]
        return [2, 0, code & 0xFF, code >> 8]
    if value.startswith("double:"):
        return [3, MODIFIERS[value[7:]], 0, 0]
    if value == "mac":
        return [4, 0, 0, 0]
    if value.startswith("mac+"):
        mask, code = parse_key(value[4:])
        return [5, mask, code, 0]
    mask, code = parse_key(value)
    return [1, mask, code, 0]


def encode_state(state):
    color = state.get("couleur", "#000000").lstrip("#")
    r, g, b = (int(color[k:k + 2], 16) for k in (0, 2, 4))
    return [EFFECTS[state.get("effet", "fixe")], r, g, b]


def normalize_led(led):
    """Accepte aussi l'ancien format {couleur, mode}."""
    if "repos" in led:
        return led
    c, mode = led.get("couleur", "#ffffff"), led.get("mode", "fixe")
    old = {"eteinte": ("eteinte", "eteinte"), "fixe": ("fixe", "fixe"),
           "flash": ("eteinte", "flash"), "appui": ("eteinte", "fixe"),
           "respiration": ("respiration", "fixe")}[mode]
    return {"repos": {"effet": old[0], "couleur": c}, "appui": {"effet": old[1], "couleur": c}}


def build(cfg):
    block = [ord(c) for c in "MPCF"] + [3]
    for slot in SLOTS:
        block += encode_input(cfg["entrees"].get(slot, ""))
    for led in cfg["leds"]:
        led = normalize_led(led)
        block += encode_state(led["repos"]) + encode_state(led["appui"])
    block.append(max(0, min(255, int(cfg.get("luminosite", 90)))))
    block.append(max(1, min(10, int(cfg.get("vitesse", 5)))))
    assert len(block) == 55
    return bytes(block)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else os.path.join(HERE, "macropad.json")
    with open(path) as f:
        block = build(json.load(f))

    data = bytearray(open(FIRMWARE, "rb").read())
    at = data.find(b"MPCF")
    if at < 0 or data.count(b"MPCF") != 1:
        sys.exit("bloc MPCF introuvable dans le firmware")
    data[at:at + len(block)] = block
    with open(OUTPUT, "wb") as f:
        f.write(data)
    print(f"Configuration écrite dans {os.path.basename(OUTPUT)} ({len(data)} octets)")

    if "--flash" in sys.argv:
        sys.path.insert(0, HERE)
        import chprog
        isp = chprog.Programmer()
        isp.detect()
        print("Puce détectée :", isp.chipname)
        isp.erase()
        isp.flash_data(bytes(data))
        isp.verify_data(bytes(data))
        try:
            isp.exit()                      # la puce redémarre sur le nouveau firmware
        except Exception:
            pass
        print("Flash réussi : le clavier redémarre avec les nouveaux réglages.")


if __name__ == "__main__":
    main()
