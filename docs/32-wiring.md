# Wiring — XIAO ESP32-S3 Sense

Single source for the Cyclops wearable wiring. Board: Seeed XIAO ESP32-S3 **Sense**
(onboard mic + microSD + OV2640 camera). Current firmware target: `xiao_128x32_i2c`
(I2C SSD1306 128×32 OLED + camera + config portal).

## Firmware pin map (already reserved — DO NOT reuse)

| GPIO (silk) | Function            | Notes |
|-------------|---------------------|-------|
| GPIO0 (D0)  | WHEEL_A             | scroll wheel A |
| GPIO4 (D4)  | WHEEL_B             | scroll wheel B |
| GPIO3 (D3)  | BTN_A               | short=select, long=back/stop |
| GPIO5 (D5)  | BTN_B               | cancel/back |
| GPIO1 (D1)  | ST7735 RST / IMU INT| reset line for ST7735; optional IMU IRQ on I2C builds |
| GPIO2 (D2)  | ST7735 DC / BAT sense| data/command for ST7735; optional battery divider on I2C builds |
| GPIO6 (D6-silk, unused) | —          | free on ST7735 build; I2C SDA on I2C builds |
| GPIO7 (D8)  | SPI SCK / SD SCK    | screen + microSD share VSPI |
| GPIO8 (D9)  | SPI MISO / SD MISO  | screen + microSD share VSPI |
| GPIO9 (D10)  | SPI MOSI / SD MOSI | screen + microSD share VSPI |
| GPIO21      | SD CS               | onboard microSD slot |
| GPIO40/41/42| MIC (onboard)       | I2S, do not touch |
| GPIO43 (D6) | I2C SDA             | shared screen + gyro bus (I2C builds only) |
| GPIO44 (D7) | I2C SCL             | shared screen + gyro bus (I2C builds only) |

Free GPIOs for expansion: GPIO10–20, GPIO38/39/45–48.

## Display — I2C SSD1306 128×32 OLED (default target)

Primary build target. Firmware env: `xiao_128x32_i2c`. I2C on D6/D7.

| OLED pin | XIAO pad | GPIO |
|----------|----------|------|
| VCC      | 3V3      | —    |
| GND      | GND      | —    |
| SDA      | D6       | 43   |
| SCL      | D7       | 44   |

- 3.3 V native, no level shifter, no reset pin needed (`rst_pin=-1`).
- Address 0x3C default (try 0x3D if blank in `screens.h` `addr_` ctor param).
- 128×32 = 4 text rows at default font → compact HUD layout (banner + status + bottom strip).
- Build/flash:
  ```
  cd firmware && . .venv/bin/activate
  pio run -e xiao_128x32_i2c -t upload --upload-port /dev/ttyACM0
  ```

### SPI ST7735 alternative (128×128 TFT, legacy)

For an SPI ST7735 128×128 TFT on VSPI (GPIO7/8/9). Firmware env: `xiao_st7735`.

| ST7735 pin | XIAO pad | GPIO | Notes |
|------------|----------|------|-------|
| VCC        | 3V3      | —    | 3.3 V |
| GND        | GND      | —    | |
| SCK        | D8       | 7    | SPI clock |
| MOSI/SDA   | D10      | 9    | SPI data |
| MISO/SDO   | D9       | 8    | unused by TFT (shared with SD) |
| CS         | D6       | 6    | chip select |
| DC/A0      | D2       | 2    | data/command |
| RES/RST    | D1       | 1    | reset line |

- Init: `initR(INITR_144GREENTAB)` or `initR(INITR_MINI160x80)` depending on module.
- 128×128 = 16 text rows → expanded HUD layout (health/notes/REC/consent preview on HOME).
- Build: `pio run -e xiao_st7735`.

### SPI SSD1306 alternatives

| Env | Screen | Bus |
|-----|--------|-----|
| `xiao_128x64` | SSD1306 128×64 SPI | VSPI (GPIO7/8/9), CS=GPIO6 |
| `xiao_128x32` | SSD1306 128×32 SPI | VSPI, CS=GPIO5 |

## Gyroscope / IMU — I2C (shared bus, I2C builds only)

On `xiao_128x32_i2c` / `xiao_128x32` / `xiao_128x64` builds only. The `xiao_st7735`
SPI build uses GPIO1/2/6 for the TFT and has no I2C bus for an external IMU.

I2C breakout (MPU-6050 or LSM6DS3) on D6/D7 shared with OLED:

| IMU pin | XIAO pad | GPIO |
|---------|----------|------|
| VCC     | 3V3      | —    |
| GND     | GND      | —    |
| SDA     | D6       | 43   |
| SCL     | D7       | 44   |
| INT     | D1       | 1    |  (optional; note D1 is ST7735 RST on SPI build)
| ADDR    | —        | —    |

- Addresses: MPU-6050 = 0x68 / 0x69, LSM6DS3 = 0x6A / 0x6B. OLED = 0x3C, no clash.
- The XIAO S3 Sense **onboard** LSM6DS3 sits on the *default* I2C bus (GPIO5/6)
  which collides with BTN_B (GPIO5). Do NOT use the onboard IMU without first
  moving BTN_B to a free pin.

## Camera (onboard OV2640, default build)

The XIAO S3 Sense has an **onboard OV2640** camera on the proprietary ribbon.
Firmware initialises it for snapshot (/snap) and MJPEG stream (/stream) over WiFi.

| Camera resource | Notes |
|----------------|-------|
| SCCB (I2C-like) | GPIO18 (SIOC) / GPIO17 (SIOD) — dedicated, not shared with user GPIO |
| DVP parallel bus | GPIO11–16 — dedicated, not exposed on headers |
| VSYNC / HREF / PCLK / XCLK | Dedicated camera interface pins on Sense |
| PSRAM | Required for frame buffers; `ps_malloc` fallback in `camera_capture.cpp` |

- Pins are set via `esp_camera_init()` config struct — no user wiring needed.
- Camera init fallback chain: VGA@20MHz → VGA@16MHz → QVGA@20MHz.
- WiFi stream serves ~10 fps MJPEG, 60s idle teardown.

## Reserved — leave these alone

- Wheel + buttons: GPIO0/3/4/5 (firmware live).
- SPI bus: GPIO7/8/9 (screen + SD, shared on `xiao_st7735`).
- SD: GPIO21/7/8/9 (onboard Sense slot; FAT32 card ≤32 GB).
- Mic: GPIO40/41/42 (onboard I2S PDM).
- Camera: GPIO11–18 (onboard ribbon, not on headers).
- I2C bus (I2C builds): GPIO43/44.

## Battery (optional, not wired by default)

The Sense has an onboard charger but **no fuel-gauge ADC** routed. To read
battery %, add a divider:

```
BAT+ ── 100k ── GPIO2 (D2) ── 100k ── GND
```

Leave GPIO2 free for this. Firmware support is added on request
(`-DENABLE_BATT=1`).

## Full layout (one picture)

```
                 XIAO ESP32-S3 SENSE
   ┌──────────────────────────────────────────┐
   │  USB-C                                     │
   │                                            │
   │  OLED 128x32 (I2C) ── SDA→D6  SCL→D7       │  ← screen + gyro bus
   │  GYRO (I2C)        ── SDA→D6  SCL→D7       │
   │  GYRO INT (opt)     ── D1                  │
   │                                            │
   │  WHEEL_A→D0  WHEEL_B→D4                    │
   │  BTN_A→D3    BTN_B→D5                      │
   │  BAT sense→D2 (opt, divider)              │
   │  SD (onboard, GPIO21/7/8/9)               │
   │  MIC (onboard, GPIO40/41/42)              │
   └──────────────────────────────────────────┘
```

## Build matrix (firmware/platformio.ini)

| Env                 | Screen              | Notes |
|---------------------|---------------------|-------|
| `xiao_128x32_i2c`   | SSD1306 128×32 I2C  | **current**; camera + config portal + VAD + ring + IMU; -DCONFIG_PORTAL=1 -DENABLE_RING=1 -DENABLE_IMU=1 |
| `xiao_st7735`       | ST7735 128×128 SPI  | ST7735 TFT; camera + config portal + VAD + expanded HUD |
| `xiao_128x64`       | SSD1306 128×64 SPI  | |
| `xiao_128x32`       | SSD1306 128×32 SPI  | |

Flash any: `pio run -e <env> -t upload --upload-port /dev/ttyACM0`.

## Software features (firmware/shared + xiao/src)

| Feature | File(s) | Details |
|---------|---------|---------|
| Config Portal | `xiao/src/config_portal.h` | Captive WiFi portal on first boot; factory-reset with BTN_A+BTN_B hold; gated behind `-DCONFIG_PORTAL=1` |
| VAD Gate | `shared/include/audio_trigger.h` (`VadGate`) | RMS energy gate before ADPCM encode; adaptive ambient floor |
| Power-saving | `xiao/src/main.cpp` | Brownout disable (`WRITE_PERI_REG`); PSRAM-aware camera buffers; VGA→QVGA fallback chain |
| WiFi camera stream | `xiao/src/camera_capture.cpp` | `/snap` JPEG, `/stream` MJPEG ~10 fps, 60s idle teardown |
| HUD layout (128×128) | `shared/include/hud.h` | HOME: expanded banner + health preview + notes preview + REC timer + consent indicator on ≥6-row panels |
| HUD layout (128×32) | `shared/include/hud.h` | HOME: compact 4-row (banner + status + bottom strip); NOTES scrolls on overflow |
| Notes scroll | `shared/include/hud.h` | NOTES mode scrolls view to keep `note_sel` visible; right-edge scroll bar on overflow |

## SD logging (on by default in i2c build)

- Mounts `/sdcard` on the onboard slot. FAT32 card ≤32 GB.
- Appends timestamped lines to `/sdcard/cyclops.log`: notes, health samples,
  rec start/stop.
- If no card: boots with `[boot] sd card NOT present (logging disabled)`.
