# Cyclops — Optics (displays & light path)

> **RECONSTRUCTED DOC** — original `docs/14-optics.md` (2026-07-04) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `firmware/xiao/src/main.cpp`, `docs/01-hardware.md`, `docs/22-screens-plan.md`,
> `docs/21-architecture-v2.md` (G2 glasses), `docs/07-features-omi-g2.md`.
> **[inferred]** = reconstructed. Optics here = the *display* choices + the
> G2 glanceable HUD light-path; no camera optics in scope (OV2640 cam is
> mentioned but not detailed).

## 0. What "optics" covers

Cyclops has **two display classes**:
1. **On-device OLED** (XIAO-attached): ST7735 / SSD1306 — what the wearer
   glances at on the wearable itself.
2. **Glasses HUD** (EvenRealities G2): a tiny projector/ waveguide that paints
   text into the wearer's peripheral vision.

Both are *output only* — Cyclops does not do camera-vision optics on the
wearable (vision is a tool, off-device).

## 1. On-device OLED panels

| Panel | Res | Type | Driver | XIAO CS | View |
|-------|-----|------|--------|----------|------|
| ST7735 | 128×128 | RGB565 color | `St7735Screen` | D7 | clearest, 16 text rows |
| SSD1306 | 128×64 | 1bpp mono | `Ssd1306_128x64_Screen` | D6 | compact, 8 rows |
| SSD1306 | 128×32 | 1bpp mono | `Ssd1306_128x32_Screen` | D5 | glanceable-only, 4 rows |

- SPI: `SCK=D8 MOSI=D10 MISO=D9` (VSPI). DC=D2, RST=D1 shared.
- Mono: white-on-black. ST7735: green-on-black; selected row inverted.
- No full framebuffer needed — Adafruit draws direct; 128×64=1 KB, 128×32=
  512 B controller RAM (fits Uno 2 KB). Decoder buffer 1024→256 for Uno.
- Resolution-agnostic: `Screen` base exposes `char_cols()`/`text_rows()`;
  `Hud::render` lays out header + note list + status per panel geometry.

## 2. G2 glasses HUD (light path)

EvenRealities G2 ≈ **640×200** effective — about **4 short lines** of text in
the wearer's lower vision. Cyclops drives it via BLE `HUD_FRAME` (premortem #4):

- `lines` max 4 strings, each ≤ 18 chars.
- `teleprompter`: phone streams one line at a time; glasses auto-scroll slow.
- Never raw transcript — only extracted/summarized text.
- Frames tiny (< 20 B payload) to survive classic BLE (premortem #1).

The G2 sink (`G2Transport` + `G2HudSink` in `device/` / brain) builds the
`HUD_FRAME` and chunkes it to the G2 BLE characteristic (MTU-sized).

## 3. Readability rules (premortem #4)

- Strict truncation + pagination: one note at a time + "more" cue.
- Word-aware wrap (not char-wrap) so answers don't split mid-word (huge on
  128×32/64). Implemented in `draw_detail` (HUD/UX doc).
- NAV arrow: map heading deg → glyph (↑↗→↘↓↙←↖), pure text, BOM-free.

## 4. Brightness / power

- OLED: screen-off after `sleep_after` s idle (burn-in + power); any input
  wakes. `text_size()` lets ST7735 render a big banner; mono stays size 1.
- G2: brightness is glasses-side; Cyclops only controls content + cadence.

## 5. Not in scope / pending

- **Camera optics:** OV2640 (QVGA) on XIAO is wired but Cyclops uses it
  only as a future capture source; no lens/FOV docs here.
- **Vibration motor:** haptic confirm (a tactile, not optical, channel).
- **Live G2 render test:** headless-unverifiable (needs glasses).

---
**[inferred]** The panel table, SPI pins, RAM figures, the G2 640×200 / 4-line
constraint, the `HUD_FRAME` rules and the premortem #4 wrap rule are all
grounded in committed `main.cpp` + `22-screens-plan.md` + `21-architecture-v2.md`
+ `20-premortem-integration.md` and should be accurate. Inferred only: the §0/§2
"optics" framing, the G2 "projector/waveguide" description (a reasonable guess
at G2's mechanism), and any camera-lens detail (explicitly out of scope here).
