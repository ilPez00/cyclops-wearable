# Cyclops — Pocket Build

> **RECONSTRUCTED DOC** — original `docs/11-pocket-build.md` (2026-07-08) lost
> on corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `docs/10-form-factor.md` (full wearable), `docs/15-cyclops-mini.md` (Mini),
> `docs/08-bringup.md`, `docs/30-colmi-r02-integration.md`. **[inferred]** =
> reconstructed. The pocket build = the Full wearable tightened to a pocketable
> unit (the bridge between Dev board and Mini).

## 0. What a "pocket build" is

A pocket build is the **Full wearable** packed into a small enclosure you carry
in a pocket: XIAO + OLED + Li-Po + (optional) ring, in a 3D-printed or
off-the-shelf case, charged from a power bank or wall wart via USB-C. It is the
field-testable middle ground before shrinking to the ring-scale Mini.

## 1. BOM (pocket)

| Part | Role |
|------|------|
| XIAO ESP32-S3 Sense | wearable MCU + I2S mic + BLE |
| SSD1306 128×64 **or** ST7735 128×128 | HUD (mono compact vs color) |
| Li-Po 3.7 V (~300–500 mAh) | untethered power |
| Charge/protect circuit | Li-Po safety (or rely on XIAO onboard charger) |
| Small tactile buttons + scrollwheel | input (D3/D5 + D0/D4) |
| Enclosure (`enclosure/` dir) | 3D-printed or clamshell case |
| (optional) COLMI R02 ring | health/gesture |

## 2. Enclosure / wiring

- SPI: `SCK=D8 MOSI=D10 MISO=D9`; screen CS per panel (D6 mono / D7 color),
  DC=D2, RST=D1.
- Input: Wheel A=D0 B=D4; BTN_A=D3 (pull-up); BTN_B=D5 (pull-up — **not D4**).
- I2S mic pads 40/41/42 (onboard; no external wiring needed).
- Li-Po → `BAT` pad through charge/protect; USB-C for charge + data.
- Keep total draw < 300 mA.

## 3. Build flags

- Color: `-DSCREEN_ST7735` on `xiao_st7735`.
- Compact mono: `-DSCREEN_128x64` on `xiao_128x64`.
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

1. `pio run -e xiao_128x64 -t upload` (or `_st7735`).
2. Verify `CyclopsXIAO` advertises; screen renders HOME.
3. Wheel/buttons navigate; long-press A backs out.
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
