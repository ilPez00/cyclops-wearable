# Cyclops — Arduino Uno / Nano HUD Schematic (dev unit)

Desktop / development **HUD-only** unit. The ATmega328 (Uno/Nano) has **no
I2S peripheral**, so it cannot capture audio. It is a *display + control*
companion that talks to the brain over **USB-Serial** (the phone/PC runs the
real capture + transcription). Use this board to develop the HUD/menu/scroll
logic without an ESP32.

- Code: `firmware/arduino/src/main.cpp`, board `nanoatmega328` (Uno-class
  ATmega328), framework `arduino`.
- Build: `pio run -e arduino_st7735 | arduino_128x64 | arduino_128x32`.
- Link to brain: `Serial` at 115200 baud (use `SerialFrameReader` on the
  PC, or `Transport` with `kind="serial"`).

## Pin map (ATmega328, Nano/Uno layout)

| Function            | Arduino | AVR GPIO | Note                          |
|---------------------|---------|----------|-------------------------------|
| SPI SCK             | 13      | PB5      | screen SPI clock              |
| SPI MOSI            | 11      | PB3      | screen data                   |
| SPI MISO            | 12      | PB4      | (screen nc)                   |
| Screen CS (ST7735)  | 10      | PB2      | `SCREEN_ST7735` build         |
| Screen CS (128x64)  | 7       | PD7      | `SCREEN_128x64` build         |
| Screen CS (128x32)  | 4       | PD4      | `SCREEN_128x32` build         |
| Screen DC           | 9       | PB1      | all SPI screens               |
| Screen RST          | 8       | PB0      | all SPI screens               |
| BTN_A               | 5       | PD5      | active-low                    |
| BTN_B               | 6       | PD6      | active-low                    |
| Wheel A (quad)      | 2       | PD2      | INT0 — quadrature A           |
| Wheel B (quad)      | 3       | PD3      | INT1 — quadrature B           |
| Wheel BTN           | 4       | PD4      | active-low (alt to 128x32 CS) |
| Joy X (analog)      | A1      | PC1      |                              |
| Joy Y (analog)      | A2      | PC2      |                              |
| Joy BTN             | 7       | PD7      | active-low (alt to 128x64 CS) |
| Prox (analog)       | A0      | PC0      | IR proximity → screen on/off  |
| VBAT (analog)       | A6      | ADC6     | battery sense (divider)       |
| USB-Serial          | 0/1     | PD0/PD1  | TX/RX to brain @ 115200       |

> Pin conflicts: `128x64` CS (D7) == Joy BTN (D7), `128x32` CS (D4) == Wheel
> BTN (D4). Pick one function per build. Prox/joystick are optional (the HUD
> still works without them).

## Wiring diagram (ST7735 default build)

```
        Arduino NANO / UNO (ATmega328)
     +-------------------------------+
  5V |VIN                        VIN| 5V
  GND|GND                        GND| GND
     |D13 SCK  D11 MOSI  D12 MISO |
     |D10 CS    D9 DC     D8 RST  |---- SPI to OLED
     |D5 BTN_A  D6 BTN_B          |
     |D2 WHEEL_A D3 WHEEL_B D4 WB | (quad + wheel btn)
     |A0 PROX  A1 JOY_X  A2 JOY_Y | (analog)
     |A6 VBAT                      |
     |D0 RX    D1 TX  -> brain USB | (115200)
     +--------------+--------------+
                    |
          ST7735 1.8" TFT (SPI)
      +---------------------------+
 XIAO | pin | ST7735
  D13  | SCK |
  D11  | MOSI/SDA
  D12  | MISO/SDO (nc)
  D10  | CS
  D9   | DC/A0
  D8   | RES/RESET
  5V   | VCC  (ST7735 modules are 5 V tolerant on VCC; logic via level shift
       |       on most breakouts — wire 3V3 if your module is 3.3 V only)
  GND  | GND
       +---------------------------+
```

Optional analog controls:
- Joystick: GND + 3V3 to outer legs, wiper → A1 (X) / A2 (Y), press → D7.
- Prox: IR phototransistor / Sharp GP2Y0A divider → A0.
- VBAT: LiPo through 2:1 resistor divider (e.g. 100k+100k) → A6, so
  `Vbat = analogRead(A6) * (5.0/1023) * 2`.

## Controls

- BTN_A — select; BTN_B — back/cancel; Wheel — scroll; Joystick Y — scroll;
  Wheel BTN / Joy BTN — long-back.
- Proximity > 200 → screen on; falls below for ~30 s → screen off (power
  save).

## How it talks to the brain

`arduino/src/main.cpp` frames every command/note/status as a Cyclops wire
frame (magic `0xAA 0xAA 0x55`, len/type/payload/CRC16) and writes it to
`Serial`. On the PC, `device/transport.py::SerialFrameReader` decodes those
frames into `HudBridge`. So this board is a *headless HUD sink + input
source* for the brain — no audio here.

## Notes / gotchas

- No I2S → no audio capture. Audio lives on the XIAO S3 Sense board (see
  `30-schematics-xiao.md`). If you need audio on an Uno-class MCU you must
  add an external I2S codec (e.g. INMP441 + a board with I2S, or a MAX9814
  analog mic → ADC, lower quality).
- 328P has 2 KB RAM — keep strings short; the `add_note` buffer is 64 B.
- Screen CS pin depends on the `SCREEN_*` build flag.
- Enclosure CAD: `cad/cyclops_arduino_enclosure.scad`.
