# Flashing Cyclops firmware to the XIAO ESP32-S3 Sense

This guide covers building and flashing the wearable firmware. The **host
logic gate** (`make test`, `make proto`) runs anywhere with `g++` — no
toolchain. The **real device build/flash** needs PlatformIO.

**Target (V3 slim, == `make SCREEN=xiao_128x32_i2c`):** XIAO ESP32-S3 Sense
(onboard OV2640 cam + PDM mic + SD slot) + external HW-123 accel + 4-pin I2C
SSD1306 128×32 OLED + 2 buttons + battery divider on D2. Pin map:
`docs/wiring-v3-slim.md`. Screen layout + vision: `docs/42-vision.md`.

## 0. Prereqs

- XIAO ESP32-S3 Sense (bare board is enough: the screen and accel are the
  only I2C devices, and boot degrades gracefully with none attached).
- USB-C cable (data, not charge-only).
- PlatformIO (see §1).

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

### No global `pio` on PATH (this dev box)

PlatformIO 6.1.19 is installed for **python3.13** under
`/mnt/faststore/home-gio-sync/`, with the whole espressif32 toolchain cached
in `/mnt/faststore/home-gio-sync/.platformio`. `make compile` / `make flash`
already point at it via `PIO_PY` / `PIO_SITE` / `PIO_CORE` (override with
`make compile PIO_PY=... PIO_SITE=... PIO_CORE=...`).

The one wrinkle: that external `site-packages` ships an ancient
`pathlib-1.0.1` shim which shadows the real stdlib package whenever it is on
`PYTHONPATH`, so `semantic_version` → `pkg_resources` →
`platformio` fails with `cannot import name 'Sequence' from 'collections'`.
`firmware/tools/pio_pathlib_shim.py` re-exports the real stdlib module and is
prepended as `pathlib.py` on `PYTHONPATH` by the recipes. Nothing is
installed into the repo; the shim is copied to `/tmp/cyclops-pio-shim/`.

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
make compile                      # XIAO S3 Sense (default, docs/42)
make compile BOARD=feather        # Adafruit Feather ESP32-S3 (fallback board)
pio run -d mini4                  # Cyclops mini4 (own project, docs/15)
```

Measured footprint (PlatformIO 6.1.19 / espressif32):

| target | RAM | Flash |
|---|---|---|
| `xiao_128x32_i2c` | 18.5% (60468/327680) | 33.5% (1120917/3342336, 8MB) |
| `feather_128x32_i2c` | 20.8% (68148/327680) | 73.0% (1052917/1441792, 4MB) |
| `xiao_mini4` | 10.1% (33068/327680) | 17.0% (567453/3342336, 8MB) |

### Feather ESP32-S3 (no XIAO on the bench)

Same application, same HUD/BLE/input surface — no OV2640, no PDM mic, no SD slot.
All differences are in `firmware/xiao/src/board_config.h`; the env passes
`-DCYCLOPS_BOARD_FEATHER` and the guards compile the sensors out:

| | XIAO Sense | Feather |
|---|---|---|
| Buttons | D3(GPIO3) A / D5(GPIO5) B | GPIO5 A / GPIO6 B |
| I2C (OLED + HW-123) | D6=43 / D7=44 | SDA=3 / SCL=4 |
| Battery divider | D2(GPIO2), ÷2 | A13(GPIO35), ÷2, enable=GPIO7 |
| PDM mic | GPIO42 clk / GPIO41 data | none → capture refused, gesture still sent |
| Camera / SD | OV2640 / CS=21 | none |
| BLE name | `CyclopsXIAO` | `CyclopsFeather` |
| Flash path | esptool / merged 0x0 image | TinyUF2: double-tap RESET → FTHRS3BOOT |

`-DARDUINO_ESP32_WEBSERVER=1` is required on the Feather for the first-boot config
portal; the XIAO env gets the library transitively through DNSServer.

## 4. Flash

```bash
make flash                        # XIAO (default)
make flash BOARD=feather          # Feather ESP32-S3 (TinyUF2, 1200bps touch reset)
```

With no board attached the target refuses *before* touching the toolchain:

```text
no XIAO on USB (/dev/ttyACM* /dev/ttyUSB* absent).
plug the board, then: make flash SCREEN=xiao_128x32_i2c
```

### No PlatformIO on the flashing machine (prebuilt image)

```bash
cd firmware && make dist                 # XIAO: merged bootloader+partitions+app @0x0
cd firmware && make dist BOARD=feather   # Feather: app image for the UF2 drive
```

XIAO yields `cyclops-xiao.bin` (1.19 MB, offset `0x0`): flash with
`esptool.py --chip esp32s3 --port /dev/ttyACM0 write_flash 0x0 cyclops-xiao.bin`,
or from Chromium via ESP Web Tools (WebSerial — no install at all). The Feather
yields `cyclops-feather.bin` (app only: its TinyUF2 bootloader is Adafruit's and
is not regenerated) — double-tap RESET and copy it onto the `FTHRS3BOOT` drive.

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
