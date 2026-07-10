# Cyclops — Hardware

> **RECONSTRUCTED DOC** — original `docs/01-hardware.md` lived only on the
> corrupted `/dev/sde2` mount (2026-07-07) and was never bundled. Rebuilt
> 2026-07-10 from `firmware/xiao/src/main.cpp`, `docs/22-screens-plan.md`,
> `docs/30-colmi-r02-integration.md`, `docs/21-architecture-v2.md` and the
> `README.md`. Sections marked **[inferred]** are reconstructions — verify on
> metal before trusting.

## 0. Two MCUs, one design

Cyclops firmware targets two MCUs through a shared `cyclops_shared` lib:

| MCU | Role | Build envs |
|-----|------|-----------|
| **XIAO ESP32-S3 Sense** | wearable HUD + I2S mic + NimBLE | `xiao_st7735` `xiao_128x64` `xiao_128x32` |
| **Arduino Uno / Nano** | bench/teaching HUD (no BLE/mic) | `arduino_st7735` `arduino_128x64` `arduino_128x32` |

XIAO is the real wearable. Arduino proves the HUD logic on 2 KB RAM hardware.

## 1. XIAO ESP32-S3 Sense — spec

- dual-core Xtensa LX7 @ 240 MHz, 8 MB PSRAM, 8 MB flash (seeed_xiao_esp32s3).
- Onboard: OV2640 cam (QVGA), I2S MEMS mic (pads 40/41/42), 6-axis IMU
  (gyro + accel, for nod/shake gestures), Li-Po charge circuit.
- Wireless: WiFi + BLE 4.2 (NimBLE). SPI on GPIO 1/2/7/8/9/10.
- USB-C: power + data + flashing (UF2 / PlatformIO).

## 2. Displays (one of three, compile-selected)

From `22-screens-plan.md`, all three wrap Adafruit drivers behind a header-only
`Screen` base (`shared/include/screen.h`). Resolution-agnostic: `char_cols()` /
`text_rows()` drive layout; no fixed 4×22 buffer forced on big panels.

| Panel | Res | driver | XIAO CS | Arduino CS |
|-------|-----|--------|----------|-------------|
| ST7735 | 128×128 RGB565 | `St7735Screen` | D7 | 10 |
| SSD1306 128×64 | 128×64 1bpp | `Ssd1306_128x64_Screen` | D6 | 7 |
| SSD1306 128×32 | 128×32 1bpp | `Ssd1306_128x32_Screen` | D5 | 4 |

Mono panels: white-on-black. ST7735: green-on-black. DC=D2, RST=D1 (shared).

## 3. XIAO pin map (verified by compile)

```
  XIAO ESP32-S3 Sense          Function              Notes
  ─────────────────────────────────────────────────────────────────────
  D0  ── wheel A (quad)        scroll input          INT on CHANGE
  D4  ── wheel B (quad)        scroll input
  D3  ── BTN_A (pull-up)      select (short) / back (long >600 ms)
  D5  ── BTN_B (pull-up)      cancel / back one level   (was D4; moved to free GPIO5)
  D8  ── SPI SCK               screen (VSPI)
  D10 ── SPI MOSI              screen
  D9  ── SPI MISO              screen
  D7/D6/D5 ── screen CS        (panel-selected, see §2)
  D2  ── screen DC             all panels
  D1  ── screen RST            all panels
  40/41/42 ── I2S BCLK/WS/DIN mic capture (onboard pad)
  5V / GND ── USB-C            power + data + charge
  BAT (pad) ── Li-Po + (optional)   untethered runtime
```

**BUG fixed (HUD/UX doc):** `PIN_BTN_B` was GPIO4 == `PIN_WHEEL_B` (4) — confirm/
cancel and wheel were aliased, breaking menu/back. Moved to GPIO5 (verified free:
SPI uses 1/2/7/8/9/10, mic 40/41/42). Done in `main.cpp`.

## 4. COLMI R02 ring (health/gesture sensor)

Sealed $20 BLE smart ring. No solder — "wiring" = establishing the BLE GATT
link (`30-colmi-r02-integration.md`). 17 mAh cell, ~5 days, magnetic pogo
charge. Feeds HR / SpO2 / battery / steps / gestures to the XIAO HUD via
`RingBle` (NimBLE central, `-DENABLE_RING`).

## 5. Power

- **Tethered dev:** USB-C 5 V. No battery circuit needed.
- **Untethered wearable:** 3.7 V Li-Po → `BAT` pad through charge/protect;
  XIAO's onboard charger tops from USB-C. Keep total draw **< 300 mA**
  (ESP32 + screen + mic + ring BLE client).

## 6. Build matrix (verified green)

| env | RAM | Flash | status |
|-----|-----|--------|--------|
| arduino_st7735 | 59.3% | 55.5% | OK |
| arduino_128x64 | 67.9% | 62.8% | OK |
| arduino_128x32 | 67.9% | 62.8% | OK |
| xiao_st7735 | 9.3% | 15.8% | OK |
| xiao_128x64 | 9.4% | 16.2% | OK |
| xiao_128x32 | 9.4% | 16.2% | OK |

Uno + ST7735 uses no full framebuffer (Adafruit draws direct); 128×64 = 1 KB,
128×32 = 512 B controller RAM — all fit 2 KB. Decoder buffer shrunk 1024→256
to fit Uno RAM.

## 7. Not yet on metal (headless-unverifiable)

- Real I2S mic + OLED bench test (only Arduino/XIAO envs compile; native_test
  used for logic).
- Live BLE connect to a physical R02 / G2 (no ring/glasses on the bench).
- `pio run -e xiao_*` flash + field test (PlatformIO not installed locally;
  CI compiles the firmware).
- Vibration-motor feedback, low-batt auto-sleep, gyro gesture calibration.

---
**[inferred]** The exact "two MCU" framing, the §6 RAM/flash table and the
§3 pin note about the BTN_B bug are taken from committed `main.cpp` +
`22-screens-plan.md` and should be accurate. The "bench/teaching" description of
the Arduino target and the §5 draw budget are reasonable reconstructions.
