# HUD / UX — best possible version (BOM-aware)

Hardware (bill of materials) that constrains the UX:
- XIAO ESP32-S3 Sense: dual-core 240 MHz, 8 MB PSRAM, OV2640 cam (QVGA),
  I2S mic (pads 40/41/42), BLE + WiFi. SPI on 1/2/7/8/9/10.
- Display, one of: ST7735 128x128 color (16 text rows), SSD1306 128x64 (8 rows),
  SSD1306 128x32 (4 rows). Input: scrollwheel (A=0,B=4) + 2 buttons (A=3,B=4**).
- **BUG**: PIN_BTN_B=4 == PIN_WHEEL_B=4 (both GPIO4). Confirm/cancel and wheel
  are aliased -> menu/back broken in hardware. Fix: move BTN_B to free GPIO 5.

## Plan
1. **Pin fix (hw)**: BTN_B -> GPIO5 in xiao/src/main.cpp. Wire BTN_B = confirm-no /
   back. Wake screen on any input.
2. **Word-aware wrap**: replace char-wrap in draw_detail with space-aware wrapping
   so agent answers don't split mid-word (huge on 128x32/64).
3. **Idle auto-sleep**: screen_off after `sleep_after` s of no input (OLED burn-in
   + power); any input wakes. tick_sec drives it.
4. **Agent progress + steps**: `progress` (0-100) bar + `add_step()` buffer; AGENT
   view shows thinking bar and streaming tool ticks (·device ·web) so the user
   sees the agent working, not a black screen.
5. **Glanceable HOME**: banner + clock + battery + unread-note count + REC flag.
6. **NAV arrow**: map heading deg -> arrow glyph (↑↗→↘↓↙←↖), pure text, BOM-free.
7. **Screen text_size()**: let ST7735 render a big banner; mono stays size 1.

## Premortem (what will break)
- *Pin still shared*: if BTN_B left at 4, holding confirm also spins wheel. FIXED
  by moving to 5 (verified free: SPI uses 1/2/7/8/9/10, mic 40/41/42).
- *PSRAM blow-up*: streaming DETAIL=1024 + steps[8][12] is ~1.1 KB. Safe.
- *OLED burn-in*: static "Cyclops ready" -> auto-sleep + content swap. Mitigated.
- *128x32 too tight for steps*: steps/bar only render when rows>=6; 4-row shows
  banner + first line only.
- *Word-wrap O(n) per render*: 1024 chars, trivial; no buffer needed.
- *Tests regress*: extend test_hud.cpp, keep host gate green before commit.

## Verification
- `make test` (g++ Hud logic) + `make proto` must pass.
- New tests: word-wrap, steps footer, idle sleep, nav arrow, pin independence.
- Keep lib/cyclops_shared/include/hud.h byte-identical (copied).
