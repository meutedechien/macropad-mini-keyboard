#!/usr/bin/env python3
"""Envoie des paquets bruts (9 octets, Report ID 3) au macropad 1189:8890 sur EP 0x02.
usage: led_raw.py "a1 01" "b0 18 11" "aa a1"   (chaque argument = un paquet, sans le 03 initial)"""
import sys, usb.core, usb.backend.libusb1
be = usb.backend.libusb1.get_backend(find_library=lambda x: "/opt/homebrew/lib/libusb-1.0.0.dylib")
dev = usb.core.find(idVendor=0x1189, idProduct=0x8890, backend=be)
assert dev, "macropad introuvable"
cfg = dev.get_active_configuration()
intf = next(i for i in cfg if any(e.bEndpointAddress == 0x02 for e in i))
try:
    if dev.is_kernel_driver_active(intf.bInterfaceNumber):
        dev.detach_kernel_driver(intf.bInterfaceNumber)
except (NotImplementedError, usb.core.USBError):
    pass
usb.util.claim_interface(dev, intf.bInterfaceNumber)
for a in sys.argv[1:]:
    data = [3] + [int(x, 16) for x in a.split()]
    data += [0] * (65 - len(data))
    dev.write(0x02, data, timeout=1000)
usb.util.release_interface(dev, intf.bInterfaceNumber)
