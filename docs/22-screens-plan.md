# Cyclops — Screen Support Plan (v3)

## Goal
Both MCUs (XIAO ESP32-S3 Sense, Arduino Uno/Nano) must work with ANY of three
panels, selected at compile time:
  1. ST7735  (128x128, RGB565, SPI)        — "clear color" option
  2. SSD1306 SPI 128x64 (1bpp, SPI)        — "clear mono" option
  3. SSD1306 SPI 128x32 (1bpp, SPI)        — compact HUD

## Design
- `Screen` abstract base (shared/include/screen.h): resolution-agnostic. Exposes
  char_cols()/text_rows(), draw_text(col,row,str), draw_rect, set_ink, clear,
  flush, and a default render(const UiState&) that lays out header + note list +
  status (rec dot, batt) using the panel's own geometry. Color panels map ink to
  green-on-black; mono panels to white-on-black.
- `UiState` gains read accessors (note_count, note(i), sel, view_top, batt_mv,
  charging, bt, hr, clock, screen_on) so drivers pull data; no fixed 4x22 buffer
  forced on large panels.
- Three header-only drivers wrap Adafruit libraries and implement `Screen`:
  St7735Screen, Ssd1306_128x64_Screen, Ssd1306_128x32_Screen.
- MCU mains pick the driver via -DSCREEN_ST7735 | -DSCREEN_128x64 | -DSCREEN_128x32.
- Shared lib made header-only (inline impl) to remove the AVR link duplication.

## Pin maps (only the selected screen's pins are compiled in)
### XIAO ESP32-S3 Sense (3.3V, VSPI: SCK=D8 MOSI=D10 MISO=D9)
  ST7735:        CS=D7  DC=D2  RST=D1
  128x64 SPI:     CS=D6  DC=D2  RST=D1
  128x32 SPI:     CS=D5  DC=D2  RST=D1
  Wheel A=D0 B=D4 BTN=D3 ; BTN_A=D3 BTN_B=D4 (reassigned to avoid DC)

### Arduino Uno/Nano (5V, SPI: SCK=13 MOSI=11 MISO=12)
  ST7735:        CS=10 DC=9  RST=8
  128x64 SPI:     CS=7  DC=6  RST=5
  128x32 SPI:     CS=4  DC=3  RST=2
  Wheel A=2(INT0) B=3(INT1) BTN=4 ; BTN_A=5 BTN_B=6 (share w/ screen RST ok:
  RST tied to board RESET or pulled high)

## Build matrix (platformio.ini)
  arduino_st7735, arduino_128x64, arduino_128x32,
  xiao_st7735,    xiao_128x64,    xiao_128x32
Each = CYCLOPS_ARDUINO|XIAO + SCREEN_* + include path.

## Verification
  - Native host test: fake Screen captures draw_text calls; assert header +
    note lines + status render for 4x22, 21x8 (128x64@1px?), 21x4 (128x32).
  - pio run each of the 6 envs; XIAO already green; Arduino must link (header-only
    fixes the prior ld error).
  - Memory check: Uno + ST7735 128x128 uses no full framebuffer (Adafruit draws
    direct); 128x64=1KB, 128x32=512B controller RAM — all fit 2KB.

## Out of scope (next pass)
  Per-target fonts/scaling, status bar clock/BT/HR display, detail/health screens.
  This pass = make all 3 panels render the existing UI on both MCUs.

## RESULT (verified)
All 6 firmware envs + native_test COMPILE/LINK. Header-only shared lib removed
the AVR link duplication (prior ld error gone). Decoder buffer shrunk 1024->256
to fit Uno RAM.

| env              | RAM       | Flash     | status  |
|------------------|-----------|-----------|---------|
| arduino_st7735   | 59.3%     | 55.5%     | OK      |
| arduino_128x64   | 67.9%     | 62.8%     | OK      |
| arduino_128x32   | 67.9%     | 62.8%     | OK      |
| xiao_st7735      | 9.3%      | 15.8%     | OK      |
| xiao_128x64      | 9.4%      | 16.2%     | OK      |
| xiao_128x32      | 9.4%      | 16.2%     | OK      |

Python suite: 16 passed. Native pio test: passed.

## Pin maps used (verified by compile)
Arduino Uno/Nano (SPI 13/11/12):
  ST7735 cs10 dc9 rst8 | 128x64 cs7 dc6 rst5 | 128x32 cs4 dc3 rst2
  wheel A2 B3 btn4 ; btnA5 btnB6 ; joy A1/A2/7 ; prox A0 ; vbat A6
XIAO ESP32-S3 (SPI 8/10/9):
  ST7735 cs7 dc2 rst1 | 128x64 cs6 dc2 rst1 | 128x32 cs5 dc2 rst1
  wheel A0 B4 ; btnA3 btnB4(shared w/ wheel B — reassign if conflict)
