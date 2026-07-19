# Wiring guide (from zero)

Canonical wiring for the current minimal builds. Supersedes `12-wiring.md` and
`32-wiring.md`. Two devices:

- **Cyclops** — XIAO ESP32-S3 wearable: 128×32 screen, **1 button**, scrollwheel,
  **onboard LED** as REC indicator, onboard mic. BLE to phone.
- **CyclUno** — Arduino dev unit, now **two boards**: a *controller* (2 joysticks,
  2 buttons, 128×32 OLED) that streams the HUD over one wire to a *display board*
  driving a big 128×128 TFT.

Pin labels are the board silk (XIAO `Dn`, Uno `Dn`/`An`). Everything below matches
the firmware as built: `firmware/xiao/src/main.cpp`, `firmware/cycluno/main.cpp`,
`firmware/cyclobig/main.cpp`.

---

## 1. Cyclops wearable — XIAO ESP32-S3 Sense

Firmware env: `xiao_128x32` (default). Screen is an **SPI SSD1306 128×32**.
Mic, LED and SD are all onboard — no wires for those.

### 1.1 Pin map

| XIAO pad | GPIO | Function | Notes |
|----------|------|----------|-------|
| D0  | 0  | Wheel A | quadrature, ISR on CHANGE, pull-up |
| D4  | 4  | Wheel B | quadrature, pull-up |
| D3  | 3  | **BTN_A** | the only button. single=OK, double=photo, long=video |
| D8  | —  | SPI SCK  | screen |
| D10 | —  | SPI MOSI | screen |
| D9  | —  | SPI MISO | screen |
| D5  | —  | screen CS | |
| D2  | —  | screen DC | |
| D1  | —  | screen RST | |
| —   | 21 | **REC LED** | onboard user LED (active-LOW). No wire. |
| —   | 42/41 | Mic PDM clk/data | onboard MSM261D. No wire. |
| USB-C / BAT | — | power + charge | Li-Po on BAT pad for untethered |

> **SD card is disabled on this build.** The onboard SD slot's CS is GPIO21 —
> the same pin now driving the REC LED. SD is only wired on the I2C-OLED
> variant anyway.

### 1.2 Screen — SSD1306 128×32 (SPI, 7 wires)

| OLED pin | XIAO pad |
|----------|----------|
| VCC | 3V3 |
| GND | GND |
| SCK / CLK | D8 |
| MOSI / DIN | D10 |
| CS  | D5 |
| DC  | D2 |
| RST | D1 |

(MISO=D9 is reserved by the SPI bus but the OLED doesn't drive it.)

*Fewer wires?* Build `xiao_128x32_i2c` instead and wire only VCC / GND /
SDA=D6 / SCL=D7 (4 wires). Same firmware behavior; only the screen bus changes.

### 1.3 Button + wheel

```
   BTN_A ── D3 ───┐
                  ├── (internal pull-up, active-LOW)
   button  ── GND ┘

   Scrollwheel (rotary encoder):
     A  ── D0
     B  ── D4
     C  ── GND      (common)
```

Button B is gone. Navigation = scrollwheel, selection = BTN_A. The old B
gestures (back / voice-note / voice-cmd) are no longer bound.

### 1.4 LED

Onboard user LED (GPIO21, active-LOW). Lights while recording. Nothing to
solder.

### 1.5 Joystick variant (optional)

Firmware env: `xiao_128x32_joy` (adds `-DINPUT_JOYSTICK`, uses the **I2C**
128×32 screen so the SPI pins stay free for the ADC lines). The joystick sits
**alongside** the scrollwheel — the wheel is not removed.

| Joystick pin | GPIO | XIAO silk | Function |
|--------------|------|-----------|----------|
| VRx | 1 | D1 | reserved (read, unused) |
| VRy | 2 | D2 | scroll (center-locked steps) |
| SW  | 6 | D5 | push = button A (single/double/long) |
| +5V/VCC | — | 3V3 | |
| GND | — | GND | |

Screen must be the 4-pin I2C OLED for this variant: VCC/GND/SDA=D6/SCL=D7.
Wheel (D0/D4) and BTN_A (D3) stay wired as in §1.3; the joystick push is a
second source of the same button-A gestures. Override `PIN_JOY_X/Y/SW` at
build time if you wired different pins.

---

## 2. CyclUno — controller board (Arduino Uno)

Firmware env: `cycluno`. Holds all HUD state. Talks to the brain over USB and
mirrors the 4 HUD rows to the display board over one wire.

### 2.1 Pin map

| Uno pin | Function | Notes |
|---------|----------|-------|
| A0 | Joystick 1 VRx | ADC |
| A1 | Joystick 1 VRy | ADC (scroll) |
| D2 | Joystick 1 SW → **Button A** | select / REC, active-LOW pull-up |
| A2 | Joystick 2 VRx | ADC |
| A3 | Joystick 2 VRy | ADC (scroll) |
| D3 | Joystick 2 SW → **Button B** | menu / back, active-LOW pull-up |
| A4 | OLED SDA | I2C |
| A5 | OLED SCL | I2C |
| D4 | Link TX → display board | SoftwareSerial, 19200, one-way |
| D0/D1 | USB serial | to the brain (115200). Do not reuse. |

No LEDs. No extra buttons. The two joystick pushes **are** the two buttons.
"Ask agent" and "Home" moved into the on-screen MENU (press B, then A).

**Headless option** (`env:cycluno_headless`, `-DNO_LOCAL_OLED`): drop the local
128×32 OLED entirely — A4/A5 left unwired — and rely only on the big-display
board. Same pin map minus the OLED rows. Pure input board: 2 joysticks + the
link out.

### 2.2 OLED — SSD1306 128×32 (I2C, addr 0x3C)

| OLED pin | Uno pin |
|----------|---------|
| VCC | 5V |
| GND | GND |
| SDA | A4 |
| SCL | A5 |

### 2.3 Joysticks (2× HW-504)

```
   Joystick 1                 Joystick 2
     +5V  ── 5V                 +5V  ── 5V
     GND  ── GND                GND  ── GND
     VRx  ── A0                 VRx  ── A2
     VRy  ── A1                 VRy  ── A3
     SW   ── D2  (= Button A)   SW   ── D3  (= Button B)
```

### 2.4 Link to the display board

```
   controller D4 (TX) ───────────> display board D2 (RX)
   controller GND     ───────────  display board GND
```

One wire + common ground. Data flows controller → display only.

---

## 3. CyclUno — display board (second Arduino Uno)

Firmware env: `cyclobig`. Stateless. Renders the 4 rows it receives on a big
**ST7735 128×128** TFT.

### 3.1 Pin map

| Uno pin | Function |
|---------|----------|
| D2 | Link RX ← controller D4 |
| D11 | SPI MOSI → TFT |
| D13 | SPI SCK → TFT |
| D10 | TFT CS |
| D9  | TFT DC |
| D8  | TFT RST |

### 3.2 ST7735 128×128 (SPI)

| TFT pin | Uno pin | Notes |
|---------|---------|-------|
| VCC | 3.3V | **not 5V** |
| GND | GND | |
| SCK | D13 | |
| SDA / MOSI | D11 | |
| CS  | D10 | |
| DC / A0 | D9 | |
| RST | D8 | |
| BL / LED | 3.3V | backlight (via resistor if the module lacks one) |

> **Logic levels.** The Uno drives 5V logic; most ST7735 breakouts are 3.3V.
> Use a level shifter (or series resistors) on SCK/MOSI/CS/DC/RST unless the
> module is explicitly marked 5V-tolerant. Power VCC from 3.3V.

---

## 4. Wiring at a glance

```
  ┌─────────────── Cyclops (XIAO S3) ───────────────┐
  │  wheel(D0/D4)  BTN_A(D3)  OLED-SPI  mic+LED+SD   │
  │  ───────────── all onboard except wheel/btn ──── │
  │                     ⇅ BLE                         │
  │                   phone / brain                   │
  └───────────────────────────────────────────────────┘

  ┌──────── CyclUno controller (Uno) ────────┐        ┌──── display board (Uno) ────┐
  │  Joy1(A0/A1/D2=A)  Joy2(A2/A3/D3=B)       │        │                              │
  │  OLED 128×32 I2C (A4/A5)                  │        │  ST7735 128×128 SPI          │
  │  USB ⇄ brain                              │        │  (D8/D9/D10/D11/D13)         │
  │  D4 ─────────────── link (19200) ─────────┼───────>│  D2                          │
  │  GND ─────────────────────────────────────┼────────│  GND                         │
  └───────────────────────────────────────────┘        └──────────────────────────────┘
```

---

## 5. Verify

```
cd firmware
make test proto                        # host logic + wire-protocol tests
pio run -e cycluno -e cyclobig         # both Uno boards
pio run -e xiao_128x32                 # cyclops wearable
```
