# Cyclops — STATUS (2026-07-09)

Single source of truth for build state lives in [`docs/00-superplan.md`](docs/00-superplan.md).
This file is the at-a-glance snapshot.

## Branch / repo
- Working branch: `cyclops` on `github.com/ilPez00/ayu`.
- Latest commit: `76a2841` (P2-D flash guide). All P0–P2 work pushed.
- `master` carries >100MB legacy binaries GitHub rejects → PR `cyclops`→`master`
  is the promotion path (T4.10, in progress).

## Verification snapshots
| Gate | Result |
|------|--------|
| Python full suite (`tests/run_tests.py tests/test_*.py`) | **170 passed, 0 failed** |
| Firmware host gate (`make test`) | **11 cmds PASS** |
| Firmware proto gate (`make proto`) | **ALL SHARED TESTS PASSED** |
| G2 layout parity (Python↔JS) | PASS |
| Kotlin `:core:test` | CI-only (no local gradle 8.9) |
| Android APK build | CI-only (no local SDK) |

Every step this cycle was committed + pushed after passing suite, an ad-hoc
script, and a host-gate run.

## What shipped this cycle (P0–P2)
- **P0-A** desktop HUD simulator (`shells/hud_sim.py`) — decodes real wire frames.
- **P0-B** OpenGlass / XIAO camera ingest (`device/camera.py`, `agent/tools/camera.py`).
- **P0-C** EvenRealities G2 4×18 layout + `even_hub_sdk` `.ehpk` plugin (`device/g2_layout.py`, `g2-plugin/`).
- **P0-D** Consent Mode (`consent_mode` config, `consent` tool, capture/camera/omi gated, firmware REC gated + `X ` indicator).
- **P1-A** Omi audio ingestion (`device/omi.py`, `agent/tools/omi.py`).
- **P1-B** local-first pipeline (`local_first` default, cloud only when opted in).
- **P1-C** G2/R1 gestures → HUD input (`GEST` protocol, firmware `on_gesture`, bridge routing).
- **P1-D** unified health frame (`HealthAggregator` fuses COLMI/Omi/G2).
- **P2-A** local-first plugin marketplace (`PluginManifest` + `PluginRegistry` + offline `sync`).
- **P2-B** multi-source context fusion (`ContextAssembler`: notes + health + calendar), wired into the agent loop + `context` tool.
- **P2-C** phone→wearable health relay (`MSG_HEALTH_SAMPLE` → `on_health_sample`).
- **P2-D** offline-safe `make flash` (`ENABLE_RING`/`SCREEN`) + `docs/flash-xiao.md`.

## T4 hardening
- **T4.11 DONE** — CI now runs firmware host gate (`make test`/`make proto`) +
  full Python suite + firmware build matrix + native tests, triggered on the
  `cyclops` branch (`.github/workflows/ci.yml`).
- **T4.10 IN PROGRESS** — open PR `cyclops`→`master`.
- **T4.12 BLOCKED** — backup to `c459b`: drive unmounted/degraded.

## Open / not locally verifiable
- Real XIAO flash + I2S mic + OLED field test (T1.1) — manual, board-attached.
- Live Ollama llava vision test (T2.6).
- Kotlin `:core:test` and Android APK — CI-gated (no local toolchain).

## Principles (unchanged)
One brain, thin clients. Offline-first (every tool stubs without network/keys).
Secrets never committed. KISS/DRY. Verify before claiming done.
