# Cyclops Wiring Guide — 2 buttons + 4-pin I2C screen + accelerometer

> Target: XIAO ESP32-S3 Sense. Build env: `xiao_128x32_i2c`.
> **No scroll wheel, no BLE ring** — only what you listed.

---

## 1. Pin map (reserved — DO NOT reuse)

| GPIO (silk) | Function | Notes |
|---|---|---|
| GPIO3 (D3) | BTN_A | short=OK/select, long=back |
| GPIO5 (D5) | BTN_B | cancel/back |
| GPIO43 (D6) | I2C SDA | shared: screen + gyro |
| GPIO44 (D7) | I2C SCL | shared: screen + gyro |
| GPIO1 (D1) | IMU INT | optional: tap IRQ |

Free GPIOs for expansion: GPIO0, GPIO2, GPIO4, GPIO6, GPIO10–20, GPIO38/39/45–48.
(Mic GPIO40/41/42 and SD GPIO21/7/8/9 reserved by onboard hardware.)

---

## 2. Screen — 4-pin I2C OLED (128×32 SSD1306)

```
OLED VCC → XIAO 3V3
OLED GND → XIAO GND
OLED SDA → XIAO D6 (GPIO43)
OLED SCL → XIAO D7 (GPIO44)
```

- 3.3V native, no level shifter, no reset pin.
- I2C addr `0x3C` default; flip to `0x3D` in `screens.h` if blank.
- Build: `pio run -e xiao_128x32_i2c -t upload`

---

## 3. Accelerometer — MPU-6050 / LSM6DS3 (I2C, same bus)

```
IMU VCC → XIAO 3V3
IMU GND → XIAO GND
IMU SDA → XIAO D6 (GPIO43)
IMU SCL → XIAO D7 (GPIO44)
IMU INT → XIAO D1 (GPIO1)  [optional]
```

Typical addresses: MPU-6050 = 0x68 / 0x69, LSM6DS3 = 0x6A / 0x6B. OLED is 0x3C, no clash.

**Onboard LSM6DS3 warning:** the Sense onboard IMU sits on GPIO5/6, which collides with BTN_B. Use the **external** IMU on D6/D7 above instead.

---

## 4. 2 Buttons

```
BTN_A: GPIO3 (D3) ── button ── GND   [INPUT_PULLUP]
BTN_B: GPIO5 (D5) ── button ── GND   [INPUT_PULLUP]
```

Active-low (press=0, release=1). Debounced by `GestureDetector`.

| Gesture | BTN_A | BTN_B |
|---|---|---|
| Single click | OK / select | Back / cancel |
| Double click | Photo | Voice note |
| Long press | Video | Voice command |

Remappable via `DISPLAY_CMD {"kind":"bind","btn":0,"g":1,"act":N}`.

---

## 5. Battery (optional)

The Sense has an onboard charger but no fuel-gauge ADC. Add a divider:

```
BAT+ ── 100kΩ ── GPIO2 (D2) ── 100kΩ ── GND
```

GPIO2 is free (no scroll wheel). Firmware support: `-DENABLE_BATT=1` (not enabled by default).

---

## 6. Full ASCII layout

```
              XIAO ESP32-S3 SENSE
   ┌──────────────────────────────────────────┐
   │  USB-C                                     │
   │                                            │
   │  OLED 128x32 (I2C) ── SDA→D6  SCL→D7       │
   │  GYRO (I2C)        ── SDA→D6  SCL→D7       │
   │  GYRO INT (opt)     ── D1                  │
   │                                            │
   │  BTN_A→D3   BTN_B→D5                       │
   │  BAT sense→D2 (opt, divider)              │
   │  SD (onboard, GPIO21/7/8/9)               │
   │  MIC (onboard, GPIO40/41/42)              │
   └──────────────────────────────────────────┘
```

---

## 7. Build & flash

```bash
cd ~/dev/cyclops-wearable
pio run -e xiao_128x32_i2c -t upload --upload-port /dev/ttyACM0
```

---

## 8. Wire protocol (v2 framing)

Protocol over USB serial, `cyclops_shared.h`:

- Frame: `[0xAA][0x55][type][len][payload...][crc]`
- `MSG_INPUT_EVENT` (type 3): 4-byte LE int16
  - `src`: 0=JOY1, 1=JOY2, 3=BTN, 4=MODE
  - `btn codes`: 0=A, 1=B (val 1=down, 0=up)
  - `joy codes`: 0=step-x, 1=step-y, 2=raw-x, 3=raw-y
- `MSG_DISPLAY_CMD` (type 5): JSON → HUD state
- `MSG_NOTE` (type 6): text note from brain
- `MSG_HEALTH_SAMPLE` (type 8): HR/SpO2/battery from ring (unused here)

---

## 9. Run the brain

```bash
cd ~/dev/cyclops-wearable
python3 demo_cycluno.py    # auto-detects /dev/ttyACM*|ttyUSB*
```

---

## 10. Common failures

| Symptom | Check |
|---|---|
| OLED blank | SDA/SCL swap, wrong I2C addr (try 0x3D), missing VCC |
| I2C devices not found | `i2cdetect -y 0` — look for 0x3C (OLED) and 0x68 (IMU) |
| IMU WHOAMI 0xFF | Wrong addr (try 0x69), SDA/SCL swap |
| Buttons no response | Verify D3/D5 to GND, INPUT_PULLUP in firmware |
| Battery always 0 | Divider not wired, or ENABLE_BATT not compiled |
| Battery value wrong | Check resistor values (100k/100k = ÷2, 3.6V full → 1.8V at ADC) |

---

## 11. Reference code

- `firmware/xiao/src/main.cpp` — firmware entry, pin setup
- `firmware/xiao/src/imu.cpp` — MPU-6050/9250/ICM-206xx driver
- `firmware/lib/cyclops_shared/include/screens.h` — screen drivers
- `firmware/lib/cyclops_shared/include/hud.h` — HUD + button bindings
- `firmware/lib/cyclops_shared/include/cyclops_shared.h` — frame protocol
