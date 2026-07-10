# Cyclops Mini — Compact Wearable Build

> **RECONSTRUCTED DOC** — the original `docs/15-cyclops-mini.md` lived only on the
> now-corrupted `/dev/sde2` mount (created 2026-07-08 15:59) and was never
> committed to a bundle. This version was rebuilt 2026-07-10 from the surrounding
> project docs (`00-superplan.md`, `30-colmi-r02-integration.md`,
> `22-screens-plan.md`, `10-form-factor.md`, `11-pocket-build.md`) and the actual
> code in the recovery tree. Sections marked **[inferred]** are reconstructions
> where the source was ambiguous — verify against hardware before trusting.

## 0. What "Mini" is

Cyclops Mini is the **minimal untethered wearable** form factor: the smallest
physical build that still runs the full Cyclops loop. It drops the dev breadboard
and the tethered USB-C harness in favour of:

- a **COLMI R02 smart ring** as the always-on health/gesture sensor
  (HR / SpO2 / batt / steps — see `30-colmi-r02-integration.md`), and
- a **XIAO ESP32-S3 Sense** running the HUD + I2S mic, powered by a small
  Li-Po and a **128x32 SSD1306** panel (the compact HUD from `22-screens-plan.md`).

The brain stays on the phone/laptop (`agent/` core, unchanged). Mini is a thin
client: it sends `MSG_CMD` / `MSG_AUDIO_CHUNK` and renders `DISPLAY_CMD` /
`HUD_FRAME` streamed back. No agent logic moves to the device.

This is the "pocket build" (doc `11-pocket-build.md`) tightened to ring-scale:
one finger-mounted sensor + one coin-sized HUD instead of a wrist/chest unit.

## 1. Bill of materials

| Part | Role | Notes |
|------|------|-------|
| XIAO ESP32-S3 Sense | wearable MCU + I2S mic + BLE | dual-core 240 MHz, 8 MB PSRAM, NimBLE |
| COLMI R02 ring | HR / SpO2 / batt / accel | $20, open NUS BLE, no solder |
| SSD1306 128x32 SPI | compact HUD panel | 512 B controller RAM, fits easily |
| Li-Po 3.7 V (~200–300 mAh) | untethered power | through charge/protect circuit |
| Magnetic pogo cradle | ring charging | supplied with ring, nothing to wire |
| (optional) tiny vibration motor | haptic confirm | driven off a XIAO GPIO via FET |

Total wearable draw kept **< 300 mA** (ESP32 + screen + mic + ring BLE client).

## 2. Pin map (XIAO, Mini configuration)

From `22-screens-plan.md` (XIAO, SPI 8/10/9) + `30-colmi-r02-integration.md`,
the 128x32 panel is the Mini default:

```
  XIAO ESP32-S3 Sense          Function              Notes
  ─────────────────────────────────────────────────────────────────────
  D0  ── wheel A (quad)        scroll (if wheel fitted; often omitted on Mini)
  D4  ── wheel B (quad)
  D3  ── BTN_A (pull-up)      select (short) / back (long >600 ms)
  D4  ── BTN_B (pull-up)      cancel / back one level   (shared w/ wheel B)
  D8  ── SPI SCK              screen (VSPI)
  D10 ── SPI MOSI             screen
  D9  ── SPI MISO             screen
  D5  ── screen CS            128x32 SSD1306
  D2  ── screen DC            all panels
  D1  ── screen RST           all panels
  40/41/42 ── I2S BCLK/WS/DIN mic capture (onboard pad)
  5V / GND ── USB-C           dev power + data + charge
  BAT (pad) ── Li-Po +        untethered runtime
```

Build flag: `-DSCREEN_128x32 -DENABLE_RING` for the `xiao_128x32` env
(see `firmware/platformio.ini`, `firmware/Makefile`).

## 3. Software blocks (reused, not rewritten)

- **Ring client** — `firmware/xiao/src/ring_ble.h|.cpp` (NimBLE central) +
  `ring_proto.h` (16-byte parser). Compiled in with `-DENABLE_RING`.
  `RingBle::begin("R02_")` scans/connects on boot, feeds `hud.set_health()`.
- **HUD state machine** — `Hud` (14 modes) from `shared/`, renders to the
  `Ssd1306_128x32_Screen` driver. Header-only `Screen` base keeps RAM low.
- **Brain link** — NimBLE server `"CyclopsXIAO"` for phone/glasses HUD mirror +
  agent dispatch; `MSG_AUDIO_CHUNK` → phone transcribe.
- **Phone-side ring read** — `device/colmi_r02.py` (bleak) can read the ring
  directly with no XIAO, so health works even if the XIAO HUD is off.

All three protocol implementations (Python / C / Kotlin) share identical
UUIDs, CRC and decode — verified by parallel offline test suites
(`tests/test_colmi_r02.py` 6/6, firmware `make test` HUD logic + ring block).

## 4. Power & charging (Mini)

1. **Tethered dev**: USB-C 5 V. No battery circuit.
2. **Untethered**: 3.7 V Li-Po → `BAT` pad through a small charge/protect
   circuit; XIAO's onboard charger tops it from USB-C. Keep draw < 300 mA.
3. **Ring power is independent**: magnetic pogo cradle, ~1 hr to full, ~5 days.

Low-batt auto-sleep and a vibration-motor confirm are the Mini UX niceties
(see `00-superplan.md` §5 gaps — gyro gesture calibration + vib motor still
pending hardware verification).

## 5. Differences from the full wearable

| Aspect | Full wearable (doc 10/11) | Mini |
|--------|---------------------------|------|
| Sensor | XIAO onboard IMU + optional ring | ring-first, IMU optional |
| Panel | ST7735 128x128 or 128x64 | 128x32 SSD1306 (glanceable only) |
| Power | USB-C tether or Li-Po | Li-Po default, pocket-sized |
| Input | wheel + 2 buttons | buttons (wheel often omitted) |
| Footprint | wrist/chest unit | finger ring + coin-sized HUD |

## 6. Verification status

- **Done (offline):** ring packet parser (Python/C identical), HUD render to
  128x32 driver (native host test), `xiao_128x32` compile/link, BLE client
  import-safe (bleak lazy-loaded).
- **Needs hardware (unverified headless):** live BLE connect to a physical R02,
  `pio run -e xiao_128x32 -DENABLE_RING` flash + field test (PlatformIO not
  local; CI `xiao_128x32` job compiles), Li-Po runtime/battery-life, vib motor,
  HR/SpO2 accuracy vs reference, end-to-end banner over real BLE to glasses.

## 7. Privacy

The R02 BLE link is unencrypted/unauthenticated (~1 m range). Acceptable on
your own body; never forward raw ring data off-device without TLS (brain server
terminates BLE locally). Same guidance as `30-colmi-r02-integration.md` §8.

---
**[inferred]** Items reconstructed from adjacent docs rather than the lost
original: exact BOM quantities, the "finger + coin-sized HUD" framing, and the
full-vs-Mini comparison table. The pin map, build flags, protocol blocks and
power sections are taken directly from committed, verified code/docs and should
be accurate.
