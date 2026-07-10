# Cyclops — Firmware

> **RECONSTRUCTED DOC** — original `docs/02-firmware.md` (2026-07-06) was
> lost on corrupted `/dev/sde2` and never bundled. Rebuilt 2026-07-10 from
> `firmware/xiao/src/main.cpp`, `firmware/shared/`, `firmware/platformio.ini`,
> `docs/01-hardware.md` and `docs/03-hud-ux-plan.md`. **[inferred]** = guessed.

## 0. Layout

```
firmware/
  platformio.ini          # 6 xiao/arduino envs + native_test
  Makefile                # host gate: g++ Hud logic + ring parser tests
  xiao/src/              # XIAO main + RingBle (NimBLE)
    main.cpp              # wearable HUD + I2S mic + NimBLE server
    ring_ble.h / .cpp    # COLMI R02 BLE central (ARDUINO-guarded)
    ring_proto.h          # pure-C 16-byte parser (host-testable)
  arduino/src/           # Arduino Uno/Nano main (no BLE/mic)
  shared/
    include/screen.h     # resolution-agnostic Screen base
    include/hud.h        # Hud state machine (byte-identical across builds)
    test_hud.cpp         # host Hud logic tests (9 cmds + ring block)
    test_shared.cpp      # protocol/codec tests
  lib/cyclops_shared/    # shared lib, header-only (rm AVR link dup)
```

## 1. Hud state machine (14 modes)

`Hud` is the device brain. Resolution-agnostic — it renders into a `Screen`
whose geometry it reads (`char_cols()`, `text_rows()`). Modes:

`HOME, MENU, NOTES, NOTE_DETAIL, TRANSCRIBE, TRANSLATE, HEALTH,
TELEPROMPTER, NAV, CAMERA, IMAGE_ANALYSIS, SSH, SETTINGS, CONFIRM`

Plus `AGENT` view + `ACT_AGENT` / `ACT_AGENT_ABORT` (latest HUD/UX rework):
glanceable `hud_line` banner, live REC timer, transient toasts, mode
breadcrumb, DETAIL 256→1024.

Data the Hud keeps (fits Uno 2 KB): `notes[12][23]`, `detail[256]` shared
scroll buffer, `scroll_off`, `hr/spo2/ring_batt/bead_batt`, `nav_*`,
`tele_page`, `confirm_prompt[32]`, `rec_secs`, `clock` (from TIME_SYNC).

## 2. Input handling (main.cpp loop)

```
wheel tick      -> hud.on_wheel(+1/-1)        (IRAM ISR on D0 CHANGE)
BTN_A short     -> hud.on_select()
BTN_A long>600 -> hud.on_long_back()
BTN_B short     -> hud.on_cancel()
nod / shake     -> quick-capture / dismiss      (IMU, arduino:N/A)
proximity       -> wake OLED                    (arduino:N/A)
```

## 3. Audio capture (XIAO only)

`start_capture()` installs I2S (16 kHz, 16-bit, left-only), announces format
via `MSG_AUDIO_META`, then `audio_task` streams `MSG_AUDIO_CHUNK` frames over
BLE. `stop_capture()` uninstalls I2S and sends `MSG_AUDIO_STOP`. The phone
transcribes (whisper/cloud) — the XIAO never runs STT.

## 4. BLE (NimBLE, XIAO only)

- **Peripheral (server):** advertises `"CyclopsXIAO"` service
  `4fafc201-…`, `NOTE_CH` `beb5483e-…` (read/notify/write). Phone writes
  `DISPLAY_CMD` / `NOTE` frames → `on_frame` → `hud.apply_display_cmd(json)`.
  XIAO pushes `MSG_CMD` (actions) and `MSG_STATUS` (every 5 s) back.
- **Central (ring):** `RingBle::begin("R02_")` scans/connects the COLMI R02,
  `ring.update()` feeds `hud.set_health()` each loop tick when connected.

## 5. Build & verify

```
pio run -e xiao_st7735 | xiao_128x64 | xiao_128x32   # flash / compile
pio run -e arduino_*                                    # Uno/Nano
pio run -e native_test                                  # host logic
make test        # g++ Hud logic (9 cmds) + ring parser — host gate
make proto       # CRC/framing round-trip
```

All 6 PlatformIO envs + `native_test` compile/link green. Python suite
(16–115 tests across the project) mirrors the protocol 1:1.

## 6. Build flags

- `-DSCREEN_ST7735 | -DSCREEN_128x64 | -DSCREEN_128x32` — pick panel.
- `-DENABLE_RING` — compile in the COLMI R02 client (default off, offline-safe).
- `-DCYCLOPS_ARDUINO` — Arduino target (disables NimBLE/I2S).

## 7. Out of scope / pending

- Real flash + on-metal pin test (CI only compiles `xiao_*`).
- Live G2/Omi HUD stream over real BLE (server path done; transport glue pending).
- Vibration motor, low-batt auto-sleep, gyro calibration (logic stubbed).

---
**[inferred]** §1 mode list + `AGENT` rework, §2 input map, §3/§4 BLE + audio,
and §6 flags are all lifted from `main.cpp` + `03-hud-ux-plan.md` and should be
accurate. The exact `lib/cyclops_shared` header-only rationale and the native
Makefile gate description follow the committed `22-screens-plan.md` RESULT
section. Inferred only: the precise wording of the "14 modes" enumeration beyond
what `23-hud-menu-plan.md` lists.
