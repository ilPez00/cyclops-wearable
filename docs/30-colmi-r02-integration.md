# COLMI R02 Smart Ring — Hardware Integration, Schematic & Wiring Guide

How the COLMI R02 (a $20 open-protocol BLE smart ring) feeds live heart-rate,
SpO2 and battery into Cyclops, and how to physically wire/power the XIAO that
hosts the wearable HUD.

Reverse-engineered facts (community-verified: `tahnok/colmi_r02_client`,
`Puxtril/colmi-docs`): the ring speaks a **Nordic UART Service (NUS)** clone
over BLE — no pairing, no auth, open link (range is ~1 m, low risk).

---

## 1. What the ring actually is (internal hardware)

```
  COLMI R02 (sealed epoxy ring, ~17 mAh Li cell, magnetic pogo charger)
  ┌───────────────────────────────────────────────────────────┐
  │  nRF52-class SoC (BlueX BlueMicro RF03 / Telink)  + BLE 4.x │
  │  ├─ Accelerometer      (steps, sleep, gesture)             │
  │  ├─ PPG optical module (HR + SpO2, green LED + photodiode) │
  │  └─ 17 mAh battery  (~5 days; magnetic charge, ~1 hr)      │
  └───────────────────────────────────────────────────────────┘
        │  BLE GATT (NUS): SERVICE 6E40FFF0-...-E50E24DCCA9E
        │   RX (write)  6E400002-...   TX (notify) 6E400003-...
        ▼
   XIAO ESP32-S3 Sense  (Cyclops wearable: HUD + mic + ring client)
```

The ring is **not user-solderable** — there is no header, test pad, or wired
interface. "Wiring" the ring = establishing the BLE GATT link below. All
physical wiring in this guide is on the **XIAO side** (power, charging, screen,
mic), which IS the part you build.

---

## 2. System schematic (Cyclops + ring)

```
                          ┌──────────────────────────── XIAO ESP32-S3 Sense ────────────────────────────┐
                          │  dual-core 240 MHz · 8 MB PSRAM · BLE (NimBLE server + client)              │
                          │                                                                             │
   COLMI R02  ── BLE ──▶  │  RingBle (central) ──16B pkt──▶ ring_parse() ──▶ hud.set_health(hr,spo2,batt)│
   (HR/SpO2/batt)         │        │                                                                │     │
                          │        │ NimBLE scan/connect to "R02_*", subscribe TX                    │     │
                          │        ▼                                                                ▼     │
                          │  Hud state machine ──render──▶ Screen (ST7735 / 128x64 / 128x32)         │     │
                          │        │                                                                │     │
                          │  NimBLE server "CyclopsXIAO" ◀── phone/glasses (HUD mirror + agent)      │     │
                          │        │ I2S mic (pads 40/41/42) ──▶ MSG_AUDIO_CHUNK ──▶ phone transcribe│
                          └────────┼─────────────────────────────────────────────────────────────────┘
                                   │ 5V USB-C (data + charge)  ·  Li-Po via BAT pin (optional)
                                   ▼
                              Power / charge section (Section 4)

   Phone / laptop (brain server) can ALSO read the ring directly via the same
   protocol using device/colmi_r02.py (bleak) — no XIAO required for health.
```

---

## 3. BLE "wiring" — how to connect the ring (software)

The ring needs **no bond**. Flow (mirrored in `ring_ble.cpp` and `colmi_r02.py`):

1. **Scan** for a device whose name starts with `R02_` (or `R06_`/`R10_`).
2. **Connect**, get service `6E40FFF0-B5A3-F393-E0A9-E50E24DCCA9E`.
3. **Subscribe (notify)** to TX characteristic `6E400003-B5A3-F393-E0A9-E50E24DCCA9E`.
4. **Write** request packets to RX `6E400002-B5A3-F393-E0A9-E50E24DCCA9E`
   (no response flag). Each request → one or more 16-byte notifications on TX.
5. **Parse** every 16-byte TX packet with `ring_parse()` (C) /
   `parse_battery`/`parse_real_time` (Python).

### Packet format (every frame is exactly 16 bytes)
```
 byte 0     : command tag          (>= 0x80 ⇒ ring error response, ignore)
 byte 1..14 : subdata / payload
 byte 15    : checksum = sum(byte[0..14]) & 0xFF
```

### Command reference
| Tag | Name | Request | Response decode |
|-----|------|---------|-----------------|
| 3   | Battery / info | `make_packet(3)` | `byte[1]`=level %, `byte[2]`=charging(0/1) |
| 21 (0x15) | Daily HR log | date-packed subdata | 288 × 5-min points (multi-packet) |
| 105 | Start real-time | `sub=[kind, action]` action 1=START | `byte[1]`=kind, `byte[2]`=err, `byte[3]`=value |
| 106 | Stop real-time  | `sub=[kind,0,0]` | — |
| real-time kinds | | | 1=HR, 2=BP, 3=SpO2, 4=fatigue, 5=health, 7=ECG, 10=HRV |

Real-time HR: send start(kind=1) → collect ≥6 values (ring streams ~1/s) →
send stop. Same for SpO2 (kind=3). Live `RingSample` exposed to the HUD.

---

## 4. XIAO physical wiring & power

The XIAO is the only part you build. Pin map (from `docs/22-screens-plan.md`,
already verified on metal for button/wheel):

```
  XIAO ESP32-S3 Sense            Function              Notes
  ─────────────────────────────────────────────────────────────────────
  D0  ── wheel A (quadrature)    scroll input          INT on CHANGE
  D4  ── wheel B (quadrature)    scroll input
  D3  ── BTN_A (pull-up)         select (short) / back (long >600 ms)
  D5  ── BTN_B (pull-up)         cancel / back one level   (was D4; D4 aliased WHEEL_B)
  D8  ── SPI SCK                 screen                      VSPI
  D10 ── SPI MOSI                screen
  D9  ── SPI MISO                screen
  D7/D6/D5 ── screen CS (ST7735/128x64/128x32)            see docs/22
  D2  ── screen DC               all panels
  D1  ── screen RST              all panels
  40/41/42 ── I2S mic BCLK/WS/DIN (onboard pad)          audio capture
  5V / GND ── USB-C               power + data + charge
  BAT (pad) ── Li-Po + (optional)                        if running untethered
```

### Power & charging options
1. **Tethered (dev)**: USB-C 5 V from host/laptop/power-bank. Simplest; no
   battery circuit needed. The XIAO regulates to 3.3 V for the ESP32 + screen.
2. **Untethered wearable**: connect a 3.7 V Li-Po to the `BAT` pad (+, – to GND)
   through a small charge/protect circuit; the XIAO's onboard charger tops it
   from USB-C when plugged in. Keep total draw < 300 mA (ESP32 + screen + mic).
3. **Ring power is independent**: the COLMI R02 charges on its **magnetic pogo
   cradle** (2-pin). Nothing to wire — just set it on the cradle. ~1 hr to full,
   ~5 days runtime.

### Build flags
- Default build: ring client **compiled out** (offline-safe, smaller).
- Enable: add `-DENABLE_RING` to the PlatformIO `build_flags` for the
  `xiao_*` env you flash. `ring.begin("R02_")` then scans + connects on boot and
  feeds `hud.set_health()` every loop tick.

---

## 5. Files added / changed

| File | Role |
|------|------|
| `device/colmi_r02.py` | Python protocol + `bleak` client (brain/companion can read ring) |
| `tests/test_colmi_r02.py` | Offline parser tests (checksum, battery, HR/SpO2, errors) — 6 cases |
| `firmware/xiao/src/ring_proto.h` | Pure-C 16-byte parser (host-testable, mirrors Python 1:1) |
| `firmware/xiao/src/ring_ble.h` / `.cpp` | NimBLE central client (ARDUINO-guarded; host = no-op stub) |
| `firmware/xiao/src/main.cpp` | `#ifdef ENABLE_RING` hooks `RingBle` → `hud.set_health` |
| `firmware/Makefile` | host gate now includes `xiao/src` (ring parser tested) |
| `firmware/shared/test_hud.cpp` | +COLMI R02 packet parser tests (battery/HR/SpO2/error/CRC) |

The HUD already renders `HR %d  SpO2 %d%%` and `ring %dmV bead %dmV` — ring
data flows straight into the existing HEALTH view.

---

## 6. Verification (done)

- Python suite: `tests/test_colmi_r02.py` → 6/6 (checksum, battery, real-time
  HR+SpO2, error-bit/error-code/bad-CRC rejection, request builders).
- Firmware host gate: `make test` → ALL HUD LOGIC TESTS PASSED (9 cmds),
  including the new ring-protocol block (parser identical to Python).
- Import-safe: `device/colmi_r02.py` imports `bleak` ONLY inside `connect()`,
  so the brain can parse/store ring packets with no Bluetooth dependency.

## 7. Not verifiable headless (needs hardware)

- Actual BLE connect to a physical R02 (no ring on the bench here).
- `pio run -e xiao_st7735` with `-DENABLE_RING` (PlatformIO not installed
  locally; CI `xiao_st7735` job compiles the firmware). The NimBLE central
  path is ARDUINO-guarded and untested at runtime until flashed.
- Field accuracy of HR/SpO2 vs a medical reference.

## 8. Privacy note

The ring's BLE link is **unencrypted and unauthenticated** — anyone within
~1 m can read your HR/SpO2/steps. Acceptable for a personal wearable on your
own body; do not rely on it near strangers, and never forward raw ring data
off-device without TLS (the brain server already terminates BLE locally).
