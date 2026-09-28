# Cyclops mini4 — 4-part minimal wearable

Minimal untethered build: **screen + battery + gyroscope + 1 button**.

## What it is

XIAO ESP32-S3 Sense with:
- **SSD1306 128×32 I2C OLED** (D6=SDA, D7=SCL, 0x3C)
- **MPU-6050 IMU** on same bus (AD0→GND = 0x68), shared pins
- **Single button** (D2/GPIO3) to GND with INPUT_PULLUP
- **Battery sense** via 2:1 divider: BAT+→100k→D1→100k→GND

## What it does

| Feature | Implementation |
|---------|----------------|
| HUD display | Notes/status streamed from brain over BLE or USB serial |
| Scroll | Tilt forward/back ≈ wheel scroll |
| Select | Accel tap (single/double) or button single press |
| Cancel | Button double press |
| Agent ask | Button long press (>600 ms) or tap gesture |
| Battery % | Read ADC, divide by 2, clamp 0–100 |
| Low-power | Sleep 250 ms when screen off or <20% batt |
| Consent | Off-body detection via accel stability (4 s stillness) |

## What it does NOT do

No mic, camera, SD card, ring, wheel, or second button. Audio/photo capture and agent calls are **phone-driven**: the wearable forwards `MSG_CMD` and the brain/app fulfils.

## Wiring (XIAO ESP32-S3 Sense)

| Part | XIAO silk | GPIO | Note |
|------|-----------|------|------|
| OLED VCC | 3V3 | — | 3.3 V |
| OLED GND | GND | — | |
| OLED SDA | D6 | 43 | shared with IMU |
| OLED SCL | D7 | 44 | shared with IMU |
| MPU-6050 VCC | 3V3 | — | 3.3 V |
| MPU-6050 GND | GND | — | |
| MPU-6050 SDA | D6 | 43 | same as OLED |
| MPU-6050 SCL | D7 | 44 | same as OLED |
| BTN1 | D2 | 3 | SIG→GND, INPUT_PULLUP |
| BAT sense | D1 | 2 | divider tap |

## Build & flash

```bash
# mini4 is its own PlatformIO project; src_dir is explicit (docs/43 C6):
pio run -d firmware/mini4 -t upload
```

> **Not the MVP target.** The shipping MVP is `xiao_128x32_i2c` (all Sense
> peripherals + one button, docs/43). mini4 remains the minimal bench/dev unit.
> Its project root `main.cpp` is **not** built — PlatformIO compiles
> `firmware/mini4/src/main.cpp`; a stray root copy silently shadowed it once
> (found 2026-09-28), hence `src_dir = src` in `mini4/platformio.ini`.

## Protocol

Same v2 framing as full Cyclops:
- `MSG_CMD {a,N,arg":"S"}}` → wearable emits back
- `MSG_DISPLAY_CMD` / `MSG_NOTE` → HUD update
- `MSG_STATUS` → battery, BT, HR, etc.
- `MSG_HUD_FRAME` → optional HUD frame to mirror

## Comparison

| Feature | Full Cyclops | mini4 |
|---------|--------------|-------|
| Screen | ST7735 128×128 or 128×32 I2C | 128×32 I2C only |
| IMU | Optional, D6/D7 | Required, shared with screen |
| Mic | Onboard PDM I2S | — (phone handles) |
| Camera | OV2640 ribbon | — (phone handles) |
| Buttons | 2 | 1 |
| Wheel | 3-pin encoder | — |
| Ring | COLMI R02 BLE | — |
| SD card | Onboard slot | — |

## APK Integration

The companion app gains:
- **LifeOS tab** (physis goals/today)
- **Coherence tab** (quality + communities)
- **Concept memory** (search notes + entities)
- **Ranker** (BM25 + RRF hybrid, offline)
- **Planner** (counterfactual simulation, agent gates)

The API endpoint matrix (`CyclopsApi.kt`) now includes:
- `/api/physis/*` — physis bridge (status, today, goals, coherence)
- `/api/concepts` — concept memory (concept search/groups)
- `/api/truth` — audited truth editing (before/after log)
- `/api/cost` — per-provider token usage

## Power budget

| Component | Typical current |
|-----------|-----------------|
| ESP32-S3 (idle) | ~20 mA |
| OLED (display) | ~5–10 mA |
| IMU (polled) | <1 mA |
| BLE (active) | ~5–10 mA |
| **Total** | <50 mA at 3.7 V |

Untethered runtime: ~800 mAh cell → ~16 h (with moderate BLE use).

## Development

- Firmware gate: `shared/test_hud.cpp` + wire framing.
- Host gate: same as Cyclops (no pio needed).
- Test battery sense by `pio run -e xiao_mini4 -t upload && screen /dev/ttyACM0 115200`.