# Cyclops — Wiring Guide

Single-source reference for every Cyclops hardware variant. Each variant shares the
same firmware core — only the screen driver and pin assignments change per build env.

## Variant quick reference

| Tag | Board | Screen | Bus | Input | Build env | Purpose |
|-----|-------|--------|-----|-------|-----------|---------|
| V1 | Arduino Uno | SSD1306 128×32 I2C | I2C | 2 joysticks + 4 buttons | `cycluno` | Dev/breadboard |
| V2 | Arduino Uno/Nano | ST7735 128×128 SPI | SPI | scrollwheel/joystick + 2 buttons | `arduino_st7735` | Dev HUD |
| V3 | XIAO ESP32-S3 Sense | SSD1306 128×32 I2C | I2C | scrollwheel + 2 buttons | `xiao_128x32_i2c` | Wearable (current) |
| V4 | XIAO ESP32-S3 Sense | 1.51" Transparent OLED | SPI | scrollwheel + 2 buttons | `xiao_transparent_151` | Transparent HUD |

---

## V1 — CyclUno (Arduino Uno dev unit)

**Screen:** I2C SSD1306 128×32 (blue board, 0x3C). **Input:** 2 analog joysticks + 4 buttons.
No rotary encoder, no LEDs — scroll is the joystick Y axis, REC/link state on the OLED only.

### Pin table

| Part | Pin | Uno pin | Notes |
|------|-----|---------|-------|
| OLED SSD1306 I2C | VCC | **5V** | |
| | GND | **GND** | |
| | SDA | **A4** | |
| | SCL | **A5** | |
| | *(7-pin board)* RES | **5V via 10k** | strap pullup |
| | *(7-pin board)* DC | **GND** | strap |
| | *(7-pin board)* CS | **5V** | strap |
| Joystick 1 (primary nav) | VRx | **A0** | analog scroll X |
| | VRy | **A1** | analog scroll Y |
| | SW | **D2** | push = select/REC |
| | + | **5V** | |
| | GND | **GND** | |
| Joystick 2 (secondary) | VRx | **A2** | |
| | VRy | **A3** | |
| | SW | **D3** | push = menu/back |
| | + | **5V** | |
| | GND | **GND** | |
| Button B1 (select/REC) | SIG | **D4** | other leg → GND |
| Button B2 (menu/back) | SIG | **D5** | other leg → GND |
| Button B3 (ask agent) | SIG | **D6** | other leg → GND |
| Button B4 (home) | SIG | **D7** | other leg → GND |

**Buttons need NO VCC wire** — internal `INPUT_PULLUP` provides the logic HIGH.
Joysticks need +5V (pot wiper feeds the ADC).

### Build & run
```
cd firmware
pio run -e cycluno -t upload
python3 demo_cycluno.py
```

### Controls
- J1 Y / scroll — navigate menu
- J1 push or B1 — select / REC toggle on HOME
- J2 push or B2 — menu/back
- B3 — ask agent
- B4 — home

---

## V2 — Arduino Uno/Nano dev HUD

**Screen:** SPI ST7735 128×128 (3.3 V logic, 5 V-tolerant VCC). **Input:** scrollwheel OR
joystick + 2 buttons. No I2S (no audio capture) — HUD+input only, brain link over USB serial.

### Pin table

| Signal | Arduino pin | AVR GPIO | Notes |
|--------|-------------|----------|-------|
| SPI SCK | **D13** | PB5 | |
| SPI MOSI | **D11** | PB3 | |
| SPI MISO | **D12** | PB4 | unused |
| Screen CS (ST7735) | **D10** | PB2 | |
| Screen CS (128×64) | **D7** | PD7 | alt build |
| Screen CS (128×32) | **D4** | PD4 | alt build |
| Screen DC | **D9** | PB1 | all SPI screens |
| Screen RST | **D8** | PB0 | all SPI screens |
| BTN_A | **D5** | PD5 | active-low, pullup |
| BTN_B | **D6** | PD6 | active-low, pullup |
| Wheel A | **D2** | PD2 | INT0, quadrature |
| Wheel B | **D3** | PD3 | INT1, quadrature |
| Wheel push | **D4b** | PD4 | alt 128×32 CS |
| Joy X | **A1** | PC1 | analog |
| Joy Y | **A2** | PC2 | analog |
| Joy push | **D7b** | PD7 | alt 128×64 CS |
| Prox (opt) | **A0** | PC0 | IR → screen on/off |
| VBAT (opt) | **A6** | ADC6 | divider |
| USB serial | **D0/D1** | PD0/PD1 | TX/RX → brain @115200 |

**Pin conflict warning:**
- 128×64 build: CS(D7) = Joy push — pick one
- 128×32 build: CS(D4) = Wheel push — pick one

### Build
```
pio run -e arduino_st7735       # or arduino_128x64 | arduino_128x32
```

### Screen wiring (ST7735)
| ST7735 pin | Arduino |
|------------|---------|
| SCK | D13 |
| MOSI/SDA | D11 |
| MISO/SDO | D12 (nc) |
| CS | D10 |
| DC/A0 | D9 |
| RES/RST | D8 |
| VCC | 5V or 3V3 |
| GND | GND |

---

## V3 — XIAO wearable (I2C OLED) — current primary build

**Board:** Seeed XIAO ESP32-S3 Sense (onboard PDM mic + microSD slot).
**Screen:** 4-pin I2C SSD1306 128×32 (VCC/GND/SCL/SDA, addr 0x3C).
**Input:** scrollwheel + 2 buttons. Optional I2C IMU on shared bus.

### Pin table

| XIAO pad | GPIO | Function | Notes |
|----------|------|----------|-------|
| D0 | 0 | WHEEL_A | quadrature A; ISR on CHANGE. **Don't hold at boot** (enters flash mode) |
| D4 | 4 | WHEEL_B | quadrature B |
| D3 | 3 | BTN_A | short=select, long>600ms=back/stop. INPUT_PULLUP |
| D5 | 5 | BTN_B | cancel/back. INPUT_PULLUP. **Was D4 (bug — aliased WHEEL_B)** |
| D6 | 43 | I2C SDA | shared screen + optional IMU bus |
| D7 | 44 | I2C SCL | shared screen + optional IMU bus |
| D1 | 1 | IMU INT (opt) | optional tap/double-tap IRQ |
| 3V3 | — | OLED VCC | 3.3 V, no level shifter |
| GND | — | OLED GND | |
| USB-C | — | 5V + data + flash | |
| BAT | — | Li-Po + (opt) | through charge/protect |

### Onboard (no wires needed)
| Peripheral | Pins |
|-----------|------|
| PDM mic | CLK=GPIO42, DATA=GPIO41 |
| microSD | CS=GPIO21, SCK=GPIO7, MISO=GPIO8, MOSI=GPIO9 |

### Screen wiring (I2C OLED)
| OLED pin | XIAO pad | GPIO |
|----------|----------|------|
| VCC | **3V3** | — |
| GND | **GND** | — |
| SDA | **D6** | 43 |
| SCL | **D7** | 44 |

No reset pin needed (`rst_pin=-1`). If blank, try addr 0x3D in `screens.h`.

### Optional I2C IMU (MPU-6050 / LSM6DS3)
Shares D6/D7 with the OLED — devices distinguished by I2C address (no clash:
OLED=0x3C, MPU=0x68/0x69, LSM6DS3=0x6A/0x6B). Optional INT → D1.

### Build
```
cd firmware
pio run -e xiao_128x32_i2c -t upload --upload-port /dev/ttyACM0
```

The `xiao_128x32_i2c` env in `platformio.ini` enables `-DENABLE_RING=1 -DENABLE_IMU=1`
and SD logging. The bulk of this build (everything except the screen + input wiring)
is onboard — no external mic, SD, or camera wiring.

### Reserved — don't reuse
- GPIO0/3/4/5 — wheel + buttons (firmware live)
- GPIO43/44 — I2C bus (screen + gyro)
- GPIO21/7/8/9 — SD slot
- GPIO40/41/42 — PDM mic
- GPIO1 — optional IMU INT

Free for expansion: GPIO2 (D2), GPIO6, GPIO10–20, GPIO38/39, GPIO45–48.

### Battery (optional)
BAT+ → 100k → GPIO2 (D2) → 100k → GND for voltage sense.

---

## V4 — XIAO Transparent OLED (Waveshare 1.51")

**Board:** Seeed XIAO ESP32-S3 Sense. **Screen:** Waveshare 1.51" Transparent OLED
(128×64, SSD1309 controller, 4-wire SPI). Unlit pixels = transparent glass.
**Input:** scrollwheel + 2 buttons.

### Pin table (SPI mode)

| XIAO pad | GPIO | Transparent OLED | Notes |
|----------|------|------------------|-------|
| D10 | 9 | **MOSI/DIN** | SPI data |
| D8 | 7 | **SCK/CLK** | SPI clock |
| D5 | 6 | **CS** | |
| D1 | 2 | **DC** | |
| D0 | 1 | **RST** | |
| 3V3 | — | **VCC** | EXTVCC boost |
| GND | — | **GND** | |
| D0w | 0 | WHEEL_A | rotary encoder |
| D4 | 4 | WHEEL_B | rotary encoder |
| D3 | 3 | BTN_A | pullup |
| D5b | 5 | BTN_B | pullup |

### Build (SPI)
```
cd firmware
pio run -e xiao_transparent_151 -t upload
```

### I2C variant
Move the two solder resistors on the module per Waveshare wiki, then build:
```
pio run -e xiao_transparent_151_i2c -t upload
```
I2C frees SPI pins: SDA→D6, SCL→D7 (GPIO43/44). No CS/DC/RST wires.

### Transparent render notes
- `begin(SSD1306_EXTERNALVCC, 0x3C)` — external boost, not charge pump
- `dim(false)` — max brightness (panels are dim in daylight)
- Filled "off" rectangles are no-ops — unlit pixels stay clear glass

---

## Common to all XIAO variants

### Power budget
Keep total draw **< 300 mA** (ESP32 + screen + mic + ring BLE client).
- **Tethered:** USB-C 5 V, no battery circuit
- **Untethered:** 3.7 V Li-Po → BAT pad through charge/protect; onboard charger
  tops from USB-C

### COLMI R02 ring (BLE, no wires)
Scan for `R02_*`, connect service `6E40FFF0-…-E50E24DCCA9E`, subscribe TX
`6E400003-…`, write to RX `6E400002-…`. Enabled with `-DENABLE_RING=1` in build flags.

### Flashing notes
- XIAO: double-tap reset to enter UF2 bootloader, or use `pio run -e <env> -t upload`
- Arduino Uno: auto-detected by PlatformIO

### Full visual reference
Generated diagrams in `docs/`:
- `cyclops_wiring.pdf` — all four variants (one per page)
- `cyclops_wiring.svg` — combined SVG
- `cyclops_wiring.png` — combined PNG
- `cyclops_v1_CyclUno_EXPANDED.png` — 3x scale CyclUno poster
- `cyclops_v1_CyclUno_ASSEMBLY.png` — top-down finished-board drawing
- Per-variant PNGs: `cyclops_v1_*.png` through `cyclops_v4_*.png`