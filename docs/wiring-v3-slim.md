# Cyclops V3-slim — wiring (single target)

Board: XIAO ESP32-S3 Sense (onboard OV2640 cam + PDM mic + SD slot).
External: HW-123 accel + 4-pin I2C SSD1306 128x32 OLED + 2 buttons + battery divider.
Vision: cyclops + app = single access point (through physis) to computer, internet, AI.

```
XIAO pad  GPIO   → what
D3        3      BTN_A (eye: OK/photo/video), INPUT_PULLUP, to GND
D5        5      BTN_B (ear: back/voice-note/voice-cmd), INPUT_PULLUP, to GND
D6        43     I2C SDA → OLED SDA + HW-123 SDA (shared bus)
D7        44     I2C SCL → OLED SCL + HW-123 SCL (shared bus)
D2        2      BAT sense: BAT+ --100k--> D2 --100k--> GND (÷2)
3V3       —      OLED VCC + HW-123 VCC
GND       —      OLED GND + HW-123 GND + buttons GND + divider GND
5V        —      USB-C tether (dev/flash/charge)
BAT pad   —      3.7V Li-Po + (optional, untethered runtime)
```

Onboard (no wires): OV2640 cam (XCLK10/SIOD40/SIOC39/…), PDM mic (CLK42/DATA41 @16kHz),
SD slot (CS21/SCK7/MISO8/MOSI9 — free because the screen is I2C, not SPI).

Reserved — don't reuse: GPIO3/5 buttons, GPIO43/44 I2C, GPIO21/7/8/9 SD,
GPIO40/41/42 mic, GPIO1 IMU INT (opt), GPIO2 battery.
Free: GPIO6, GPIO10–20, GPIO38/39, GPIO45–48.

2×3 button grid: A single=OK double=photo long=video; B single=back
double=voice-note long=voice-cmd (remappable via DISPLAY_CMD bind).

Build: `cd firmware && pio run -e xiao_128x32_i2c -t upload`.
