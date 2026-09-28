# Cyclops — Pocket Build

> **RECONSTRUCTED DOC** — original `docs/11-pocket-build.md` (2026-07-08) lost
> on corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `docs/10-form-factor.md` (full wearable), `docs/15-cyclops-mini.md` (Mini),
> `docs/08-bringup.md`, `docs/30-colmi-r02-integration.md`. **[inferred]** =
> reconstructed. The pocket build = the Full wearable tightened to a pocketable
> unit (the bridge between Dev board and Mini).

> **MVP note (2026-09-28):** the shipped harness is docs/43's — 128×32 **I2C**
> OLED, **one** button on GPIO3, MPU-class accel at `0x68`, XIAO ESP32-S3 Sense.
> Rows below marked *legacy* are kept for pin history only. Case geometry:
> `docs/44-case-redesign.md`.

## 0. What a "pocket build" is

A pocket build is the **Full wearable** packed into a small enclosure you carry
in a pocket: XIAO + OLED + Li-Po + (optional) ring, in a 3D-printed or
off-the-shelf case, charged from a power bank or wall wart via USB-C. It is the
field-testable middle ground before shrinking to the ring-scale Mini.

## 1. BOM (pocket)

| Part | Role |
|------|------|
| XIAO ESP32-S3 Sense | wearable MCU + I2S mic + BLE |
| SSD1306 **128×32 I2C** (`0x3C`) | HUD (the MVP panel; 128×64 / ST7735 are *legacy*) |
| Li-Po 3.7 V (~300–500 mAh) | untethered power |
| Charge/protect circuit | Li-Po safety (or rely on XIAO onboard charger) |
| **One** tactile button (GPIO3) + MPU-class accel (`0x68`) | input: tap / double-tap / long-hold + tilt-scroll (no wheel — removed) |
| Enclosure (`enclosure/` dir) | 3D-printed or clamshell case |
| (optional) COLMI R02 ring | health/gesture |

## 2. Enclosure / wiring

- I2C (MVP): SDA=GPIO43, SCL=GPIO44 — OLED at `0x3C`, accel at `0x68` on the
  same bus. Full pin/keep-out table: `docs/30-schematics-xiao.md`.
- SPI (*legacy* screens only): `SCK=D8 MOSI=D10 MISO=D9`; screen CS per panel
  (D6 mono / D7 color), DC=D2, RST=D1.
- Input (MVP): **one** button, GPIO3, active-low `INPUT_PULLUP` — tap = OK,
  double-tap = BACK, long = AGENT. GPIO5 is free; BTN_B is not populated.
- PDM mic (GPIO42 clk / GPIO41 data, onboard Sense): no external wiring.
- Li-Po → `BAT` pad through charge/protect; USB-C for charge + data.
- Keep total draw < 300 mA.

## 3. Build flags

- Color (*legacy*): `-DSCREEN_ST7735` on `xiao_st7735`.
- Compact mono (*legacy*): `-DSCREEN_128x64` on `xiao_128x64`.
- **MVP:** `pio run -e xiao_128x32_i2c` — I2C OLED + accel + one button.
- Ring: add `-DENABLE_RING`.

## 4. Pocket vs Mini vs Dev

| | Dev board | Pocket (this) | Mini (doc 15) |
|--|-----------|---------------|----------------|
| Display | ST7735 128×128 | 128×64 or 128×128 | 128×32 |
| Sensor | IMU + I2S | IMU + I2S (+ring) | ring-first |
| Power | USB-C tether | Li-Po | Li-Po |
| Footprint | breadboard | pocket enclosure | finger + coin HUD |
| Purpose | firmware dev | field test | minimal wearable |

## 5. Bring-up (from `08-bringup.md`)

1. `pio run -e xiao_128x32_i2c -t upload` (MVP; `_128x64` / `_st7735` are legacy).
2. Verify `CyclopsXIAO` advertises; screen renders HOME.
3. tap = OK / opens MENU, double-tap = BACK, long-press = AGENT; tilt scrolls
   (`docs/43` §2 for the single-button map).
4. `Transcribe` → mic → phone STT → NOTE on HUD.
5. (ring) `HEALTH` shows HR/SpO2/batt.
6. Low-batt auto-sleep; vibration confirm (pending).

## 6. Not yet on metal

- Real I2S mic + OLED bench test (logic only, native_test).
- Live BLE to physical R02 / G2 (no hardware on bench).
- `pio run -e xiao_*` flash + field test (CI compiles only).
- Vibration motor, gyro calibration.

---
**[inferred]** The BOM, pin/CS facts, build flags and the comparison table are
grounded in committed `main.cpp` + `22-screens-plan.md` + `15-cyclops-mini.md`
(reconstructed) and should be accurate in structure. Inferred only: the
"pocket" naming as distinct from "full wearable," the enclosure reference, and
the §1 BOM quantities — the original may have specified exact mAh / case dims.
