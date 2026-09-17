"""Canal constructeur du firmware MacroPad RGB (report HID 3, page 0xFF00).

Vers le clavier (15 octets après l'identifiant de report) :
  1 réglage     [1, position, longueur <= 12, octets...]
  2 enregistrer dans la mémoire de données du clavier
  3 passer en bootloader
  4 aperçu de l'appui [4, masque des touches]
Depuis le clavier :
  [1, entrée, appuyé] pour les entrées réglées en « action Mac »

Une seule connexion est gardée ouverte, en mode partagé : macOS continue de
recevoir les frappes normalement.
"""
import ctypes
import threading
import time

import hid

VID, PID = 0x1189, 0x8890
VENDOR_PAGE = 0xFF00
CHUNK = 12

# hidapi ouvre les appareils en exclusif par défaut sur macOS : les frappes
# n'arriveraient plus au système.
ctypes.CDLL(hid.__file__).hid_darwin_set_open_exclusive(0)

_lock = threading.Lock()
_dev = None
_last_sent = None


def _path():
    for d in hid.enumerate(VID, PID):
        if d["usage_page"] == VENDOR_PAGE:
            return d["path"]
    return None


def available():
    return _path() is not None


def _connect():
    global _dev, _last_sent
    if _dev is None:
        path = _path()
        if not path:
            raise OSError("canal de réglage introuvable (ancien firmware ?)")
        dev = hid.device()
        dev.open_path(path)
        dev.set_nonblocking(False)
        _dev, _last_sent = dev, None
    return _dev


def _drop():
    global _dev
    if _dev is not None:
        try:
            _dev.close()
        except OSError:
            pass
    _dev = None


def _send(payload):
    report = [3, *payload]
    try:
        _connect().write(report + [0] * (16 - len(report)))
    except (OSError, ValueError):
        _drop()
        raise OSError("clavier débranché")


def apply(block, preview_mask=0, force=False):
    """Envoie les octets du bloc de réglages qui ont changé depuis le dernier envoi."""
    global _last_sent
    with _lock:
        _connect()
        old = None if force or _last_sent is None else _last_sent
        for pos in range(5, len(block), CHUNK):
            chunk = block[pos:pos + CHUNK]
            if old is None or chunk != old[pos:pos + CHUNK]:
                _send([1, pos, len(chunk), *chunk])
        _send([4, preview_mask & 7])
        _last_sent = bytes(block)


def save(block):
    apply(block, force=True)
    with _lock:
        _send([2])


def reboot_to_bootloader():
    with _lock:
        _send([3])
        _drop()


def listen(on_event):
    """Boucle sans fin (à lancer dans un thread) : on_event(entrée, appuyé)."""
    while True:
        try:
            with _lock:
                dev = _connect()
            data = dev.read(16, 500)
            if len(data) >= 4 and data[0] == 3 and data[1] == 1:
                on_event(data[2], bool(data[3]))
        except (OSError, ValueError):
            with _lock:
                _drop()
            time.sleep(1)
