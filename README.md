# Macropad — configurateur macOS pour le « MINI KeyBoard » (1189:8890)

Une petite application locale pour configurer les macropads USB chinois à 3 touches + molette
(VID `0x1189` / PID `0x8890`, puce CH57x) depuis un Mac, sans le logiciel Windows du fabricant.

*A local web app to configure the cheap 3-key + knob USB macropads (VID `0x1189` / PID `0x8890`,
CH57x) from macOS. Interface is in French; English notes below.*

## Ce que ça fait

- Assigner à chaque touche et à chaque sens de la molette : une frappe clavier (jusqu'à 5 frappes
  enchaînées avec Ctrl / Maj / Option / Cmd), une touche multimédia, un clic ou une molette de souris.
- Choisir le mode d'éclairage, avec un bouton « couleur au hasard » (voir plus bas).
- Tout est écrit dans la mémoire du clavier : il garde ses touches sur n'importe quel ordinateur.

## Installation

```bash
brew install ch57x-keyboard-tool       # ou : cargo install ch57x-keyboard-tool
git clone https://github.com/meutedechien/macropad-mini-keyboard.git ~/macropad
cd ~/macropad && python3 server.py
```

La page s'ouvre sur <http://localhost:8766>. Ensuite, un double-clic sur `Macropad.command` suffit.

Aucune dépendance Python : tout tient dans la bibliothèque standard.

Pour aller plus loin, comme ouvrir une application d'une touche, on peut ajouter
[Karabiner-Elements](https://karabiner-elements.pqrs.org/) : l'onglet « Action Mac » de l'appli s'en sert.

## Aller plus loin : couleurs RVB et réglage en direct (bricoleurs)

La puce du clavier (WCH CH552G) peut recevoir un autre firmware. Il donne une couleur RVB au choix et
un effet par touche (fixe, respiration, clignotement, arc-en-ciel…), le réglage en direct depuis
l'appli, et des touches qui ouvrent une application. Il faut ouvrir le boîtier et souder une résistance, et le
firmware d'origine est perdu définitivement. Tout est expliqué sur la branche
[`firmware-rgb`](https://github.com/meutedechien/macropad-mini-keyboard/tree/firmware-rgb).

## Ce qu'on a appris sur ce matériel

- **L'éclairage n'accepte aucune couleur.** Le protocole ne prévoit que `led <index>` :
  `0` éteint, `2` fait défiler les couleurs sur les trois touches, `1` fige la couleur du moment et
  la fait respirer. Les index suivants éteignent tout. Le codage `(couleur << 4) | mode` des modèles
  voisins (0x8840 / 0x8842) est refusé par ce firmware : vérifié à la webcam sur une trentaine de
  combinaisons d'octets. D'où le bouton « 🎲 Autre couleur », qui lance le défilement puis le fige
  après un délai aléatoire.
- **Une seule LED est allumée à la fois**, jamais les trois ensemble.
- **La prise USB-C du boîtier est souvent « fausse »** : sans les résistances de 5,1 kΩ sur CC1 et
  CC2, un câble USB-C → USB-C ne fournit aucun courant et le clavier reste invisible. Utiliser un
  câble USB-A → USB-C, ou souder les deux résistances.

## Fichiers

| Fichier | Rôle |
| --- | --- |
| `server.py` | Serveur local : écrit la config dans le clavier avec `ch57x-keyboard-tool` |
| `index.html` | L'interface |
| `Macropad.command` | Lanceur à double-cliquer |
| `led_raw.py` | Envoi de paquets USB bruts, utilisé pour explorer le protocole des LED (pyusb) |
| `snap/snap.swift` | Petit outil de capture webcam, utilisé pour observer les LED pendant les tests |

## English summary

This configures the generic AliExpress 3-key + knob macropad on macOS. It wraps
[`ch57x-keyboard-tool`](https://github.com/kriomant/ch57x-keyboard-tool) with a local web UI, and
can optionally use Karabiner-Elements for keys that launch apps or run commands. Findings about this firmware: LED colors cannot be set (only three
built-in modes), only one LED lights at a time, and the USB-C port frequently lacks its CC pull-down
resistors, so it needs a USB-A → USB-C cable.

## Licence

MIT. `ch57x-keyboard-tool` est un projet séparé, de Mikhail Trishchenkov.
