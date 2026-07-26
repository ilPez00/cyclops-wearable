# Wiring — XIAO ESP32-S3 Sense

Single source for the Cyclops wearable wiring. Board: Seeed XIAO ESP32-S3 **Sense**
(onboard mic + microSD + OV2640 camera). Current firmware target: `xiao_128x32_i2c`
(I2C SSD1306 128×32 OLED + camera + config portal).

## Firmware pin map (already reserved — DO NOT reuse)

Silk↔GPIO uses the official XIAO ESP32-S3 (Sense) header map (D0=GPIO1,
D1=GPIO2, D2=GPIO3, D3=GPIO4, D4=GPIO5, D5=GPIO6, D6=GPIO43, D7=GPIO44,
D8=GPIO7, D9=GPIO8, D10=GPIO9). GPIO0 is the BOOT pad, **not** a header pin.

| Silk | GPIO | Function     | Notes |
|------|------|--------------|-------|
| D0   | 1    | WHEEL_A      | scroll wheel signal A (I2C-screen build) |
| D2   | 3    | BTN_A        | short=select, long=back/stop |
| D3   | 4    | WHEEL_B      | scroll wheel signal B |
| D4   | 5    | BTN_B        | cancel/back (see "Why 2 buttons?" below) |
| D6   | 43   | I2C SDA      | OLED data line |
| D7   | 44   | I2C SCL      | OLED clock line |
| D8   | 7    | SPI SCK      | SD card clock |
| D9   | 8    | SPI MISO     | SD card data out |
| D10  | 9    | SPI MOSI     | SD card data in |
| —    | 21   | SD CS        | onboard microSD chip select |
| —    | 40/41/42 | MIC     | I2S PDM, onboard |
| —    | 11–18 | CAM      | OV2640 ribbon, not on headers |

> **WHEEL_A never on GPIO0.** GPIO0 is a boot strapping pin — an encoder
> pulsing it during reset drops the S3 into download mode and can brick boot.
> On **SPI-screen** builds (ST7735 / transparent-151-SPI) the screen owns
> D0/D1/D5 for CS/DC/RST, so WHEEL_A moves to **D7 (GPIO44)** there; on I2C
> builds it is **D0 (GPIO1)** as above. Firmware picks this automatically.

Free header pads (I2C build): **D1 (GPIO2** — battery sense**)**, **D5 (GPIO6)**.
Everything else on the 11-pad header is in use. GPIO0 (BOOT) is off-limits for
signals; GPIO10–20 / 38/39/45–48 are internal (PSRAM/flash/USB/camera) and not
broken out.

## Why two buttons?

BTN_A (short=select, long=back/stop) and BTN_B (short=cancel) serve different
purposes — one button can't cover all cases:

| Action | BTN_A | BTN_B |
|--------|-------|-------|
| Navigate into a menu/subview | short | — |
| Go back one level | long (>600ms) | short |
| Decline a confirm dialog | — | short |
| Stop recording / abort agent | long | — |

The 3-pin scroll wheel provides navigation (up/down via quadrature A/B) but has
**no push switch**. Without a push-to-click encoder, two separate buttons are
needed for select and cancel. The firmware supports a 5-pin encoder (with
built-in switch) as an alternative — just wire the switch pin to D2 (BTN_A) and
leave D4 (BTN_B) unwired — but the 3-pin encoder + 2 buttons is the documented build.

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
| CS         | D5       | 6    | chip select |
| DC/A0      | D1       | 2    | data/command |
| RES/RST    | D0       | 1    | reset line |

- Init: `initR(INITR_144GREENTAB)` or `initR(INITR_MINI160x80)` depending on module.
- 128×128 = 16 text rows → expanded HUD layout (health/notes/REC/consent preview on HOME).
- Build: `pio run -e xiao_st7735`.

### SPI SSD1306 alternatives

| Env | Screen | Bus |
|-----|--------|-----|
| `xiao_128x64` | SSD1306 128×64 SPI | VSPI (GPIO7/8/9), CS=GPIO6 |
| `xiao_128x32` | SSD1306 128×32 SPI | VSPI, CS=GPIO6 |

## Gyroscope / IMU — external I2C breakout (optional)

The XIAO ESP32-**S3** Sense has **no onboard IMU** (camera + PDM mic + microSD
only — the onboard LSM6DS3 is on the nRF52840 *Nano* Sense, a different board).
An IMU is optional and needs an external breakout.

On the I2C-screen builds (`xiao_128x32_i2c`, `xiao_transparent_151_i2c`) the IMU
shares the OLED I2C bus on D6/D7 (GPIO43/44). SPI-screen builds drive the screen
over SPI, leaving GPIO43/44 free for a dedicated I2C IMU bus if wired.

External I2C breakout (MPU-6050 or LSM6DS3) on D6/D7:

| IMU pin | XIAO pad | GPIO |
|---------|----------|------|
| VCC     | 3V3      | —    |
| GND     | GND      | —    |
| SDA     | D6       | 43   |
| SCL     | D7       | 44   |
| INT     | D5       | 6    |  (optional; GPIO1/D0 is WHEEL_A now — use D5/GPIO6, a free pad) |
| ADDR    | —        | —    |

- Addresses: MPU-6050 = 0x68 / 0x69, LSM6DS3 = 0x6A / 0x6B. OLED = 0x3C, no clash.
- Do **not** wire an IMU to the S3's *default* I2C bus (GPIO5/6): GPIO5 is BTN_B.
  Use the D6/D7 (GPIO43/44) bus above.

## Camera (onboard OV2640, default build)

The XIAO S3 Sense has an **onboard OV2640** camera on the proprietary ribbon.
Firmware initialises it for snapshot (/snap) and MJPEG stream (/stream) over WiFi.
The same WiFi server also exposes `/audio.wav` — a live WAV stream of the onboard
PDM mic (16-bit mono 16 kHz) so the companion app can record wearable audio
(returns 503 while a BLE audio capture already holds the mic).

| Camera resource | Notes |
|----------------|-------|
| SCCB (I2C-like) | GPIO18 (SIOC) / GPIO17 (SIOD) — dedicated, not shared with user GPIO |
| DVP parallel bus | GPIO11–16 — dedicated, not exposed on headers |
| VSYNC / HREF / PCLK / XCLK | Dedicated camera interface pins on Sense |
| PSRAM | Required for frame buffers; `ps_malloc` fallback in `camera_capture.cpp` |

- Pins are set via `esp_camera_init()` config struct — no user wiring needed.
- Camera init fallback chain: VGA@20MHz → VGA@16MHz → QVGA@20MHz.
- WiFi stream serves ~10 fps MJPEG, 60s idle teardown.

## Reserved (primary build)

| Pins | Peripheral | Why |
|------|------------|-----|
| D0/D3 | scroll wheel | WHEEL_A/B quadrature, 2 signals + GND = 3 pins |
| D2/D4 | BTN_A/B | select + cancel, see "Why two buttons?" above |
| D6/D7 | I2C bus | OLED, do not reuse |
| D8/D9/D10 | SPI bus | SD card (shared bus even if no card) |
| GPIO21 | SD CS | onboard microSD |
| GPIO40/41/42 | I2S PDM mic | onboard, do not touch |
| GPIO11–18 | camera | OV2640 ribbon, not on headers |

## Battery (USB-C management board)

The XIAO S3 Sense has an onboard charger IC but **no fuel-gauge ADC** routed
to a header pin. Power comes from a separate USB-C battery management board
(e.g. TP4056/TC4056 with USB-C, IP2312, or similar):

```
USB-C battery board        XIAO S3 Sense
┌─────────────────┐
│ USB-C (charge in)│
│                  │
│ BAT+ │ BAT-      │  ← Li-Po connected here
│      │           │
│ OUT+ ────────────→ 5V pin (or USB-C VBUS)
│ OUT- ────────────→ GND
│                  │
│ (opt) BAT_LVL ───→ D1 (GPIO2) via divider if board has fuel-gauge out
└─────────────────┘
```

**Power path:** battery management board's OUT+ → XIAO 5V (or USB-C VBUS pin).
The XIAO's onboard 3.3V regulator handles the rest. GND must be shared.

**Battery level telemetry:** if your board exposes a battery voltage pin, wire
it to D1 (GPIO2) through a 100k+100k divider (BAT+ → 100k → D1 → 100k → GND) and add
`-DENABLE_BATT=1` to `platformio.ini` build flags. If the board has no such
pin, the firmware shows 0 mV and no battery icon — the device still runs fine,
you just won't see a percentage.

## Full layout (one picture)

```
                 XIAO ESP32-S3 SENSE
   ┌──────────────────────────────────────────┐
   │  OLED 128x32 (I2C) ── VCC→3V3 GND→GND     │  4-pin screen
   │                      SDA→D6  SCL→D7       │
   │                                            │
   │  WHEEL_A→D0  WHEEL_B→D3  (GND→GND)        │  3-pin encoder
   │  BTN_A→D2    BTN_B→D4                      │  2 buttons
   │                                            │
   │  USB-C battery board ── OUT+→XIAO 5V       │  power + charge
   │                       ── OUT-→GND          │
   │                       ── (opt) BAT_LVL→D1  │
   │                                            │
   │  SD (onboard, GPIO21/7/8/9)               │
   │  MIC (onboard, GPIO40/41/42)              │
   │  CAM (onboard ribbon, GPIO11-18)          │
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
| WiFi camera stream | `xiao/src/camera_capture.cpp` | `/snap` JPEG, `/stream` MJPEG ~10 fps, `/audio.wav` PDM mic, 60s idle teardown |
| HUD layout (128×128) | `shared/include/hud.h` | HOME: expanded banner + health preview + notes preview + REC timer + consent indicator on ≥6-row panels |
| HUD layout (128×32) | `shared/include/hud.h` | HOME: compact 4-row (banner + status + bottom strip); NOTES scrolls on overflow |
| Notes scroll | `shared/include/hud.h` | NOTES mode scrolls view to keep `note_sel` visible; right-edge scroll bar on overflow |

## SD logging (on by default in i2c build)

- Mounts `/sdcard` on the onboard slot. FAT32 card ≤32 GB.
- Appends timestamped lines to `/sdcard/cyclops.log`: notes, health samples,
  rec start/stop.
- If no card: boots with `[boot] sd card NOT present (logging disabled)`.
