# Cyclops — 1.51" Transparent OLED variant

A see-through HUD variant using the **Waveshare 1.51" Transparent OLED**
(128×64, **SSD1309** controller, 4-wire SPI/I2C). Lit pixels glow; unlit pixels
are fully transparent glass — ideal for a heads-up "floating text" look where the
wearer sees the world through the display.

## Why it just works
SSD1309 is command-compatible with the SSD1306 the firmware already drives, so it
reuses the `Adafruit_SSD1306` library unchanged. The only meaningful differences:

- **External VCC boost** (not the on-chip charge pump) → `begin(SSD1306_EXTERNALVCC, 0x3C)`.
- **Transparent rendering**: a filled "off" rectangle would punch a visible black
  hole on clear glass, so `draw_rect(..., on=false)` is a no-op — unlit areas stay
  transparent. Only lit pixels/rects/text are drawn.
- Panel is dim in daylight → `dim(false)` for max brightness at boot.

Geometry is 128×64 (21 cols × 8 text rows), same layout budget as `SCREEN_128x64`.

## Wiring (4-wire SPI, XIAO ESP32-S3)
| OLED | XIAO | GPIO |
|------|------|------|
| VCC  | 3V3  | —    |
| GND  | GND  | —    |
| DIN/MOSI | D10 | 9 |
| CLK/SCK  | D8  | 7 |
| CS   | D5   | 6 |
| DC   | D1   | 2 |
| RST  | D0   | 1 |

Module ships configured for SPI by default; for I2C move the two solder resistors
per the Waveshare wiki (addr 0x3C) — the SSD1306 I2C driver pattern
(`SCREEN_128x32_I2C`) can be adapted the same way if you prefer 2-wire.

## Build / flash
```
cd firmware && pio run -e xiao_transparent_151
pio run -e xiao_transparent_151 -t upload
```
Boot serial prints `[boot] screen=Transparent 1.51in SSD1309 128x64`.

## Files
- `firmware/lib/cyclops_shared/include/screens.h` — `Transparent151Screen` (SCREEN_TRANSPARENT_151)
- `firmware/xiao/src/main.cpp` — screen instance + boot log
- `firmware/platformio.ini` — `[env:xiao_transparent_151]`
