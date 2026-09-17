// ===================================================================================
// Firmware « MacroPad RGB » pour le macropad 3 touches + molette (CH552G)
// ===================================================================================
//
// Basé sur le firmware MacroPad Mini de Stefan Wagner (wagiminator, CC BY-SA 3.0),
// via https://github.com/biemster/3keys_1knob.
//
// Ce qui change :
// - chaque touche et chaque sens de la molette envoie une touche clavier (avec
//   modificateurs) ou une touche multimédia, maintenue tant que la touche l'est ;
// - chaque LED a sa couleur RVB et son mode d'éclairage ;
// - les réglages se modifient en direct par un canal HID constructeur (report 3)
//   et s'enregistrent dans la mémoire de données de la puce ; sans réglages
//   enregistrés, le bloc CFG (repéré par « MPCF ») sert de valeurs par défaut.
//
// Bootloader (LED blanches) : maintenir la touche 1 + appuyer sur la molette pendant
// 2 secondes, ou maintenir la touche 1 en branchant le câble USB.

#include <config.h>
#include <system.h>
#include <delay.h>
#include <neo.h>
#include <usb_hid.h>
#include <usb_conkbd.h>
#include <usb_handler.h>

void USB_interrupt(void);
void USB_ISR(void) __interrupt(INT_NO_USB) {
  USB_interrupt();
}

// ===================================================================================
// Configuration par défaut (réécrite par configure.py)
// ===================================================================================
//
// Entrées 0..5 = touche 1, touche 2, touche 3, molette gauche, molette appui,
// molette droite. Chacune : type, modificateurs HID, code (poids faible, poids fort).
// Types : 0 rien
//         1 touche clavier (avec modificateurs), maintenue tant que la touche l'est
//         2 touche multimédia
//         3 double appui sur les modificateurs (ex. Option Option)
//         4 action Mac : prévient l'appli, qui fait l'action
//         5 action Mac puis touche clavier maintenue 250 ms plus tard
// LED 0..2, deux états chacune (repos, appui) : effet, rouge, vert, bleu.
// Effets : 0 éteinte, 1 fixe, 2 respiration, 3 clignote, 4 flash (plein feu puis
//          fondu), 5 arc-en-ciel, 6 comme au repos (appui seulement).
// Puis luminosité maximale (0..255) et vitesse des effets (1..10).

#define CFG_INPUTS    5
#define CFG_LEDS      29
#define CFG_BRIGHT    53
#define CFG_SPEED     54

__code uint8_t CFG[55] = {
  'M','P','C','F', 3,
  1, 0x00, 0x1E, 0x00,                      // touche 1 : 1
  1, 0x00, 0x1F, 0x00,                      // touche 2 : 2
  1, 0x00, 0x20, 0x00,                      // touche 3 : 3
  2, 0x00, 0xEA, 0x00,                      // molette gauche : volume -
  2, 0x00, 0xE2, 0x00,                      // molette appui : muet
  2, 0x00, 0xE9, 0x00,                      // molette droite : volume +
  1, 255, 32, 0,    1, 255, 32, 0,          // LED 1 : rouge-orangé fixe
  1,   0, 64, 255,  1,   0, 64, 255,        // LED 2 : bleu fixe
  1,  0, 200, 60,  3,   0, 200, 60,        // LED 3 : vert fixe, clignote à l'appui
  90, 5                                     // luminosité, vitesse
};

#define CFG_SIZE      55
__xdata uint8_t cfg[CFG_SIZE];              // réglages en cours (mémoire vive)

// Mémoire de données (d'après ch55xduino, Deqing Sun)
uint8_t EEPROM_read(uint8_t addr) {
  ROM_ADDR_H = DATA_FLASH_ADDR >> 8;
  ROM_ADDR_L = addr << 1;
  ROM_CTRL = ROM_CMD_READ;
  return ROM_DATA_L;
}

void EEPROM_write(uint8_t addr, uint8_t val) {
  SAFE_MOD = 0x55; SAFE_MOD = 0xAA;
  GLOBAL_CFG |= bDATA_WE;
  SAFE_MOD = 0;
  ROM_ADDR_H = DATA_FLASH_ADDR >> 8;
  ROM_ADDR_L = addr << 1;
  ROM_DATA_L = val;
  if(ROM_STATUS & bROM_ADDR_OK) ROM_CTRL = ROM_CMD_WRITE;
  SAFE_MOD = 0x55; SAFE_MOD = 0xAA;
  GLOBAL_CFG &= ~bDATA_WE;
  SAFE_MOD = 0;
}

// Réglages enregistrés s'ils existent, sinon valeurs par défaut du firmware
void CFG_load(void) {
  uint8_t i;
  for(i = 0; i < CFG_SIZE; i++) cfg[i] = CFG[i];
  if(EEPROM_read(0) == 'M' && EEPROM_read(1) == 'P' && EEPROM_read(2) == 'C' &&
     EEPROM_read(3) == 'F' && EEPROM_read(4) == 3)
    for(i = 0; i < CFG_SIZE; i++) cfg[i] = EEPROM_read(i);
}

// ===================================================================================
// Envoi des touches
// ===================================================================================

__xdata uint8_t RPT_kbd[9] = {1,0,0,0,0,0,0,0,0};
__xdata uint8_t RPT_con[9] = {2,0,0,0,0,0,0,0,0};

__xdata uint8_t RPT_host[16] = {3,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
__idata uint8_t keyDelay[6];                // type 5 : ticks avant d'appuyer la touche
__idata uint8_t keyHeld = 0;                // type 5 : touche clavier déjà appuyée (bits)

void KBD_send(uint8_t mods, uint8_t code) {
  RPT_kbd[1] = mods;
  RPT_kbd[3] = code;
  HID_sendReport(RPT_kbd, sizeof(RPT_kbd));
}

// Prévient l'appli sur le canal constructeur : [3, 1, entrée, appuyé]
void HOST_send(uint8_t n, uint8_t pressed) {
  RPT_host[2] = n;
  RPT_host[3] = pressed;
  HID_sendReport(RPT_host, sizeof(RPT_host));
}

void INPUT_send(uint8_t n, uint8_t pressed) {
  uint8_t base = CFG_INPUTS + (n << 2);
  uint8_t type = cfg[base];
  if(type == 1) {
    KBD_send(pressed ? cfg[base + 1] : 0, pressed ? cfg[base + 2] : 0);
  }
  else if(type == 2) {
    RPT_con[1] = pressed ? cfg[base + 2] : 0;
    RPT_con[2] = pressed ? cfg[base + 3] : 0;
    HID_sendReport(RPT_con, sizeof(RPT_con));
  }
  else if(type == 3 && pressed) {
    KBD_send(cfg[base + 1], 0); DLY_ms(40); KBD_send(0, 0); DLY_ms(80);
    KBD_send(cfg[base + 1], 0); DLY_ms(40); KBD_send(0, 0);
    WDT_reset();
  }
  else if(type == 4) {
    HOST_send(n, pressed);
  }
  else if(type == 5) {
    HOST_send(n, pressed);
    if(pressed) keyDelay[n] = 50;           // 50 x 5 ms
    else {
      keyDelay[n] = 0;
      if((keyHeld >> n) & 1) { keyHeld &= ~(1 << n); KBD_send(0, 0); }
    }
  }
}

// Appelé toutes les 5 ms : appuie la touche des entrées de type 5 arrivées à échéance
void INPUT_tick(void) {
  uint8_t n, base;
  for(n = 0; n < 6; n++) {
    if(keyDelay[n] && !--keyDelay[n]) {
      base = CFG_INPUTS + (n << 2);
      keyHeld |= 1 << n;
      KBD_send(cfg[base + 1], cfg[base + 2]);
    }
  }
}

// ===================================================================================
// LED
// ===================================================================================

__idata uint8_t breath = 0;                 // phase de la respiration (0..255)
__idata uint8_t breathUp = 1;
__idata uint8_t blinkTick = 0;              // compteur du clignotement
__idata uint8_t blinkOn = 1;
__idata uint8_t hue = 0;                    // teinte de l'arc-en-ciel
__idata uint8_t flash[3];                   // niveau du flash de chaque LED
__idata uint8_t pressedMask = 0;            // touches enfoncées (bits 0..2)
__idata uint8_t previewMask = 0;            // aperçu de l'état « appui » demandé par l'appli

uint8_t scale(uint8_t c, uint8_t lvl) {
  uint16_t v = ((uint16_t)c * lvl) >> 8;
  return ((uint16_t)v * cfg[CFG_BRIGHT]) >> 8;
}

// Fait avancer les animations d'un pas (toutes les 5 ms)
void LED_tick(void) {
  uint8_t i, speed = cfg[CFG_SPEED] ? cfg[CFG_SPEED] : 1;
  if(breathUp) { if(breath >= 255 - speed) breathUp = 0; else breath += speed; }
  else         { if(breath <= speed)       breathUp = 1; else breath -= speed; }
  if(++blinkTick >= 60 / speed + 3) { blinkTick = 0; blinkOn = !blinkOn; }
  hue += (speed + 1) >> 1;
  for(i = 0; i < 3; i++) flash[i] = flash[i] > speed ? flash[i] - speed : 0;
}

// Couleur d'une LED selon son effet, écrite directement sur les NeoPixels
void LED_write(uint8_t i) {
  uint8_t base = CFG_LEDS + (i << 3);
  uint8_t r, g, b, lvl = 255, h, x;
  if(((pressedMask >> i) & 1) && cfg[base + 4] != 6) base += 4;
  r = cfg[base + 1]; g = cfg[base + 2]; b = cfg[base + 3];
  switch(cfg[base]) {
    case 1: break;
    case 2: lvl = breath < 16 ? 16 : breath; break;
    case 3: lvl = blinkOn ? 255 : 0; break;
    case 4: lvl = flash[i]; break;
    case 5:                                 // roue des couleurs, décalée par touche
      h = hue + i * 85; x = (h % 85) * 3;
      if(h < 85)       { r = 255 - x; g = x;       b = 0; }
      else if(h < 170) { r = 0;       g = 255 - x; b = x; }
      else             { r = x;       g = 0;       b = 255 - x; }
      break;
    default: lvl = 0;
  }
  NEO_writeColor(scale(r, lvl), scale(g, lvl), scale(b, lvl));
}

void LED_show(void) {
  EA = 0;
  LED_write(0); LED_write(1); LED_write(2);
  EA = 1;
}

// ===================================================================================
// Molette : décodage en quadrature sous interruption (toutes les 0,5 ms)
// ===================================================================================
//
// État = (A << 1) | B. Chaque transition valide compte +1 dans un sens et -1 dans
// l'autre ; les transitions impossibles (rebonds) comptent 0. Les crans sont comptés à
// l'arrivée sur une position de repos : 3 pour les codeurs à un cycle complet par cran,
// 3 et 0 pour ceux à un demi-cycle par cran (détectés quand la molette reste sur 0).
// La lecture sous interruption ne dépend plus des LED ni de l'USB : aucun cran perdu.

__code int8_t ENC_table[16] = {0,-1,1,0, 1,0,0,-1, -1,0,0,1, 0,1,-1,0};
__idata uint8_t encState = 3;
__idata int8_t encCount = 0;
__idata uint8_t encStable = 0;              // temps passé dans l'état actuel (x 0,5 ms)
__idata uint8_t encHalf = 0;                // 1 = codeur à demi-cycle par cran
__idata int8_t encSteps = 0;                // crans en attente d'envoi (+ droite, - gauche)

#define TMR0_RELOAD  (65536 - (FREQ_SYS / 12 / 2000))

void TMR0_ISR(void) __interrupt(INT_NO_TMR0) {
  uint8_t cur, shift;
  int8_t steps;
  TH0 = TMR0_RELOAD >> 8;
  TL0 = TMR0_RELOAD & 0xFF;
  cur = (PIN_read(PIN_ENC_A) ? 2 : 0) | (PIN_read(PIN_ENC_B) ? 1 : 0);
  if(cur == encState) {
    if(encStable < 255) encStable++;
    if(cur == 0 && encStable == 60) encHalf = 1;    // 30 ms arrêté à mi-cycle
    return;
  }
  encCount += ENC_table[(encState << 2) | cur];
  encState = cur;
  encStable = 0;
  if(cur == 3 || (cur == 0 && encHalf)) {
    shift = encHalf ? 1 : 2;                // pas de division : routines non réentrantes
    if(encCount > 0)      steps = (encCount + (1 << (shift - 1))) >> shift;
    else if(encCount < 0) steps = -((-encCount + (1 << (shift - 1))) >> shift);
    else                  steps = 0;
    encCount = 0;
    steps += encSteps;
    encSteps = steps > 20 ? 20 : (steps < -20 ? -20 : steps);
  }
}

void ENC_init(void) {
  TMOD = (TMOD & 0xF0) | 0x01;              // timer 0, 16 bits
  TH0 = TMR0_RELOAD >> 8;
  TL0 = TMR0_RELOAD & 0xFF;
  ET0 = 1;
  TR0 = 1;
}

// Renvoie 5 (droite), 3 (gauche) ou 0, un cran à la fois
uint8_t ENC_read(void) {
  uint8_t result = 0;
  EA = 0;
  if(encSteps > 0)      { encSteps--; result = 5; }
  else if(encSteps < 0) { encSteps++; result = 3; }
  EA = 1;
  return result;
}

// ===================================================================================
// Passage en bootloader sans débrancher
// ===================================================================================

void BOOT_fromRunning(void) {
  uint8_t i;
  EA = 0;
  NEO_latch();
  for(i = 9; i; i--) NEO_sendByte(60);      // LED blanches
  WDT_stop();                               // sinon le chien de garde relance le firmware
  TR0 = 0; ET0 = 0;
  USB_INT_EN = 0;
  USB_CTRL = 0x06;                          // coupe l'USB : l'ordinateur voit un débranchement
  UDEV_CTRL = 0;
  EA = 1;
  DLY_ms(200);
  EA = 0;
  BOOT_now();
}

// ===================================================================================
// Commandes reçues de l'appli (report 3, 15 octets)
// ===================================================================================
//   1 réglage : [1, position, longueur (<= 12), octets...]
//   2 enregistrer dans la mémoire de données
//   3 passer en bootloader
//   4 aperçu de l'appui : [4, masque des touches]

__xdata uint8_t cmdBuf[16];
__idata uint8_t cmdReady = 0;

void CMD_receive(uint8_t len) {             // appelé sous interruption
  uint8_t i;
  if(len < 2 || EP2_buffer[0] != 3) return;
  for(i = 0; i < 16; i++) cmdBuf[i] = EP2_buffer[i];
  cmdReady = 1;
}

void CMD_process(void) {
  uint8_t i, pos, n;
  cmdReady = 0;
  switch(cmdBuf[1]) {
    case 1:
      pos = cmdBuf[2]; n = cmdBuf[3] > 12 ? 12 : cmdBuf[3];
      for(i = 0; i < n; i++) if(pos + i < CFG_SIZE && pos + i > 4) cfg[pos + i] = cmdBuf[4 + i];
      break;
    case 2:
      for(i = 0; i < CFG_SIZE; i++) if(EEPROM_read(i) != cfg[i]) EEPROM_write(i, cfg[i]);
      break;
    case 3:
      BOOT_fromRunning();
      break;
    case 4:
      previewMask = cmdBuf[2] & 7;
      break;
  }
}

// ===================================================================================
// Boucle principale
// ===================================================================================

void main(void) {
  uint8_t last = 0;                         // bits 0..2 : touches, bit 3 : molette
  uint8_t now;
  __idata uint8_t i;
  uint8_t turned;                           // 3 = gauche, 5 = droite, 0 = rien
  uint8_t tick = 0, ledTick = 0;                         // la molette est lue toutes les 1 ms,
                                            // le reste toutes les 5 ms
  uint16_t comboTicks = 0;                  // durée de la combinaison touche 1 + molette
  uint8_t comboKnob = 0;                    // appui molette commencé touche 1 tenue

  NEO_init();
  if(!PIN_read(PIN_KEY1)) {                 // touche 1 au branchement : bootloader
    NEO_latch();
    for(i = 9; i; i--) NEO_sendByte(127);
    BOOT_now();
  }

  CLK_config();
  DLY_ms(5);
  CFG_load();
  HID_init();
  ENC_init();
  WDT_start();

  while(1) {
    if(cmdReady) CMD_process();
    // Rotation : lue à chaque milliseconde, un appui-relâché par cran
    turned = ENC_read();
    if(turned) {
      INPUT_send(turned, 1);
      INPUT_send(turned, 0);
    }
    DLY_ms(1);
    WDT_reset();
    if(++tick < 5) continue;
    tick = 0;

    // Touches 1..3
    for(i = 0; i < 3; i++) {
      if(i == 0)      now = !PIN_read(PIN_KEY1);
      else if(i == 1) now = !PIN_read(PIN_KEY2);
      else            now = !PIN_read(PIN_KEY3);
      if(now != ((last >> i) & 1)) {
        last ^= (1 << i);
        INPUT_send(i, now);
        if(now) flash[i] = 255;
      }
    }
    pressedMask = (last & 7) | previewMask;

    // Touche 1 + appui molette pendant 2 s : bootloader
    if((last & 9) == 9) { if(++comboTicks >= 400) BOOT_fromRunning(); }
    else comboTicks = 0;

    // Appui sur la molette
    // (ignoré pendant que la touche 1 est tenue : c'est la combinaison bootloader)
    now = !PIN_read(PIN_ENC_SW);
    if(now != ((last >> 3) & 1)) {
      last ^= 8;
      if(now && (last & 1)) comboKnob = 1;
      if(!comboKnob) INPUT_send(4, now);
      if(!now) comboKnob = 0;
    }

    INPUT_tick();
    LED_tick();
    if(++ledTick >= 4) { ledTick = 0; LED_show(); }
  }
}
