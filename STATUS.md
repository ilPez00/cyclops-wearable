# Cyclops — STATUS (2026-07-12)

Single source of truth for build state lives in [`docs/00-superplan.md`](docs/00-superplan.md).
This file is the at-a-glance snapshot.

## Branch / repo
- Remote: `github.com/ilPez00/cyclops-wearable.git` (origin).
- Working branch: `main`.
- Latest commit: `e9fd77c` (fix BLE v2 wire protocol encoding).

## Verification snapshots
| Gate | Result |
|------|--------|
| Python full suite (`tests/run_tests.py tests/test_*.py`) | **214 passed, 0 failed** |
| Firmware host gate (`make test`) | **14 cmds PASS (warning-free after #29)** |
| Firmware proto gate (`make proto`) | **ALL SHARED TESTS PASSED** |
| G2 layout parity (Python↔JS) | PASS |
| Kotlin `:core:test` | CI-only (no local gradle 8.9) |
| Android APK build | CI-only (no local SDK) |

Every step this cycle was committed + pushed after passing all three gates.

## Recently shipped
- **P0–P2 completed** (2026-07-09): HUD sim, OpenGlass, G2 plugin, consent mode, Omi audio, local-first, gestures, unified health, plugin marketplace, context fusion, health relay, flash guide.
- **Memory rewrite** (C9+C10): `MemoryView` → card-based `MemoryStore` (Hermes-style, char-budgeted, thread-safe). `hermes_home`/`digigio_home` config keys are now unused by `MemoryStore` (migration: `memory_root`).
- **Auto-learning** (`agent/learning.py`): background daemon-thread reviews each turn and writes durable facts to USER.md / MEMORY.md — mirrors Hermes's post-turn fork.
- **BLE v2 protocol fix** (`device/ble.py`): `send_cmd` now encodes as MSG_CMD(9) with JSON-wrapped inner action. Aligns C++/Python/Kotlin on same wire format.
- **Firmware audit** (C1–C3): ring BLE connect path, arduino target prune, power management, audio backpressure, SD log rollover.
- **CAD**: pendant enclosure v2 (body/cap, v3 antenna variant, STLs).

## T4 hardening
- **CI green**: firmware host gate + full Python suite + firmware build matrix runs on `main` branch.
- **PR `cyclops→master` promotion**: on hold — `>100MB` legacy binaries on `master` unresolved.
- **CAD**: pendant enclosure v2 (body/cap, v3 antenna variant, STLs).

## Open / not locally verifiable
- Real XIAO flash + I2S mic + OLED field test (T1.1) — manual, board-attached.
- Live Ollama llava vision test (T2.6).
- **Android `:app` BLE build** — needs a local Android SDK (currently ABSENT: `ANDROID_HOME` has only `cmake/`+`ndk/`, no cmdline-tools/platforms/build-tools, no `sdkmanager`). The `:app` glue (`CyclopsService.kt`) is implemented but SDK-gated; `:core` (pure-Kotlin, unit-tested: `RingProtoTest` etc.) builds + tests on CI. Installing the SDK + finishing `CyclopsService.connect()` is the next Android step, but it is **runtime-unverifiable without a BLE device/emulator** — per loop rules, Kotlin that can't be runtime-tested is not shipped blind.
- `agent/learning.py` **now has** `tests/test_learning.py` (was flagged missing — stale).
- End-to-end BLE streaming (brain ↔ wearable) — transport glue present (`device/ble.py` + `CyclopsService`), device-side needs hardware.

## Principles (unchanged)
One brain, thin clients. Offline-first (every tool stubs without network/keys).
Secrets never committed. KISS/DRY. Verify before claiming done.
