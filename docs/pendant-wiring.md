# Cyclops Pendant — Wiring

Pendant form-factor wearable: teardrop case housing a XIAO ESP32-S3 Sense + I2C OLED +
EC11 crown wheel + side button + external IMU (MPU-6050/LSM6DS3) + Li-Po.

Current firmware target: `xiao_128x32_i2c` (I2C OLED, no SPI screen pins).

## Pin map

| XIAO pad | GPIO | Function | Wire to |
|----------|------|----------|---------|
| D0 | 0 | WHEEL_A | EC11 encoder pin A. **Don't hold at boot** (enters flash) |
| D4 | 4 | WHEEL_B | EC11 encoder pin B |
| D3 | 3 | BTN_A | side button SIG. Short=select, long>600ms=back/stop |
| D5 | 5 | BTN_B | side button SIG (cancel/back) — also used as IMU IRQ alt if only 1 button |
| D6 | 43 | I2C SDA | shared bus: OLED SDA + IMU SDA |
| D7 | 44 | I2C SCL | shared bus: OLED SCL + IMU SCL |
| D1 | 1 | IMU INT (opt) | MPU-6050 INT pin |
| 3V3 | — | 3.3 V | OLED VCC + IMU VCC + encoder + |
| GND | — | GND | all grounds |
| BAT | — | Li-Po + | 302030 battery through charge/protect |
| USB-C | — | 5V + data | flash + charge |

## Wire-by-wire

### OLED — I2C SSD1306 128×32 (4-pin, blue board, addr 0x3C)
| OLED | XIAO |
|------|------|
| VCC  | 3V3  |
| GND  | GND  |
| SDA  | D6   |
| SCL  | D7   |

If blank → try addr 0x3D in `firmware/lib/cyclops_shared/include/screens.h`.

### IMU — MPU-6050 / LSM6DS3 (I2C breakout, shared D6/D7 bus)
| IMU  | XIAO |
|------|------|
| VCC  | 3V3  |
| GND  | GND  |
| SDA  | D6   |
| SCL  | D7   |
| INT  | D1   (optional — tap/double-tap IRQ) |

Addr: MPU-6050 = 0x68, LSM6DS3 = 0x6A. No clash with OLED (0x3C).

**Do NOT use the XIAO S3 Sense onboard IMU** — its default I2C bus (GPIO5/6)
collides with BTN_B (GPIO5). The external IMU on D6/D7 avoids this.

### Wheel — EC11 rotary encoder
| EC11 | XIAO |
|------|------|
| A    | D0   |
| B    | D4   |
| COM  | GND  |
| SW   | D3   (optional, = BTN_A press) |

### Side button(s)
| Button | XIAO |
|--------|------|
| SIG    | D3   (BTN_A: select/long=back) |
| GND    | GND  |

No VCC wire — internal `INPUT_PULLUP` provides logic HIGH.
Pendant case has 4 tact holes (2 per side). Second button → D5 (BTN_B: cancel/back).

### Battery — 302030 Li-Po 3.7 V
| Li-Po | XIAO |
|-------|------|
| +     | BAT  (through charge/protect) |
| -     | GND  |

XIAO onboard charger tops from USB-C. Keep total draw < 300 mA.

## Build & flash
```
cd firmware
pio run -e xiao_128x32_i2c -t upload
```

The `xiao_128x32_i2c` env enables `-DENABLE_RING=1 -DENABLE_IMU=1` and SD logging.

## Onboard (no external wiring)
- PDM mic: CLK=GPIO42, DATA=GPIO41
- microSD slot: CS=GPIO21, SCK=GPIO7, MISO=GPIO8, MOSI=GPIO9

## Reserved — don't touch
| Pins | Used by |
|------|---------|
| GPIO0/4 | wheel |
| GPIO3/5 | buttons |
| GPIO43/44 | I2C (screen + IMU) |
| GPIO21/7/8/9 | SD (onboard) |
| GPIO40/41/42 | PDM mic (onboard) |

Free: GPIO1 (IMU INT), GPIO2, GPIO6, GPIO10–20, GPIO38/39, GPIO45–48.

## CAD reference
`cad/cyclops_xiao_pendant.scad` — teardrop case with pockets for XIAO, IMU,
battery, EC11 crown wheel, side tacts, LED window, and mic vent.
Print body front-face-down, cap flat.