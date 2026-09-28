# Cyclops — Form Factor (wearable shapes)

> **RECONSTRUCTED DOC** — original `docs/10-form-factor.md` (2026-07-08) lost
> on corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `firmware/xiao/src/main.cpp`, `docs/01-hardware.md`, `docs/22-screens-plan.md`,
> `docs/30-colmi-r02-integration.md`, `docs/15-cyclops-mini.md` (itself
> reconstructed). **[inferred]** = reconstructed. This doc enumerates the
> physical builds Cyclops targets.

## 0. Design space

> **MVP supersedes the input/display rows below** (docs/43, docs/44): the harness
> is a XIAO ESP32-S3 **Sense** + a 128×32 **I2C** OLED + **one** button on GPIO3
> + an external MPU-class accel at `0x68`. There is **no onboard IMU** on a
> XIAO, no rotary wheel (removed — AGENTS.md), and no ST7735 in the MVP. The
> ST7735 / 128×64 rows below are legacy lab builds, kept for pin history.

Cyclops separates **compute/wearable** (XIAO) from **sensing** (ring) and
**display** (glasses / OLED). Three form factors trade off size vs capability:

| Factor | Display | Sensor | Power | Footprint |
|--------|----------|---------|--------|-----------|
| **Dev board** (legacy) | ST7735 128×128 | external accel @`0x68` + PDM mic (`imu.cpp` speaks MPU registers only — `imu_whoami.h` refuses anything else) | USB-C tether | breadboard |
| **Full wearable** | ST7735 128×128 or 128×64 | IMU + optional ring | Li-Po or tether | wrist / chest unit |
| **Mini** (doc 15) | SSD1306 128×32 | ring-first (R02) | Li-Po default | finger ring + coin-sized HUD |

All three run the **same firmware** — only `-DSCREEN_*` + `-DENABLE_RING`
differ (see `01-hardware.md`, `22-screens-plan.md`).

## 1. Dev board (bench)

- XIAO on a breadboard, ST7735 128×128 (CS=D7, DC=D2, RST=D1).
- USB-C tether: power + serial + flashing. No battery circuit.
- Purpose: firmware logic dev, HUD layout, protocol bring-up.

## 2. Full wearable

- XIAO + a larger OLED (128×128 color or 128×64 mono), Li-Po via `BAT`.
- Optional COLMI R02 ring for HR/SpO2/steps/gesture (`-DENABLE_RING`).
- Worn on wrist or as a chest/visor unit; gyro nod/shake gestures live.
- Untethered: 3.7 V Li-Po → charge/protect → XIAO charger; draw < 300 mA.

## 3. Mini (compact)

See `15-cyclops-mini.md` (reconstructed). Essence:
- COLMI R02 ring as the always-on health/gesture sensor.
- XIAO ESP32-S3 + **128×32 SSD1306, I2C** (`0x3C`; SDA GPIO43 / SCL GPIO44) —
  the glanceable-only panel. There is no CS pin on an I2C carrier.
- Li-Po default, pocket-sized. One finger-mounted sensor + one coin-sized HUD.
- Build: `pio run -e xiao_128x32_i2c` (the MVP env, docs/43). `-DENABLE_RING`
  only for ring work (the ring has no button — taps come from accel spikes).
- Case work: dimensions, tolerances and the caliper sheet live in
  `docs/44-case-redesign.md` — the committed `.scad`/`.blend`/FreeCAD files are
  not valid for this build.

## 4. Display fit (from `22-screens-plan.md`)

| Panel | Rows | Use |
|-------|------|-----|
| ST7735 128×128 | 16 text rows | dev / full wearable (most info) |
| SSD1306 128×64 | 8 rows | full wearable (compact, mono) |
| SSD1306 128×32 | 4 rows | Mini (glanceable only) |

Mono panels: white-on-black. ST7735: green-on-black; selected row inverted.

## 5. Power budget (all factors)

Keep total draw **< 300 mA** (ESP32 + screen + mic + ring BLE client).
Li-Po via `BAT` + charge/protect; USB-C tops from the host. Ring is
independent (magnetic pogo, ~5 days).

## 6. Not yet on metal

- Real I2S mic + OLED bench test (logic only, native_test).
- Live BLE to physical R02 / G2 (no hardware on bench).
- `pio run -e xiao_*` flash + field test (CI compiles only).
- Vibration motor, low-batt auto-sleep, gyro calibration.

---
**[inferred]** The three-factor table, the display-fit rows, the pin/CS facts
and the < 300 mA budget are taken from committed `main.cpp` + `22-screens-plan.md`
+ `30-colmi-r02-integration.md` and should be accurate. Inferred only: the
"Dev board / Full wearable / Mini" naming and the §1–§3 descriptive prose;
the original doc may have used different labels or included enclosure detail
(now in `docs/10-form-factor`? — see `enclosure/` dir, which this rebuild
does not open).
