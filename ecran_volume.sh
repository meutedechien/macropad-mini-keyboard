#!/bin/bash
# Volume de l'écran en DDC : ecran_volume.sh up|down|mute
# L'écran (Samsung U28E590) ne sait pas renvoyer son volume : on garde la valeur dans un fichier.
M1DDC=/opt/homebrew/bin/m1ddc
STATE="$HOME/macropad/.volume_ecran"
STEP=4
read -r VOL MUTE < "$STATE" 2>/dev/null
VOL=${VOL:-30}; MUTE=${MUTE:-0}
# Numéro de l'écran externe (change selon ce qui est branché)
DISP=$($M1DDC display list | grep -v '(null)' | head -1 | sed -E 's/^\[([0-9]+)\].*/\1/')
[ -z "$DISP" ] && exit 1
case "$1" in
  up)   VOL=$((VOL + STEP)); MUTE=0 ;;
  down) VOL=$((VOL - STEP)) ;;
  mute) MUTE=$((1 - MUTE)) ;;
esac
((VOL > 100)) && VOL=100; ((VOL < 0)) && VOL=0
if [ "$1" = mute ] && [ "$MUTE" = 1 ]; then
  $M1DDC display "$DISP" set volume 0
else
  $M1DDC display "$DISP" set volume "$VOL"
fi
echo "$VOL $MUTE" > "$STATE"
