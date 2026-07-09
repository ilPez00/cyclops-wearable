# Cyclops firmware — build / flash / test
#
# Host gate (no toolchain needed, runs anywhere with g++):
#   make test          -> compile + run the Hud state-machine logic test
#   make proto         -> compile + run the wire-protocol test
#
# Real builds (need PlatformIO: `pip install platformio` or `brew install platformio`):
#   make native        -> pio run -e native_test   (logic, host)
#   make xiao          -> pio run -e xiao_st7735   (XIAO + ST7735 screen)
#   make flash         -> pio run -e xiao_st7735 -t upload
#   make monitor       -> pio run -e xiao_st7735 -t monitor
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

# Which pio environment to build. Override with SCREEN=...
SCREEN   ?= xiao_st7735
# Extra build flags forwarded to the compiler (e.g. -DENABLE_RING).
EXTRA_FLAGS ?=
ifeq ($(ENABLE_RING),1)
  EXTRA_FLAGS += -DENABLE_RING
endif
export PLATFORMIO_BUILD_FLAGS := $(EXTRA_FLAGS)

.PHONY: test proto native xiao flash monitor clean pio-check

pio-check:
	@command -v pio >/dev/null 2>&1 || { \
	  echo "PlatformIO not found. Install: pip install platformio"; \
	  echo "Or see docs/flash-xiao.md for the full flashing guide."; \
	  exit 1; }

test:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_hud.cpp -o /tmp/cyclops_test_hud
	/tmp/cyclops_test_hud

proto:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_shared.cpp -o /tmp/cyclops_test_shared
	/tmp/cyclops_test_shared

native: pio-check
	pio run -e native_test

xiao: pio-check
	pio run -e $(SCREEN)

flash: pio-check
	pio run -e $(SCREEN) -t upload

monitor: pio-check
	pio run -e $(SCREEN) -t monitor

clean:
	rm -f /tmp/cyclops_test_hud /tmp/cyclops_test_shared
	pio run -e native_test -t clean 2>/dev/null || true
