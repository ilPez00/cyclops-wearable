# Cyclops — Hardware Bring-up

> **RECONSTRUCTED DOC** — original `docs/08-bringup.md` (2026-07-06) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `firmware/xiao/src/main.cpp`, `docs/01-hardware.md`, `docs/30-colmi-r02-integration.md`,
> `docs/03-hud-ux-plan.md`, `PLAN.md` (Next: hardware). **[inferred]** = guessed.
> Bring-up = the on-metal steps the headless build can't do.

## 0. What "bring-up" means here

The whole stack is **offline-verified** (firmware logic via `make test`, brain
via 115 Python tests, Android via `:core:test`). What remains is *physical*:
flash the XIAO, wire the I2S mic + OLED, connect real BLE peers, and field-test.
This doc is the bench checklist.

## 1. Toolchain

- **PlatformIO** (`platformio.ini`): `pio run -e xiao_st7735` (or `_128x64`
  / `_128x32`) to build + flash; `pio run -e native_test` for the host gate.
  (PlatformIO not installed locally — CI compiles `xiao_*`.)
- **Arduino IDE / CLI** optional for the Uno/Nano bench target.
- **esptool / UF2** for the XIAO if flashing over USB-C directly.
- **bleak** (Python) on the phone/PC for ring + G2 bridging without the XIAO.

## 2. Flash the XIAO

1. `pio run -e xiao_128x32` (Mini) or `xiao_st7735` (dev).
2. Connect XIAO over USB-C; `pio run -e <env> -t upload`.
3. Open serial @ 115200; expect the `CyclopsXIAO` NimBLE server to advertise.
4. With `-DENABLE_RING`, `ring.begin("R02_")` scans for the COLMI R02 on boot.

## 3. Wire I2S mic (onboard pads)

The XIAO S3 has an **onboard MEMS mic** — no external wiring for audio:
`MIC_BCLK=40`, `MIC_WS=41`, `MIC_DIN=42` (set in `main.cpp`). If using an
external I2S breakout, route those three pads + GND. `start_capture()` installs
I2S @ 16 kHz / 16-bit / left-only, streams `MSG_AUDIO_CHUNK`.

## 4. Wire the OLED / SPI screen

SPI on XIAO: `SCK=D8 MOSI=D10 MISO=D9`. Pick the panel:

| Panel | CS | DC | RST |
|-------|----|----|-----|
| ST7735 128×128 | D7 | D2 | D1 |
| SSD1306 128×64 | D6 | D2 | D1 |
| SSD1306 128×32 | D5 | D2 | D1 |

Build with the matching `-DSCREEN_*`. DC=D2, RST=D1 shared across all three.

## 5. Input wiring (verified-free pins)

| Signal | Pin | Note |
|--------|-----|------|
| Wheel A | D0 | quadrature, INT on CHANGE |
| Wheel B | D4 | quadrature |
| BTN_A | D3 | pull-up; short=select, long>600ms=back |
| BTN_B | D5 | pull-up; short=cancel/back (moved from D4 — was aliased to WHEEL_B) |

**BUG to avoid:** Do NOT put BTN_B on GPIO4 — it collides with WHEEL_B. Use D5.

## 6. Power the wearable

- **Dev:** USB-C 5 V, no battery circuit.
- **Untethered:** 3.7 V Li-Po → `BAT` pad through charge/protect; XIAO
  charger tops from USB-C. Keep draw < 300 mA.

## 7. Connect real BLE peers (phone hub)

Phone is the single BLE hub (premortem #1): bead/XIAO + G2 + ring each pair
only with the phone.
- **XIAO ↔ phone:** phone connects to `"CyclopsXIAO"` (service `4fafc201-…`),
  writes `DISPLAY_CMD`/`NOTE` to `NOTE_CH` `beb5483e-…`; XIAO pushes
  `MSG_CMD` + `MSG_STATUS`.
- **COLMI R02:** XIAO (`-DENABLE_RING`) or `device/colmi_r02.py` (bleak)
  scans `R02_*` and subscribes TX `6E400003-…`.
- **G2 glasses:** phone streams `HUD_FRAME` to the G2 BLE characteristic
  (chunked to MTU).

## 8. Field-test checklist

- [ ] XIAO boots, advertises, screen renders HOME.
- [ ] Wheel/buttons navigate MENU; long-press A backs out.
- [ ] `Transcribe` → mic captures → phone transcribes → NOTE appears on HUD.
- [ ] Ring connects, `HEALTH` shows HR/SpO2/batt.
- [ ] `HUD_FRAME` reaches G2 (≤4 lines, ≤18 chars each).
- [ ] Low-batt auto-sleep; vibration confirm (pending).
- [ ] Gyro nod/shake gestures (pending calibration).

## 9. Not verifiable headless (the bring-up scope)

- Actual I2S mic + OLED bench test (logic only, via native_test).
- Live BLE to physical R02 / G2 (no hardware on the bench).
- `pio run -e xiao_*` flash + field test (CI compiles only).
- Vibration motor, low-batt auto-sleep, gyro calibration.

---
**[inferred]** §2–§7 pin/power/I2S facts are taken from `main.cpp` +
`01-hardware.md` + `30-colmi-r02-integration.md` and should be accurate.
§1/§8/§9 framing follows `PLAN.md` "Next (hardware)" and the premortem docs.
Inferred only: the exact toolchain commands (esptool/UF2 specifics) and the
precise ordering of the bench steps.
