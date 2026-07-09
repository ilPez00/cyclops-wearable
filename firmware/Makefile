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
# Other screen/targets: swap xiao_st7735 for xiao_128x64 | xiao_128x32 |
# arduino_st7735 | arduino_128x64 | arduino_128x32.

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra
INC      := -I shared/include -I lib/cyclops_shared/include -I xiao/src

.PHONY: test proto native xiao flash monitor clean

test:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_hud.cpp -o /tmp/cyclops_test_hud
	/tmp/cyclops_test_hud

proto:
	$(CXX) $(CXXFLAGS) $(INC) shared/test_shared.cpp -o /tmp/cyclops_test_shared
	/tmp/cyclops_test_shared

native:
	pio run -e native_test

xiao:
	pio run -e xiao_st7735

flash:
	pio run -e xiao_st7735 -t upload

monitor:
	pio run -e xiao_st7735 -t monitor

clean:
	rm -f /tmp/cyclops_test_hud /tmp/cyclops_test_shared
	pio run -e native_test -t clean 2>/dev/null || true
