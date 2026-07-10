# Cyclops — Wiring (XIAO + peripherals)

> **RECONSTRUCTED DOC** — original `docs/12-wiring.md` (2026-07-08) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `firmware/xiao/src/main.cpp`, `docs/01-hardware.md`, `docs/22-screens-plan.md`,
> `docs/30-colmi-r02-integration.md`. **[inferred]** = reconstructed. This is
> the consolidated pin/signal reference (the ring "wiring" is BLE, not solder).

## 0. Two things called "wiring"

1. **XIAO ↔ peripherals** (screen, wheel, buttons, mic, battery) — real wires.
2. **XIAO ↔ COLMI R02 ring** — **no wires**; it's a BLE GATT link
   (see `30-colmi-r02-integration.md`). "Wiring the ring" = software connect.

## 1. XIAO ESP32-S3 Sense — pin map (verified by compile)

```
  XIAO ESP32-S3 Sense          Function              Notes
  ─────────────────────────────────────────────────────────────────────
  D0  ── wheel A (quad)        scroll input          INT on CHANGE
  D4  ── wheel B (quad)        scroll input
  D3  ── BTN_A (pull-up)      select (short) / back (long >600 ms)
  D5  ── BTN_B (pull-up)      cancel / back one level   (was D4; moved to free GPIO5)
  D8  ── SPI SCK               screen (VSPI)
  D10 ── SPI MOSI              screen
  D9  ── SPI MISO              screen
  D7/D6/D5 ── screen CS        (panel-selected)
  D2  ── screen DC             all panels
  D1  ── screen RST            all panels
  40/41/42 ── I2S BCLK/WS/DIN mic capture (onboard pad)
  5V / GND ── USB-C            power + data + charge
  BAT (pad) ── Li-Po + (optional)   untethered runtime
```

## 2. Screen wiring (one panel, compile-selected)

| Panel | CS | DC | RST | SPI |
|-------|----|----|-----|-----|
| ST7735 128×128 | D7 | D2 | D1 | SCK=D8 MOSI=D10 MISO=D9 |
| SSD1306 128×64 | D6 | D2 | D1 | same |
| SSD1306 128×32 | D5 | D2 | D1 | same |

DC=D2, RST=D1 shared. Only the selected panel's CS is compiled in.

## 3. Input wiring

| Signal | Pin | Pull | Behavior |
|--------|------|------|-----------|
| Wheel A | D0 | up | quadrature A (ISR on CHANGE) |
| Wheel B | D4 | up | quadrature B |
| BTN_A | D3 | up | short=select; long>600ms=back/stop |
| BTN_B | D5 | up | short=cancel/back |

**BUG FIXED:** BTN_B was GPIO4 == WHEEL_B (4) — confirm/cancel and wheel
aliased, breaking menu/back. Moved to GPIO5 (verified free: SPI uses
1/2/7/8/9/10, mic 40/41/42). Done in `main.cpp`.

## 4. I2S mic (onboard — no external wire)

`MIC_BCLK=40`, `MIC_WS=41`, `MIC_DIN=42`. `start_capture()` installs I2S
@ 16 kHz / 16-bit / left-only and streams `MSG_AUDIO_CHUNK`. (External I2S
breakout routes to the same three pads + GND.)

## 5. Power wiring

- **Tether:** USB-C 5 V → XIAO regulator → 3.3 V for ESP32 + screen.
- **Untethered:** 3.7 V Li-Po → `BAT` pad (through charge/protect) →
  XIAO charger tops from USB-C. Keep draw < 300 mA.
- **Ring:** independent; magnetic pogo cradle, ~1 hr full, ~5 days.

## 6. Ring "wiring" (BLE, from `30-colmi-r02-integration.md`)

1. Scan for `R02_*`; 2. connect service `6E40FFF0-…-E50E24DCCA9E`;
3. subscribe TX `6E400003-…`; 4. write requests to RX `6E400002-…`;
5. parse 16-byte packets (`ring_parse` C / `parse_*` Python). `-DENABLE_RING`
on the XIAO; `device/colmi_r02.py` (bleak) on the phone/PC.

## 7. Not yet on metal

- Real I2S mic + OLED bench test (logic only, native_test).
- Live BLE to physical R02 / G2 (no hardware on bench).
- `pio run -e xiao_*` flash + field test (CI compiles only).
- Vibration motor, low-batt auto-sleep, gyro calibration.

---
**[inferred]** Every pin, CS, the BTN_B bug, the I2S pads, the power notes
and the ring connect steps are lifted from `main.cpp` + `22-screens-plan.md` +
`30-colmi-r02-integration.md` and should be accurate. Inferred only: the
narrative grouping and the "two things called wiring" framing.
