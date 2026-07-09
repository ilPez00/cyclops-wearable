# Cyclops — SUPERPLAN

> Single source of truth for the Cyclops project: what it is, what's built,
> what the gaps are, and the prioritized roadmap. Living document — update as
> tracks close. Last revised: 2026-07-08.

## 0. One-line definition
Cyclops is a **personal AI router** that takes text / audio / images from you
(phone, desktop, or XIAO wearable) and routes them through an agent loop to
cloud **or** local models, then returns results to your glasses, phone, and
desktop — mirroring the Hermes agent's loop/tools/skills/memory architecture.

## 1. Why it exists
- You carry a XIAO ESP32-S3 Sense + a phone + a laptop. None alone is the
  brain; together they are, if they share one agent core.
- Goal stated by owner: "the perfect app to route text/audio/images to AI, then
  get back results" — with full access to memory/persona/health, WhatsApp
  exports, photos/voice/places, Omi + EvenRealities-G2 features, terminal
  control, local-model option, and maximum customization.

## 2. Architecture (one core, three shells)
```
cyclops/
  agent/            # THE BRAIN (Hermes-mirroring, provider-agnostic)
    loop.py         # model -> tool_calls -> execute -> repeat (iteration budget)
    models.py       # cloud (openrouter/openai/groq/...) + LOCAL (ollama/lmstudio/custom)
    memory.py       # persona/health/USER.md/MEMORY.md (configurable roots)
    skills.py       # load SKILL.md from disk (reuses ~/.hermes/skills)
    tools/          # 17 tools (see §4)
    config.py       # cli-style config; .env + key-store precedence
    capabilities.py # registry of every capability (drives UI customization)
  shells/
    tui/            # desktop TUI (textual; REPL fallback) — Win/Mac/Linux
    companion_android/ -> android/   # full router APK (built on GitHub)
  app/server.py     # brain server: notes/ingest/extract/chat/agent/hud_cmd
  brain/            # transcriber, extractor, pipeline, HUD bridge (device fulfillment)
  firmware/         # XIAO + Arduino builds; resolution-agnostic Hud state machine
  device/           # desktop-side BLE/USB glue + v2 protocol
  protocol/         # wire framing + CRC (C++ <-> Python <-> Kotlin all match)
  .github/workflows/# builds the APK, uploads artifact (no local SDK needed)
```
**Key decision:** the wearable and phone are *thin clients*. Heavy work (STT,
LLM, vision, tools) runs on the phone/brain; the device sends `MSG_CMD` and
renders `DISPLAY_CMD` / `HUD_FRAME` streamed back. One `agent/` core powers all
three shells — no logic fork.

## 3. Built & verified (green)
- Wire protocol v1 + v2 (framing + CRC16), C++/Python/Kotlin all in sync.
- Firmware `Hud` state machine (14 modes) — host-testable, **native g++ test PASS** (11 cmds) + **proto PASS**.
- Brain: stub/whisper transcriber, rule-based + LLM note extractor, JSONL+MD store.
- Display sinks: local / G2 / console. Inputs: wheel, buttons, gyro (nod/shake),
  proximity wake.
- Web dashboard (stdlib, zero-dep) + JSON API.
- **Agent core** (loop/models/memory/skills/config) — 17+ tools.
- **TUI** (textual + REPL) with glanceable HUD banner + per-tool toggles.
- **Android** full router APK: local-model switch, transport selector (wifi/bt/
  cable), agent call, HUD mirror banner, **COLMI R02 ring screen** (RingActivity
  + RingProto). Builds on GitHub Actions.
- **HUD/UX rework:** glanceable `hud_line` banner, `AGENT` mode + live REC timer,
  transient toasts, mode breadcrumb, DETAIL 256→1024; bridge `dispatch(ACT_AGENT)`
  + `push_hud()`; Android + TUI mirror the banner.
- **P0-A** desktop HUD simulator (decodes real wire frames; `--demo`).
- **P0-B** OpenGlass / XIAO camera ingest (capture→vision pipeline, offline-safe).
- **P0-C** EvenRealities G2 HUD layout (4×18) + `even_hub_sdk` `.ehpk` plugin (node smoke test).
- **P0-D** Consent Mode: `consent_mode` config + `consent` tool + `capture`/`camera`/`omi` gated; firmware REC start gated on consent + `X ` indicator.
- **P1-A** Omi audio ingestion (source→transcriber→phrase loop, BLE import-safe, consent-gated).
- **P1-B** local-first pipeline: `local_first` default; cloud only when explicitly opted in.
- **P1-C** G2/R1 gestures → HUD input (`GEST` protocol + firmware `on_gesture` dispatch + bridge routing).
- **P1-D** unified health frame (`HealthAggregator` fuses COLMI/Omi/G2, single `build_health` emission).
- **P2-A** local-first plugin marketplace (`PluginManifest` + `PluginRegistry` + offline-safe `sync`).
- **P2-B** multi-source context fusion (`ContextAssembler`: notes + health + calendar).
- **P2-C** phone→wearable health relay (`MSG_HEALTH_SAMPLE` → `on_health_sample`; zero = absent).
- **P2-D** offline-safe `make flash` (`ENABLE_RING`/`SCREEN` flags) + `docs/flash-xiao.md`.
- **Tests: 170 passed, 0 failed** (Python full suite) + firmware host gate green.
  Code on the `cyclops` branch of `github.com/ilPez00/ayu`; `master` carries
  >100MB legacy binaries (see §6 / T4.10).

## 4. Tool inventory (capabilities.py — drives UI customization)
| tool | domain | status |
|------|--------|--------|
| terminal | system | done (sandbox+confirm) |
| fs | system | done (allowed roots) |
| vision | multimodal | done (local ollama / cloud) |
| web | knowledge | done (search+fetch, offline stub) |
| calendar | productivity | done (file-backed) |
| clipboard | productivity | done (xclip + file store) |
| health | health | done (reads digigio brain) |
| hud / notify / capture | wearable | done (transport, offline stub) |
| screen | system | done (screenshot+describe) |
| whatsapp_export | social | done (parse export .txt) |
| media_ingest | context | done (photos/voice/places) |
| device | wearable | done (wifi real; bt/cable stub) |
| brain | memory | done |
| memory | memory | done (read/append) |

## 5. Gaps / TODO (the real work left)
**Hardware bring-up (firmware/device)**
- Real I2S mic + I2C OLED on XIAO; flash & field-test (only Arduino/XIAO envs
  compile; native_test used for logic).
- BLE transport for G2/Omi: GATT done (T1.2#3). `device.py` cable is real; bt
  uses BleTransport.
- **Colmi R02 smart-ring (HR/SpO2/battery) BLE** — DONE (v0.5): XIAO ring client
  (ring_ble), shared ring_proto.h, android RingActivity + RingProto Kotlin mirror,
  device/colmi_r02.py async central + tests. [DONE 2026-07-09]
- Vibration motor feedback; low-batt auto-sleep; gyro gesture calibration.

**AI stack (quality)**
- Real faster-whisper / Deepgram on-device or edge box (stub today).
- LLM-based note extraction replacing the rule engine behind the same interface.
- Local vision via Ollama llava (wired, untested live).
- Conversation search / semantic index over notes.

**Features in PLAN not yet built**
- Navigation/GPS + maps, live translation adapter, music control, 24/7
  recording (battery + stream store), teleprompter script source.

**Connectivity / UX**
- Push the glanceable banner over real BLE to the glasses (server path done;
  transport glue pending).
- Conversation history persistence in the agent (currently stateless per call).
- Companion app: settings for model/provider/key per tool, persona editor UI.

**Repo hygiene**
- `master` carries >100MB legacy binaries GitHub refuses; `cyclops` branch is
  the clean line. Decide: keep `cyclops` as the working branch, or `git-filter-repo`
  the large files out of `master`/history.
- `c459b` (digigio persona/health) is the live memory root but is currently
  unmounted — point `memory.py` at it when available.

## 6. Prioritized roadmap (next tracks)
**T1 — Make it real on hardware (highest value)**
1. Flash firmware to XIAO; wire I2S mic + OLED; field-test HOME/MENU/AGENT.  ~[HW ONLY — manual on board-attached machine; `make flash` ready (P2-D)]~
2. **[DONE]** BLE transport: `BleLink` GATT central + `BleTransport` + streaming `Decoder`. Offline-tested.
3. Stream the glanceable banner over BLE to G2/Omi glasses end-to-end.  ~[G2 layout done P0-C; transport glue pending]~

**T2 — Make the AI actually good**
4. **[DONE]** real transcriber: faster-whisper (edge) + Deepgram/OpenAI (cloud). (T2.1)
5. **[DONE]** LLM extraction behind `Extractor` interface. (T2.5)
6. Local vision live test against Ollama llava.  ~[tool exists; live test pending]~

**T3 — Depth & stickiness**
7. **[DONE]** Agent conversation history + memory write-back; note search. (T3.1 / T3.7)
8. Companion-app settings UI (per-tool model/provider/keys, persona editor).
9. Navigation, live translation, teleprompter script source, music control.

**P0–P2 (completed this cycle, 2026-07-09)**
- P0-A desktop HUD sim · P0-B OpenGlass cam · P0-C G2 plugin · P0-D Consent Mode
- P1-A Omi audio · P1-B local-first pipeline · P1-C G2/R1 gestures · P1-D unified health
- P2-A plugin marketplace · P2-B context fusion · P2-C health relay · P2-D flash guide

**T4 — Hardening**
10. Resolve `master` vs `cyclops` branch — open PR `cyclops`→`master` (non-destructive server-side merge). **[IN PROGRESS]**
11. **[DONE]** CI: firmware host gate (`make test`/`make proto`) runs on the `cyclops` branch + full Python suite + firmware build matrix + native tests. (T4.11)
12. Backup `cyclops/` to healthy `c459b` drive.  ~[drive unmounted/degraded — blocked]~

**Not locally verifiable (need hardware / live services):**
- Real XIAO flash + I2S mic field test (T1.1).
- Live Ollama llava vision test (T2.6).
- Kotlin `:core:test` (no local gradle 8.9; CI covers it).

## 7. How to run / verify today
- Agent/TUI: `cd cyclops && python3 shells/tui/cyclops_tui.py` (or `CYCLOPS_LOCAL=1`).
- Brain server: `./serve.sh` (or `python3 app/server.py`) → http://localhost:8080.
- Tests: `python3 tests/run_tests.py tests/test_*.py` → 170 passed.
- Firmware logic: `cd firmware && make test && make proto` → both green.
- Android APK: pushed to `cyclops` branch → GitHub Actions builds debug+release
  artifact (download from the Actions run).

## 8. Principles (don't violate)
- One brain, thin clients. No agent logic in the firmware/phone beyond MSG_CMD.
- Offline-first: every tool has a stub when no transport/network; tests run with
  zero keys and zero network.
- Secrets never committed; `.gitignore` blocks them.
- KISS/DRY; match surrounding code; verify before claiming done.
