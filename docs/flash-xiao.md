# Flashing Cyclops firmware to the XIAO ESP32-S3 Sense

This guide covers building and flashing the wearable firmware. The **host
logic gate** (`make test`, `make proto`) runs anywhere with `g++` — no
toolchain. The **real device build/flash** needs PlatformIO.

## 0. Prereqs

- XIAO ESP32-S3 Sense (with the display shield: ST7735 128×128, or SSD1306
  128×64 / 128×32).
- USB-C cable (data, not charge-only).
- Python 3.10+.

## 1. Install PlatformIO

```bash
pip install platformio        # or: brew install platformio
pio --version                 # sanity check
```

Headless / no-device note: every real-build target (`flash`, `xiao`,
`monitor`, `native`) requires `pio`. If it's missing they bail with a clear
message instead of a cryptic failure:

```text
PlatformIO not found. Install: pip install platformio
Or see docs/flash-xiao.md for the full flashing guide.
```

## 2. Build (host logic gate — no hardware needed)

Run this in CI and on every machine to prove the HUD state machine + wire
protocol are correct:

```bash
cd firmware
make test     # compile + run Hud logic tests (rec, consent, gestures, health)
make proto    # compile + run the shared wire-protocol tests
```

## 3. Build for the device

```bash
cd firmware
make xiao            # XIAO + ST7735 (default)
# other screens:
make xiao SCREEN=xiao_128x64
make xiao SCREEN=xiao_128x32
make xiao SCREEN=arduino_st7735
```

## 4. Flash

```bash
make flash                       # default screen
make flash SCREEN=xiao_128x64    # explicit screen
```

First flash may need the XIAO in **boot mode**: hold the BOOT button, tap
RESET, release BOOT. PlatformIO auto-detects the port (`/dev/ttyACM*` on
Linux, `/dev/cu.usbserial-*` on macOS).

## 5. Monitor serial

```bash
make monitor                     # baud 115200; Ctrl-] to quit
```

## 6. Optional build flags

| Flag | Effect |
|------|--------|
| `ENABLE_RING=1` | Compile the COLMI R02 ring BLE **client** (off by default — the ring is normally paired to the phone, which relays health over the phone↔wearable link; see P2-C). Set when you want the XIAO to scan/connect the ring directly. |
| `SCREEN=...`   | Swap the display target (see §3). |

Example — flash with the ring client enabled:

```bash
make flash ENABLE_RING=1
```

## 7. ENABLE_RING: what it does

- Compiles `ring_proto.h` + `ring_ble.cpp` (COLMI R02 service/client).
- On boot the XIAO scans for the ring, subscribes to live HR/SpO2/battery,
  and feeds them into `Hud::set_health(...)` (shown on the HUD).
- **Default off** to keep the build offline-safe and small, and because the
  reference wiring puts the ring on the phone (P2-C relay path). Flip it on
  only when you physically want the XIAO to own the ring connection.

## 8. CI

GitHub Actions compiles the firmware (`pio run -e native_test` + the device
envs) so regressions are caught without hardware. Local flash is still a
manual step on a machine with a board attached.

## 9. Troubleshooting

- `Permission denied` on `/dev/ttyACM0` → add your user to `dialout` /
  `plugdev`, or `sudo chmod 666 /dev/ttyACM0` for a one-off.
- Board not found → try boot-mode (§4) and check `pio device list`.
- Build blows up on disk → see the `linux-install-triage` skill (disk-full
  recovery for half-installed toolchains).
