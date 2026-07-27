# Cyclops — STATUS (2026-07-27, post LAN-auth + test-green pass)

Single source of truth for build state lives in [`docs/00-superplan.md`](docs/00-superplan.md).
This file is the at-a-glance snapshot.

## Branch / repo
- Remote: `github.com/ilPez00/cyclops-wearable.git` (origin). **Default branch: `main`**
  (`master` force-aligned to `main` 2026-07-12; no longer stale).
- The outer `/home/gio` (ayu) repo carries a tracked snapshot of this tree by owner
  choice — canonical development happens HERE. Content-only-on-ayu commits (ayu #17–#20)
  were ported in #36.

## Verification snapshots
| Gate | Result |
|------|--------|
| Python full suite (`tests/run_tests.py tests/test_*.py`) | **406 passed, 0 failed** (2026-07-27) |
| Firmware host gate (`make test`) | **PASS** (incl. status_json clamp regression) |
| Firmware proto gate (`make proto`) | **PASS** (framing + OTA + **ADPCM contract**) |
| Firmware device builds (`xiao_128x32_i2c`, `xiao_selftest`) | **SUCCESS** (local PlatformIO) |
| G2 layout parity (Python↔JS) | PASS |
| Kotlin `:core:test` / APK | CI-only (no local SDK) |

## Verified ON METAL (2026-07-12, bare XIAO ESP32-S3 Sense)
First real-hardware session — D1 ("never flashed") is dead. Flash 18.9%, RAM 10.1%.
- **Boot**: missing screen/IMU/SD all degrade gracefully; heartbeat + HOME mode.
- **BLE**: advertises `CyclopsXIAO`; laptop central (bleak) connects, decodes live
  MSG_STATUS with the brain's own `Decoder`, writes MSG_CMD back.
- **Camera** (OV2640): VGA JPEG captured + pulled over serial (PSRAM detected).
- **Mic**: works ONLY as PDM (clk GPIO42, data GPIO41) — fixed in #38.
- **SD**: SDHC 32 GB formatted FAT (owner-approved), write+readback OK, mounts at boot.
- **Audio over BLE**: remote ACT_TRANSCRIBE_START → PDM capture → chunks decoded on the
  laptop → WAV. Measured notify throughput ~2 KB/s → drove the ADPCM work (#41).
- Repeatable bring-up: `pio run -e xiao_selftest` (SD/camera/mic report over serial).

## Recently shipped (2026-07-27 pass)
- **LAN auth on `app/server.py` — premortem P0 closed.** The server binds
  0.0.0.0 by design, and `POST /api/agent` reaches an agent holding the
  terminal tool; it was unauthenticated. Now the PEER decides: loopback is
  exempt, anything off-host presents the shared secret in `~/.cyclops/token`
  (`?token=` / `cyclops_token` cookie / `X-Cyclops-Token`). `/health` stays
  open for discovery. `CYCLOPS_ALLOW_INSECURE_LAN=1` opts out, loudly.
  Verified from a second address on the wire, not just in tests
  (`tests/test_app_auth.py`).
- **Auto-learning was dead in production.** `agent/learning.py` called
  `router.complete()`; `ModelRouter` only has `chat()`. Every review raised
  AttributeError into a stderr line, so no fact was ever persisted. `_ask()`
  now accepts either client shape. It is a real second model call per turn, so
  it is gated by the new `AgentConfig.learning` (default on).
- **`AiKeys` registered every `~/.env` variable as an endpoint** — so
  `get_endpoint("ai_groq_key")` returned the *secret*, and `LLMClient` built
  `gsk_.../chat/completions` ("unknown url type"). Endpoints must now look like
  URLs; trailing `# comments` are stripped out of values.
- **`LLMExtractor` degraded silently.** With `_DEFAULT_PROVIDER=omniroute`, a
  user holding only Groq keys got rule-based notes forever with no log line.
  It now falls back to a provider configured with *both* a key and an http
  endpoint, says so once, and traces failures with credentials redacted.
- **Test suite green + honest**: 389/4-failed → 406/0. `test_screen_offline`
  asserted "no screenshot backend" on a box that has scrot — it was silently
  screenshotting the developer's desktop every run; the backend lookup is now
  injectable and screen capture obeys `consent_mode`.
- **Wire-drift gates**: `brain.protocol.MSG` is now checked against the C++
  `MsgType` enum (it had stopped at TTS=20 while the header grew OTA 21–24),
  and the two in-repo copies of `cyclops_shared.h` are asserted identical.

## Recently shipped (earlier cycle, PRs #33–#42)
- **Four on-metal firmware fixes** (#38): PDM mic config; BLE audio chunks never fit
  `send_frame` (silently dropped — now sliced); `status_json` garbage-tail clamp;
  incoming MSG_CMD dispatch (phone can drive capture/HUD, consent-gated).
- **IMA ADPCM codec** (#41): 4:1 audio compression, C++/Python byte-identical wire
  contract, self-contained chunks, warm step-index across chunks; firmware streams
  ADPCM and announces the codec in MSG_AUDIO_META byte[5].
- **ADPCM ingest** (#42, in CI): `HudBridge.handle_audio` decodes per the META codec
  byte; legacy 5-byte META keeps raw PCM.
- **BleakBackend** (#40): real BLE radio behind `BleLink` — the "transport glue
  pending" gap. Import-safe (bleak loads on connect).
- **Obsidian vault sink** (#37): notes mirror into a vault as frontmatter pages +
  daily-note wikilinks (`CYCLOPS_OBSIDIAN_VAULT`); `memory_root` can live in-vault.
- **Test hardening** (#39): learning-suite gaps + env-independent omi BLE test.
- DeviceSim coverage (#33), Android BLE service glue (#35), docs sync (#34).

## Open / next
- **Live re-verify with ADPCM firmware** — board was unplugged mid-session; rerun
  audio E2E + BleLink-over-BleakBackend when reattached.
- **MSG_STATUS heartbeats starve during audio streaming** (observed live).
- **On-device VAD gate** — landed in firmware (71d2f72); not yet measured on metal.
- **Android companion must now send the token** — the APK talks to this server
  over the LAN and every route except `/health` is gated. Until it carries
  `X-Cyclops-Token`, pair by opening the dashboard URL with `?token=` once, or
  run with `CYCLOPS_ALLOW_INSECURE_LAN=1` on a network you trust.
- Ring on metal: R02 was advertising in scans; `ENABLE_RING` central path unverified.
- Live Ollama llava vision test (T2.6); Android `:app` build still SDK-gated.
- **`plan.md` and `PLAN.md` both exist here** — on a case-insensitive checkout
  (a Mac clone, a zip round-trip) one silently overwrites the other.
- **Encryption at rest** (premortem P2): `~/.cyclops/notes.jsonl`,
  `sightings.jsonl` and `profile.json` (which holds `api_key`) are plaintext,
  and `~/.cyclops/token` now joins them.

## Principles (unchanged)
One brain, thin clients. Offline-first (every tool stubs without network/keys).
Secrets never committed. KISS/DRY. Verify before claiming done — on metal when it's metal.
