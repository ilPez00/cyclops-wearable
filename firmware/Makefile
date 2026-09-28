# Cyclops firmware — build / flash / test
#
# Host gate (no toolchain needed, runs anywhere with g++):
#   make test          -> compile + run the Hud state-machine logic test
#   make proto         -> compile + run the wire-protocol test
#
# Real builds (need PlatformIO: `pip install platformio` or `brew install platformio`):
#   make compile                     -> pio run -e xiao_128x32_i2c  (NO board needed)
#   make compile BOARD=feather       -> pio run -e feather_128x32_i2c (Feather ESP32-S3)
#   make flash                       -> same + -t upload (refuses early with no tty)
#   make dist                        -> compile + merge into one 0x0 image
#                                       (.pio/build/$(SCREEN)/cyclops-*.bin)
#   make xiao                        -> pio run -e $(SCREEN)
#   make monitor                     -> pio run -e $(SCREEN) -t monitor
#
# This box has no global `pio`, so compile/flash use the python3.13 PlatformIO
# under /mnt/faststore (PIO_PY/PIO_SITE/PIO_CORE) plus tools/pio_pathlib_shim.py.
# See docs/flash-xiao.md §1.
#
# Build flags (optional env vars):
#   ENABLE_RING=1  -> compile the COLMI R02 ring BLE client (off by default)
#   SCREEN=128x64  -> swap the display target (default xiao_st7735)
#
# All real-build targets are offline-safe: they print a clear message and
# exit non-zero when `pio` is missing, instead of failing cryptically.

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra
INC      := -I shared/include -I lib/cyclops_shared/include -I xiao/src

# Which pio environment to build. Override with SCREEN=... or BOARD=feather.
#   make compile                     -> xiao_128x32_i2c   (XIAO S3 Sense, default)
#   make compile BOARD=feather       -> feather_128x32_i2c (Adafruit Feather ESP32-S3)
SCREEN   ?= xiao_128x32_i2c
BOARD    ?= xiao
FLASH_SIZE ?= 8MB
ifeq ($(BOARD),feather)
  SCREEN := feather_128x32_i2c
  FLASH_SIZE := 4MB
endif
# Extra build flags forwarded to the compiler (e.g. -DENABLE_RING).
EXTRA_FLAGS ?=
ifeq ($(ENABLE_RING),1)
  EXTRA_FLAGS += -DENABLE_RING
endif
export PLATFORMIO_BUILD_FLAGS := $(EXTRA_FLAGS)

.PHONY: test proto native xiao flash compile dist monitor clean pio-check pio-flash

pio-check:
	@command -v pio >/dev/null 2>&1 || { \
	  echo "PlatformIO not found. Install: pip install platformio"; \
	  echo "Or see docs/flash-xiao.md for the full flashing guide."; \
	  exit 1; }

# ---- XIAO build/flash without a global `pio` on PATH ----
# This box has no `pio` shim, but PlatformIO 6.1.19 IS installed for python3.13
# at $(PIO_SITE) with its toolchain cache at $(PIO_CORE). The external
# site-packages dir ships an ancient pathlib-1.0.1 shim that shadows the real
# stdlib package on PYTHONPATH, so a re-export shim is prepended (see
# tools/pio_pathlib_shim.py). Override any of these if your box differs.
PIO_PY   ?= /usr/bin/python3.13
PIO_SITE ?= /mnt/faststore/home-gio-sync/.local/lib/python3.13/site-packages
PIO_CORE ?= /mnt/faststore/home-gio-sync/.platformio

pio-flash:
	@mkdir -p /tmp/cyclops-pio-shim
	@cp tools/pio_pathlib_shim.py /tmp/cyclops-pio-shim/pathlib.py
	@if ! ls /dev/ttyACM* /dev/ttyUSB* >/dev/null 2>&1; then \
	  echo "no XIAO on USB (/dev/ttyACM* /dev/ttyUSB* absent)."; \
	  echo "plug the board, then: make flash SCREEN=$(SCREEN)"; \
	  exit 2; \
	fi
	PLATFORMIO_CORE_DIR=$(PIO_CORE) \
	PYTHONPATH="/tmp/cyclops-pio-shim:$(PIO_SITE)" \
	$(PIO_PY) -m platformio run -e $(SCREEN) -t upload

test:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_hud.cpp -o /tmp/cyclops_test_hud
	/tmp/cyclops_test_hud

proto:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_shared.cpp -o /tmp/cyclops_test_shared
	/tmp/cyclops_test_shared
	$(CXX) $(CXXFLAGS) $(INC) shared/test_ota.cpp -o /tmp/cyclops_test_ota
	/tmp/cyclops_test_ota
	$(CXX) $(CXXFLAGS) $(INC) shared/test_adpcm.cpp -o /tmp/cyclops_test_adpcm
	/tmp/cyclops_test_adpcm
	$(CXX) $(CXXFLAGS) $(INC) shared/test_cycluno.cpp -o /tmp/cyclops_test_cycluno
	/tmp/cyclops_test_cycluno
	$(CXX) $(CXXFLAGS) $(INC) shared/test_vad.cpp -o /tmp/cyclops_test_vad
	/tmp/cyclops_test_vad
	$(CXX) $(CXXFLAGS) $(INC) shared/test_imu_whoami.cpp -o /tmp/cyclops_test_imu
	/tmp/cyclops_test_imu

ota:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_ota.cpp -o /tmp/cyclops_test_ota
	/tmp/cyclops_test_ota

native: pio-check
	pio run -e native_test

xiao: pio-check
	pio run -e $(SCREEN)

flash: pio-flash

# Compile only (no board needed) — same env as pio-flash, no USB requirement.
compile:
	@mkdir -p /tmp/cyclops-pio-shim
	@cp tools/pio_pathlib_shim.py /tmp/cyclops-pio-shim/pathlib.py
	PLATFORMIO_CORE_DIR=$(PIO_CORE) \
	PYTHONPATH="/tmp/cyclops-pio-shim:$(PIO_SITE)" \
	$(PIO_PY) -m platformio run -e $(SCREEN)

monitor: pio-check
	pio run -e $(SCREEN) -t monitor

# Single merged flash image (bootloader + partitions + boot_app0 + app) at 0x0.
# Drop-in for ESP Web Tools / esptool — useful when the board is on a machine
# without PlatformIO. Writes .pio/build/$(SCREEN)/cyclops-$(BOARD).bin.
#
# Board difference: the XIAO is a plain ESP32-S3 (PlatformIO emits bootloader +
# the 8MB partition table, so everything merges). The Adafruit Feather ships
# Adafruit's TinyUF2 bootloader in flash and PlatformIO deliberately does not
# regenerate it — there is nothing to merge, so `dist` copies the app image and
# the flashing path is UF2 (double-tap RESET -> copy firmware.bin to the drive)
# or `make flash`. Same rule on the serial side either way.
dist: compile
	@mkdir -p /tmp/cyclops-pio-shim
	@cp tools/pio_pathlib_shim.py /tmp/cyclops-pio-shim/pathlib.py
ifeq ($(BOARD),feather)
	@cp .pio/build/$(SCREEN)/firmware.bin .pio/build/$(SCREEN)/cyclops-$(BOARD).bin
	@ls -l .pio/build/$(SCREEN)/cyclops-$(BOARD).bin
	@echo "Feather: UF2 board (TinyUF2 in flash, not regenerated). Copy this file"
	@echo "onto the FTHRS3BOOT drive after a double-tap of RESET."
else
	PYTHONPATH="/tmp/cyclops-pio-shim:$(PIO_SITE)" $(PIO_PY) $(PIO_CORE)/packages/tool-esptoolpy/esptool.py \
	  --chip esp32s3 merge_bin \
	  -o .pio/build/$(SCREEN)/cyclops-$(BOARD).bin \
	  --flash_mode qio --flash_freq 80m --flash_size $(FLASH_SIZE) \
	  0x0 .pio/build/$(SCREEN)/bootloader.bin \
	  0x8000 .pio/build/$(SCREEN)/partitions.bin \
	  0xe000 $(PIO_CORE)/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin \
	  0x10000 .pio/build/$(SCREEN)/firmware.bin
	@ls -l .pio/build/$(SCREEN)/cyclops-$(BOARD).bin
endif

clean:
	rm -f /tmp/cyclops_test_hud /tmp/cyclops_test_shared /tmp/cyclops_test_ota /tmp/cyclops_test_adpcm /tmp/cyclops_test_vad /tmp/cyclops_test_config_store
	pio run -e native_test -t clean 2>/dev/null || true
