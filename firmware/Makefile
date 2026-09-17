# Firmware MacroPad RGB — CH552G (dérivé du Makefile de Stefan Wagner)
TARGET    = macropad_rgb
INCLUDE   = include
FREQ_SYS  = 16000000
XRAM_SIZE = 0x0300
XRAM_LOC  = 0x0100
CODE_SIZE = 0x3800

CFLAGS  = -mmcs51 --model-small --no-xinit-opt
CFLAGS += --xram-size $(XRAM_SIZE) --xram-loc $(XRAM_LOC) --code-size $(CODE_SIZE)
CFLAGS += -I$(INCLUDE) -DFREQ_SYS=$(FREQ_SYS)
CFILES  = $(TARGET).c $(wildcard $(INCLUDE)/*.c)
RFILES  = $(notdir $(CFILES:.c=.rel))

bin: $(TARGET).bin

%.rel: $(INCLUDE)/%.c
	@sdcc -c $(CFLAGS) $<
%.rel: %.c
	@sdcc -c $(CFLAGS) $<

$(TARGET).ihx: $(RFILES)
	@sdcc $(RFILES) $(CFLAGS) -o $(TARGET).ihx

$(TARGET).bin: $(TARGET).ihx
	@makebin -p $(TARGET).ihx $(TARGET).bin
	@echo "$(TARGET).bin : $$(wc -c < $(TARGET).bin) octets"
	@rm -f *.lk *.map *.mem *.lst *.rel *.rst *.sym *.asm *.adb *.ihx

clean:
	rm -f *.bin *.ihx *.lk *.map *.mem *.lst *.rel *.rst *.sym *.asm *.adb
