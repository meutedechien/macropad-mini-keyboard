# Macropad RGB — firmware libre et appli macOS pour le « MINI KeyBoard » (CH552G)

> **Branche pour bricoleurs.** Il faut ouvrir le boîtier, souder une résistance, et **le firmware
> d'origine est perdu définitivement**. Pour configurer le clavier sans rien modifier, utiliser la
> [branche principale](https://github.com/meutedechien/macropad-mini-keyboard).

*Custom firmware + macOS app for the cheap 3-key + knob macropad (CH552G). Requires opening the case
and soldering a resistor once; the stock firmware cannot be restored. English notes at the end.*

## Ce que ça apporte

- **Couleur RVB au choix pour chaque touche**, avec un effet au repos et un autre pendant l'appui :
  éteinte, fixe, respiration, clignotement, arc-en-ciel, flash puis fondu. Luminosité et vitesse
  réglables.
- **Réglage en direct** : chaque changement dans l'appli s'applique tout de suite au clavier, avec un
  aperçu de l'état « appui ». « Enregistrer » garde les réglages dans la puce.
- **Touches** : une frappe avec modificateurs (⌘⇧C…), une touche multimédia, ou une **action Mac**
  (ouvrir une application, lancer une commande dans Terminal ou en arrière-plan), sans Karabiner.
- **Molette** lue sous interruption : aucun cran perdu, même en tournant vite.
- **Mises à jour du firmware en un clic** depuis l'appli, sans rien débrancher.

## Matériel

Macropad 3 touches + molette vendu sous le nom « MINI KeyBoard » (USB `1189:8890`), avec une puce
**WCH CH552G** (boîtier SOP-16, 16 broches) et trois LED adressables. Vérifier la puce en ouvrant le
boîtier avant de commencer.

⚠️ Utiliser un **câble USB-A → USB-C** : la prise USB-C du boîtier n'a souvent pas ses résistances CC,
et un câble USB-C → USB-C ne l'alimente pas.

## 1. Installer l'appli

```bash
brew install libusb
git clone -b firmware-rgb https://github.com/meutedechien/macropad-mini-keyboard.git ~/macropad
cd ~/macropad && ./install.sh
```

`install.sh` crée l'environnement Python (hidapi, pyusb) et lance l'appli à chaque ouverture de
session, en arrière-plan : elle est nécessaire pour les actions Mac. La page se trouve sur
<http://localhost:8766>, ou double-clic sur `Macropad.command`.

## 2. Premier flash (une seule fois)

Le firmware d'origine ne sait pas passer en mode flash tout seul : il faut le forcer au démarrage.

1. Ouvrir le boîtier et repérer la **CH552G**. La broche 1 est marquée d'un point ; les broches se
   comptent dans le sens inverse des aiguilles d'une montre (1 à 8 sur une rangée, 9 à 16 sur l'autre).
2. **Souder une résistance de 10 kΩ entre la broche 10 (D+, P3.6) et la broche 12 (VCC, 5 V).** La
   broche 11 (masse) est entre les deux : la résistance doit l'enjamber sans la toucher. Ne jamais
   relier ces broches par un fil direct.
3. Brancher le clavier. Il apparaît alors comme bootloader USB `4348:55e0` : l'appli affiche
   « mode flash ».
4. Dans l'appli, cliquer **Mettre à jour le firmware**.
5. **Débrancher et dessouder la résistance.** Sinon le clavier redémarre en bootloader à chaque fois.

Sur certains exemplaires, relier la broche 3 (P1.5) à la masse au branchement suffit, ou D+ au 3,3 V
(broche 13) par 10 kΩ. Sur le nôtre, seul le 5 V a fonctionné.

## 3. Ensuite

- Tout se règle en direct dans l'appli ; **Enregistrer sur le clavier** garde les réglages.
- Les mises à jour du firmware se font en un clic. En secours, le clavier passe aussi en mode flash
  si on **maintient la touche 1 en le branchant**, ou **touche 1 puis appui sur la molette pendant 2 s**
  (LED blanches).

## Karabiner-Elements

Si Karabiner-Elements est installé, lui dire d'**ignorer ce clavier** (Karabiner → Devices). Sinon il
en prend le contrôle exclusif et l'appli ne peut plus lui parler.

## Compiler le firmware

```bash
brew install sdcc
cd firmware && make          # produit macropad_rgb.bin
```

`configure.py` écrit les réglages dans le binaire et le flashe (`--flash`), sans recompiler.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `server.py` | Serveur local : réglage en direct, enregistrement, flash, actions Mac |
| `live.py` | Canal HID de réglage (report 3, page 0xFF00) |
| `index.html` | L'interface |
| `install.sh` | Installation et lancement à l'ouverture de session |
| `firmware/macropad_rgb.c` | Le firmware |
| `firmware/configure.py` | Encode les réglages et flashe |
| `firmware/chprog.py` | Flasheur CH55x (Stefan Wagner, MIT) |
| `firmware/include/` | Bibliothèques CH55x de Stefan Wagner (CC BY-SA 3.0) |

## English summary

Custom firmware for the CH552G-based 3-key + knob macropad: per-key RGB colors and effects (idle and
pressed), live configuration over a vendor HID channel, settings stored in the chip's data flash,
macOS actions without Karabiner, interrupt-driven knob decoding, and one-click firmware updates. The
first flash needs the bootloader forced once: solder a 10 kΩ resistor between pin 10 (D+) and pin 12
(VCC 5 V), plug in, flash from the app, then remove the resistor. Use a USB-A to USB-C cable.

## Crédits et licences

Firmware basé sur le MacroPad Mini de [Stefan Wagner (wagiminator)](https://github.com/wagiminator),
via [biemster/3keys_1knob](https://github.com/biemster/3keys_1knob) : bibliothèques sous CC BY-SA 3.0.
Le reste du projet est sous licence MIT.
