# Cyclops firmware/hardware audit — execution plan

Source: factory-loop applied (premortem -> research -> self-review) to the Arduino/hardware
tree. Goal: prune dead/over-built surface and close the one real hardware gap (ring BLE).

## Boards: one application, three build targets (2026-09-19)

All board differences live in `firmware/xiao/src/board_config.h` (`-DCYCLOPS_BOARD_XIAO`
/ `-DCYCLOPS_BOARD_FEATHER`). Adding a board = one block there + one env.

| target | command | RAM | Flash | sensors |
|---|---|---|---|---|
| XIAO S3 **Sense** (default, docs/42) | `make compile` | 18.5% | 33.5% | cam + PDM mic + SD + I2C OLED + HW-123 + 2 btn + batt |
| Adafruit Feather ESP32-S3 | `make compile BOARD=feather` | 20.8% | 73.0% (4MB) | I2C OLED + HW-123 + 2 btn + batt (no cam/mic/SD) |
| Cyclops mini4 (own project) | `pio run -d mini4` | 10.1% | 17.0% | I2C OLED + HW-123 + 1 btn + batt |

Guards: `BOARD_HAS_MIC` / `BOARD_HAS_CAMERA` / `BOARD_HAS_SD`. On a board without a
mic, recording is refused with a visible OLED notification instead of silently doing
nothing — the gesture's MSG_CMD still reaches the phone, so the brain-side voice path
(transcribe / document / ask) is unaffected. Same for photos: `ACT_PHOTO` travels to
the app; only the on-device OV2640 capture is absent.

Flash paths differ by board: XIAO is a plain ESP32-S3 (PlatformIO emits bootloader +
partition table, so `make dist` merges a single 0x0 image for esptool/ESP Web Tools).
The Feather ships Adafruit's TinyUF2 in flash which PlatformIO deliberately does not
regenerate — `make dist BOARD=feather` therefore copies the app image and the path is
UF2 (double-tap RESET → copy onto the FTHRS3BOOT drive) or `make flash`.

## Grand vision (docs/42, docs/34-41)

The wearer's past becomes queryable and their present becomes decidable, with the
wearable as the only surface needed. cyclops + app, through physis, is the single
access point to computer, internet, and AI. Loop: **capture with a question
attached → cited answer from the ledger → glanceable digest back on the OLED.**
The model is a replaceable interpreter outside (swap it and belief must survive);
only notes/claims cross the link, and anything irreversible needs a confirm row.

### What the screen shows (4-pin 128x32, 21x4; `firmware/shared/include/hud.h`)

```
row0  STATUS   12:04 BT+ RNBD 82%        clock + link + battery
row1  ANSWER   Meet Bob 3pm, bring       AI's last line (hud_line, size 2)
row2  DIGEST   standup 14:30 office      belief digest (top claim) / newest note
row3  HINT     A:ask B:note ~ tilt       affordance; progress/steps/toast preempt
```

Priority answer > digest > hint. Notifications overlay row1; toasts, REC, consent
and contradiction prompts preempt from the bottom up — no row is ever added. Idle
8s → screen off (burn-in + battery). A new text answer calls `clear_run()`, so a
finished agent run never leaves a stale progress bar on the HINT row. MENU (tilt
+ A) keeps Notes/Agent/Transcribe/Translate/Health/Navigate/Teleprompter/Camera/
ImageAnalyze/SSH/Settings/Back; CHOICE walks W4 procedure steps.

The same rows drive the laptop simulator (`shells/hud_sim.py`) and `/api/status`
(`banner`/`digest`/`hint`), so the phone mirror is never a dead demo.


## Premortem (risks)
- D1: ring BLE is a stub (`scan->start(5)` only, no connect/parse).
- D2: NimBLE dual-role (phone server + ring client) re-init risk.
- D3: CI builds only xiao_* + native; arduino_* unverified (may not compile).
- D4: gesture engine + bindings live only in xiao/; arduino uses raw on_select/on_back.
- D5: mic+BLE+ring on one core, no flow control -> possible starvation/OMemory.

## SKIP (dead / over-built)
- S1: drop `arduino/` target (dev sim is shells/hud_sim.py, uses real wire frames).
- S2: remove unused `Imu::last_gz_`.
- S3: drop `on_long_back` path if arduino is dropped.
- S4: drop arduino-only MSG_PEER_STATUS cap handshake (xiao never consumes).
- S5: drop joystick+proximity from the design surface.

## IMPROVE (high-value, grounded)
- A (C1): finish ring BLE connect (advertised-device cb -> createClient -> UART svc ->
  ring_parse -> hud.set_health). single NimBLE init, client reuses device.
- B (C2): unify input path; after dropping arduino, one gesture/binding path remains.
- C (C3): low_power mode (stop mic task, slow BLE) when screen off + not recording.
- D (C3): audio ring buffer + drop-oldest backpressure in audio_task.
- E (C3): SD log date-rotate / max-size trim.
- F (doc): document PHOTO/VIDEO/VOICE capture = phone-driven (OpenGlass), not XIAO HAL.

## XIAO-S3 grounding (Seeed wiki)
- Pins valid: btn 3/5, wheel 0/4, I2C 43/44, SD 21/7/8/9, mic 40/41/42. ~0 spare GPIO.
- No free I2S-out pins -> confirms phone-relay audio-out (TTS) was the correct call.

## Cycles (each: build+verify+commit+push as a unit)
- C1: finish ring BLE (A). Code complete: scan-by-name -> createClient ->
  NUS connect -> TX subscribe -> ring_parse -> hud.set_health, reconnect on
  drop (firmware/xiao/src/ring_ble.cpp, wired in main.cpp under ENABLE_RING).
  Host gate green (test_colmi_r02 + test_v2::test_ring_client, 13/13).
  Remaining: pio xiao build (CI) + on-board boot log.  [CODE DONE, HW PENDING]
- C2: prune arduino target (S1-S5) + dead fields (S2). Verify: CI matrix + host gate + build.  [DONE]
- C3: power mode (C) + audio backpressure (D) + SD rollover (E) + capture doc (F).  [DONE]
  - F: PHOTO/VIDEO/VOICE capture is phone-driven (OpenGlass/companion); the XIAO
    has no camera HAL. The wearable fires ACT_PHOTO/VIDEO/VOICE_* gestures which
    the brain bridges to the phone camera (see brain/hud_bridge.py). Documented.
- C4 (optional): web research upgrade pass (OpenGlass/Omi/G2 competitive) — DONE
  via docs/31-repremortem-competition.md (already written). No new code action
  surfaced beyond C1-C3. AUDIT COMPLETE.

## Verification gates
- Host: `make test` (shared) must stay green.
- Firmware: `pio run -e xiao_128x32_i2c` SUCCESS.
- Ad-hoc `/tmp/hermes-verify-*` scripts for new behavior; cleaned after.
- arduino_*: remove from CI (S1) so no unverified rows remain.

## Board
- Currently flashed at cc57ba3; b4733cc (IMU auto-detect) pending. All cycles flash once
  board connects. Until then: build+test+push only.

## MVP one-button + physis-next (2026-09-28, docs/43)

- **Input model: ONE button** (GPIO3) on the MVP harness — tap=OK, double-tap=BACK,
  long=AGENT; `BOARD_HAS_BTN_B 0` (XIAO) / `1` (Feather); factory reset = hold BTN_A
  ≥2 s at boot; HINT row `tap:ok 2x:back hold:ask` via `Hud::use_one_button()`.
  GPIO5 is now free. Accel must be MPU-class at 0x68 (LSM6DS3 would ACK and read
  garbage — no onboard IMU on the S3 Sense).
- **physis-pro is retired**: `brain/physis.py` is now the legacy embedder adapter
  only (classify/lifeos/goals/coherence deleted with their routes). Memory goes
  through `brain/physis_next.py` → `physis serve --http 127.0.0.1:19876` (MCP
  `tools/call`, stdlib). App routes `/api/physis/*` restored; loop recipes
  `just physis-serve / recall / remember` drive `scripts/physis_mcp.py`.
- **Lost routes restored** (same bug class as the physis one): `/api/concepts`,
  `/api/concepts/groups`, `/api/truth`, `/api/truth/log`; `physis` added to the
  capability registry so the app/TUI can list it.
- Gates: python suite **499/0**; `make test` (16 cmds) + `make proto` green;
  `gen_acts.py --check` in sync (27 acts). Open: C2 (firmware HTML page),
  C3 (VAD + MSG_STATUS starvation on metal), C4 (accel part check), C5
  (presence/posture as claim boundaries), Android `dead_calls` (7 pre-existing).
