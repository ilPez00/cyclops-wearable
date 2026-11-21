# Cyclops → Pansa handoff (2026-09-18)

Session moves feather → pansa. Continue on pansa in `~/dev/cyclops-wearable`.

## Goal
Android app connects via BLE to XIAO S3 Sense pendant, runs physis locally:
auto record (VAD-gated) + notebook + dictation + memory. No server required.

## Hardware state
- XIAO S3 Sense flashed `xiao_128x32_i2c` (4-pin I2C OLED build). RAM 18.2%,
  Flash 33.0%. Upload via /dev/ttyACM0 OK.
- Boot log: screen.begin ok, hud.init ok, SD mounted, `imu NOT found (0x68)`
  (expected, no accel soldered), heartbeat HOME.
- Solder pending (iron broken): OLED VCC→3V3 GND→GND SCL→D5/GPIO6 SDA→D4/GPIO5;
  MPU6050 GY-521 same bus (0x68 + 0x3C coexist); button D3→GND; LiPo to BAT pads.
- `imu.cpp` expects MPU6050 0x68. ADXL345 (0x53) will NACK.
- USB tether works for all testing. No battery needed until field test.

## Software state (copied feather → pansa)
Files (pansa `git status`):
- M `brain/pipeline.py` — `Pipeline(..., physis=True)` auto-mirrors notes via
  `capture_note`, fail-soft.
- ?? `brain/physis_sink.py` — typo alias kept, `CYCLOPS_PHYSIS_RETRY` override,
  retry queue `_rewrite()` persist fix.
- ?? `brain/vad.py`, ?? `tests/test_vad.py` — EnergyVAD (pansa lacked it).
- ?? `app/physis_notes.py` — dictate/notebook/memory/auto/export CLI, local
  ngram-128 embed + cosine search, stdlib only.
- ?? `tests/test_physis_notes.py` — 3 tests.
- ?? `android/core/.../PhysisLocal.kt` — Kotlin port: rule extractor, embed,
  memorySearch, glanceLines 4x18. Zero deps.
- ?? `android/core/.../PhysisCascade.kt` — pick(localGguf, omniroute, ollama,
  keys) local-first order from pika-hermes.
- ?? `android/core/.../PhysisTest.kt` — extractor, rank, 4x18, norm, cascade.

Gates: feather full suite 365 pass. Pansa `test_physis_notes + test_vad`
10 pass. Pio build `xiao_128x32_i2c` SUCCESS on feather.

Heads diverged: feather `2a6bebf`, pansa `fcb7c79` (was clean). On pansa
`physis_sink.py` untracked vs tracked on feather. Reconcile (diff/rebase)
before commit. Stage explicit paths only — never `git add -A`
(another agent leaves untracked work in ~/dev/aion; same discipline here).

## Donors (cloned to /tmp/opencode/donors on feather, NOT copied to pansa)
- pika-hermes (public): `ProviderCascade` order, `LocalModelManager` HF
  download pattern, `LlamaBackend` JNI. Reuse order only.
- aura_definitive (public, archived): `WikiStore`, `QuickNoteWidget`,
  `NotesWidget`, `MemoriesWidget`, `TranscriptionWidget`. Notebook pattern.
- merlin (public): `android/` wrapper + `phone/` bridge. BLE-central idea.
- Aurora repo not found under ilPez00 — confirm owner/name if still wanted.
- praxis_webapp NOT touched (live secrets). Notebook pattern only.

Re-clone on pansa if needed:
  git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/ilPez00/pika-hermes.git /tmp/donors/pika-hermes

## BLE / phone path (existing, reuse)
- XIAO peripheral `CyclopsXIAO`, SRVC `4fafc201-...`, NOTE `beb5483e-...`
  READ|NOTIFY|WRITE. `CyclopsService.kt` central with CCCD notify + backoff
  reconnect. `HudBridge` (py + `:core` kt port) fulfills MSG_CMD, streams
  `MSG_AUDIO_CHUNK` (ADPCM 4:1).
- Phone side: `device/ble.py` BleLink (needs `pip install bleak`), Android
  `CyclopsService`, dashboard `python3 app/server.py 8080` (/api/notes).
- SD: CS GPIO21 SPI 7/8/9, free only on I2C build. `/cyclops.log` 256KB
  rollover. Mount proven; write proven via `pio run -e xiao_selftest`.

## Next on pansa (ordered)
1. `cd ~/dev/cyclops-wearable && git status --short && git log --oneline -3`
   Reconcile heads. Decide: rebase feather work onto fcb7c79 or cherry-pick.
2. `python3 tests/run_tests.py tests/test_*.py` — expect 365+ pass.
3. `pip install --break-system-packages platformio bleak` (feather used
   --break-system-packages, pio 6.2.0). Disk fine on pansa (feather must not
   build — only ~20G free).
4. `cd firmware && pio run -e xiao_selftest` then upload, verify SD write +
   PDM mic (clk42/data41) over serial.
5. BLE E2E: `pip install bleak`, scan for `CyclopsXIAO`, connect, decode
   MSG_STATUS with brain Decoder, send ACT_TRANSCRIBE_START, pull WAV.
6. Android: no SDK on feather or pansa — APK is CI-only. Push branch, let CI
   run `:core:test` (includes new PhysisTest) + build. Locally only edit +
   eyeball Kotlin.
7. Backend choice for local physis LLM: (a) rule-only now (done), (b) GGUF via
   donor LlamaBackend JNI + LocalModelManager download (needs NDK + model),
   (c) cloud cascade via omniroute/ollama/keys. Recommend (a) ship, (b) next.
8. Commit: explicit paths, concise message, no secrets. Push when green.

## Env notes
- Python 3.13, pip 25.1.1, pio 6.2.0 (feather). Java 21 present, no
  kotlinc/gradle/Android SDK anywhere yet — install on pansa only if doing
  local APK work, else rely on CI.
- Services bind Tailscale IP, never loopback or 0.0.0.0.
- Do not read/copy/commit anything under `~/Praxis/praxis_webapp`
  (.env, praxis_auth*, supabase_*). Stripe live.
