# Cyclops — Testing Strategy & Status

> **RECONSTRUCTED DOC** — original `docs/05-testing.md` (2026-06-15) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `tests/run_tests.py`, the test file list, `firmware/Makefile`, `PLAN.md`,
> `docs/00-superplan.md` and `04-release-v0.4.md`. **[inferred]** = guessed.

## 0. Principle (premortem #10)

> "No tests because it needs hardware" is a failure mode. Everything has a host
> build + fake transports; CI runs the full pipeline with stub audio. Hardware is
> a runtime detail, not a build blocker.

Every component ships with an **offline test** — no keys, no network, no device.

## 1. Test runner

`tests/run_tests.py` — **zero-dependency** harness (stdlib only). Run:

```
python3 tests/run_tests.py tests/test_*.py
```

At v0.4: **115 tests pass** (was 26 at the start of the recursive loop).

## 2. Test inventory (by area)

| File | Covers |
|------|--------|
| `test_wire_contract.py` | v1 framing + CRC round-trip, every message type |
| `test_v2.py` | v2 peers / time-sync / health / HUD_FRAME encoding |
| `test_colmi_r02.py` | ring 16-byte parser (checksum, battery, HR/SpO2, error/CRC rejection, builders) — 6 cases |
| `test_brain.py` | brain: transcribe→extract→store→display glue |
| `test_pipeline.py` | end-to-end pipeline |
| `test_bridge.py` / `test_hud_bridge.py` / `test_hud_bridge_stream.py` | `HudBridge`: MSG_CMD → note + DISPLAY_CMD push; streaming |
| `test_extractor_unified.py` / `test_llm_extractor.py` | rule + LLM extraction, fallback |
| `test_search.py` | semantic + keyword note search (T3.1) |
| `test_transcriber_cloud.py` / `test_cloud_transcriber.py` | cloud STT adapter (key-gated, offline skip) |
| `test_agent_core.py` / `test_agent_endpoint.py` / `test_agent_history.py` / `test_agent_memory.py` | agent loop with fake model + fake tools; history + memory write-back |
| `test_tools_expanded.py` | expanded tool set (whatsapp/media/device registry) |
| `test_tui.py` | TUI constructs + routes a fake turn |
| `test_app_api.py` | web dashboard JSON API |
| `test_settings_profile.py` | persona/profile round-trip |
| `test_aikeys.py` | provider key store (.env precedence) |
| `test_device.py` / `test_device_transport.py` | device codec (serial/ble/cable), transport registry |
| `test_vision_tool.py` | vision tool (offline-stubbed) |

## 3. Firmware host gate (no PlatformIO needed)

`firmware/Makefile` compiles the logic with g++ and runs the native suites:

```
make test     # g++ Hud logic (9 cmds) + COLMI R02 parser block — ALL PASS
make proto    # CRC/framing round-trip
```

- `firmware/shared/test_hud.cpp` — stack push/pop, menu select, confirm
  yes/no, teleprompter paging, note-detail scroll, long-press back.
- `firmware/shared/test_shared.cpp` — protocol/CRC.
- Plus the new ring-protocol block (parser identical to Python).

`pio run -e native_test` is the PlatformIO equivalent of the host gate.

## 4. Android (Kotlin) tests

`:core` module carries offline parser/contract tests (`RingProtoTest.kt`,
protocol round-trips) run by `gradle :core:test` / the CI `Build Companion APK`
workflow. v0.4: `:core` Kotlin tests + debug/release APKs all SUCCESS.

## 5. CI (GitHub Actions)

- `ci.yml` — firmware `native_test` + `xiao_st7735` compiles on every push to
  `cyclops`; Python suite.
- `build-apk.yml` — Android APK (debug + release) on `android/**` changes;
  uploads artifact (no local SDK needed).
- Both green at v0.4.

## 6. What is NOT covered headless

- Live BLE connect to a physical R02 / G2 (no hardware on the bench).
- `pio run -e xiao_*` flash + on-metal pin/field test (CI compiles only).
- Real transcription/extraction quality (models stubbed or key-gated).
- Vibration motor, gyro calibration, Li-Po runtime.

---
**[inferred]** The runner, the v0.4 115-count, the firmware `make test` host
gate, the Android `:core:test`, and the two CI workflows are all stated in
committed docs/source and should be accurate. The per-file coverage column is a
reconstruction from file names + what the adjacent docs describe; exact test
counts per file are inferred.
