# Cyclops firmware/hardware audit — execution plan

Source: factory-loop applied (premortem -> research -> self-review) to the Arduino/hardware
tree. Goal: prune dead/over-built surface and close the one real hardware gap (ring BLE).

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
- C1: finish ring BLE (A). Verify: host gate (ring_parse offline) + xiao build + boot log.
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
