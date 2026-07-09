# Cyclops — XIAO ESP32-S3 Sense Schematic

Wearable capture + HUD unit. This is the **audio-capturing** brain-board: the
onboard MEMS mic feeds I2S → BLE audio chunks → phone transcribes. The same
board also drives the glanceable OLED and reads the Colmi R02 ring over BLE.

- Firmware: `firmware/xiao/src/main.cpp`, board `seeed_xiao_esp32s3`,
  platform `espressif32`, framework `arduino`.
- Build: `pio run -e xiao_st7735 | xiao_128x64 | xiao_128x32`
  (pick the screen at compile time via `-DSCREEN_*`).

## Pin map (Seeed XIAO ESP32-S3)

| Function            | GPIO | Note                                         |
|---------------------|------|----------------------------------------------|
| I2S BCLK (MIC)      | 40   | onboard MEMS mic (MP34DT05-class), no wire   |
| I2S WS   (MIC)      | 41   |                                              |
| I2S DIN  (MIC)      | 42   |                                              |
| SPI SCK  (screen)   | 8    | default VSPI on XIAO S3                      |
| SPI MOSI (screen)   | 10   |                                              |
| SPI MISO (screen)   | 9    |                                              |
| Screen CS (ST7735)  | 7    | `SCREEN_ST7735` build                        |
| Screen CS (128x64)  | 6    | `SCREEN_128x64` build                        |
| Screen CS (128x32)  | 5    | `SCREEN_128x32` build                        |
| Screen DC           | 2    | all SPI screens                              |
| Screen RST          | 1    | all SPI screens                              |
| BTN_A               | 3    | active-low, INPUT_PULLUP                     |
| BTN_B               | 5    | active-low (conflicts w/ 128x32 CS — alt bld)|
| Wheel A (quad)      | 0    | = onboard BOOT button (also used as wheel)   |
| Wheel B (quad)      | 4    |                                              |
| BLE radio           | —    | onboard antenna, NimBLE (no pins)            |
| USB-C               | —    | 5 V power + UART/flash                        |
| LiPo / BAT pad      | —    | battery input (charge IC onboard)            |

> The I2S mic is **on the S3 Sense module** — no external mic to wire. If you
> use a plain XIAO ESP32-S3 (no Sense), add an INMP441-style MEMS mic:
> `VCC→3V3, GND→GND, BCLK→40, WS→41, DOUT→42`.

## Wiring diagram (ST7735 default build)

```
                 XIAO ESP32-S3 SENSE
             +-----------------------------+
   USB-C  -> |[USB]                  o ANT |  (BLE)
             |                      [o]BOOT|<- GPIO0 = WHEEL_A
   LiPo ->   |[BAT]                 [ ]3V3 |<- SPI MOSI (to screen)
             | 40 BCLK  41 WS  42 DIN       |   (onboard mic)
             |                             |
             | 8 SCK   10 MOSI  9 MISO     |---- SPI to OLED
             | 7 CS    2 DC    1 RST       |---- SPI to OLED
             | 3 BTN_A  5 BTN_B  4 WHEEL_B |
             +--------------+--------------+
                            |
                  ST7735 1.8" TFT (SPI)
              +---------------------------+
    XIAO GPIO | pin | ST7735
        8 SCK | SCK |
       10 MOSI| MOSI/SDA
        9 MISO| MISO/SDO  (nc)
        7 CS  | CS
        2 DC  | DC/A0
        1 RST | RES/RESET
       3V3    | VCC        (3.3 V — do NOT use 5 V)
       GND    | GND
              +---------------------------+
```

## Power

- USB-C: 5 V, ~80–120 mA with screen + BLE + mic.
- LiPo: connect to BAT pad; the S3 Sense has an onboard charge IC (JST-1.25
  or soldered pad depending on revision). Charge current ~100 mA.
- Screen is 3.3 V logic — the XIAO is 3.3 V, so wire VCC→3V3 directly.

## Controls

- BTN_A (GPIO3) short = select; long = back/stop capture.
- BTN_B (GPIO5) short = cancel/back.
- Wheel A/B (GPIO0/4): quadrature scroll for menu navigation.
- Ring (Colmi R02): paired over BLE by the firmware (`ENABLE_RING`); HR/SpO2
  flow into `hud.set_health()` and show on the status bar.

## Notes / gotchas

- GPIO0 is the boot pin: holding it at boot enters flash mode. Using it as
  WHEEL_A is fine at runtime; don't hold during power-up.
- `MIC_BCLK/WS/DIN` are overridable via `-D` if you move the mic.
- Screen CS differs per build (`-DSCREEN_*`); BTN_B (GPIO5) overlaps the
  128x32 CS — pick one role per build.
- Enclosure CAD: `cad/cyclops_xiao_enclosure.scad`.
