# Wiring — XIAO ESP32-S3 Sense

Single source for the Cyclops wearable wiring. Board: Seeed XIAO ESP32-S3 **Sense**
(onboard mic + microSD). Current firmware target: `xiao_128x32_i2c` (4-pin I2C OLED).

## Firmware pin map (already reserved — DO NOT reuse)

| GPIO (silk) | Function            | Notes |
|-------------|---------------------|-------|
| GPIO0 (D0)  | WHEEL_A             | scroll wheel A |
| GPIO4 (D4)  | WHEEL_B             | scroll wheel B |
| GPIO3 (D3)  | BTN_A               | short=select, long=back/stop |
| GPIO5 (D5)  | BTN_B               | cancel/back |
| GPIO40/41/42| MIC (onboard)       | I2S, do not touch |
| GPIO21/7/8/9| SD (onboard slot)   | CS=21, SCK=7, MISO=8, MOSI=9 |
| GPIO43 (D6) | I2C SDA             | shared screen + gyro bus |
| GPIO44 (D7) | I2C SCL             | shared screen + gyro bus |

Free GPIOs for expansion: GPIO1 (D1), GPIO2 (D2), GPIO6 (D5-silk),
GPIO10–20, GPIO38/39/45–48.

## Display — 4-pin I2C OLED (128×32)

Default build target. Firmware: `SCREEN_128x32_I2C`, I2C on D6/D7.

| OLED pin | XIAO pad | GPIO |
|----------|----------|------|
| VCC      | 3V3      | —    |
| GND      | GND      | —    |
| SDA      | D6       | 43   |
| SCL      | D7       | 44   |

- 3.3 V native, no level shifter, no reset pin needed (`rst_pin=-1`).
- Address 0x3C default. If the panel stays **blank**, flip to 0x3D in
  `firmware/lib/cyclops_shared/include/screens.h` (`addr_` ctor param) and rebuild.
- Build/flash:
  ```
  cd firmware && . .venv/bin/activate
  pio run -e xiao_128x32_i2c -t upload --upload-port /dev/ttyACM0
  ```

## Gyroscope / IMU — I2C (shared bus)

Use an **I2C** breakout (MPU-6050 or LSM6DS3). It hangs on the same D6/D7 bus as
the screen; devices are distinguished by I2C address, so no extra bus needed.

| IMU pin | XIAO pad | GPIO |
|---------|----------|------|
| VCC     | 3V3      | —    |
| GND     | GND      | —    |
| SDA     | D6       | 43   |
| SCL     | D7       | 44   |
| INT     | D1       | 1    |  (optional: tap/double-tap IRQ)
| ADDR    | —        | —    |  (float or pull to set 2nd addr if needed)

- Typical addresses: MPU-6050 = 0x68 / 0x69, LSM6DS3 = 0x6A / 0x6B.
  OLED = 0x3C, so no clash in the common case.
- The XIAO S3 Sense **onboard** LSM6DS3 sits on the *default* I2C bus
  (GPIO5/6), which collides with **BTN_B (GPIO5)**. Do NOT use the onboard
  IMU without first moving BTN_B to a free pin. The external IMU on D6/D7
  (above) avoids this entirely.

## Reserved — leave these alone

- Wheel + buttons: GPIO0/3/4/5 (firmware live).
- Screen + gyro: GPIO43/44 I2C bus.
- SD: GPIO21/7/8/9 (onboard Sense slot; FAT32 card ≤32 GB).
- Mic: GPIO40/41/42.

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
| `xiao_st7735`       | ST7735 128×128 SPI  | CS=GPIO6, DC=GPIO2, RST=GPIO1 |
| `xiao_128x64`       | SSD1306 128×64 SPI  | |
| `xiao_128x32`       | SSD1306 128×32 SPI  | |
| `xiao_128x32_i2c`   | SSD1306 128×32 I2C  | **current**; `-DENABLE_RING=1 -DENABLE_IMU=1`, SD logging on |

Flash any: `pio run -e <env> -t upload --upload-port /dev/ttyACM0`.

## SD logging (on by default in i2c build)

- Mounts `/sdcard` on the onboard slot. FAT32 card ≤32 GB.
- Appends timestamped lines to `/sdcard/cyclops.log`: notes, health samples,
  rec start/stop.
- If no card: boots with `[boot] sd card NOT present (logging disabled)`.
