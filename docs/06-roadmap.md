# Cyclops — Roadmap

> **RECONSTRUCTED DOC** — original `docs/06-roadmap.md` (2026-07-06) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `docs/00-superplan.md` (§5 gaps, §6 roadmap), `PLAN.md`, `01-vision-best.md`,
> `04-release-v0.4.md`. **[inferred]** = reconstructed.

## 0. Status snapshot (v0.4, 2026-07-09)

**Green (offline-verified):**
- Wire protocol v1 + v2 (framing + CRC), C++/Python/Kotlin in sync.
- Firmware `Hud` state machine (14 modes) — host-testable, native g++ PASS.
- Brain: transcriber (stub/whisper/cloud), extractor (rule + LLM), JSONL+MD store, search.
- Display sinks: local / G2 / console.
- Web dashboard (stdlib) + JSON API.
- Agent core (`loop/models/memory/skills/config`) + 17 tools.
- TUI (textual + REPL) with glanceable HUD banner + per-tool toggles.
- Android full router APK (local-model switch, transport selector, agent call, HUD mirror).
- HUD/UX rework: glanceable `hud_line`, `AGENT` mode, live REC timer, toasts, breadcrumb, DETAIL 256→1024.
- **Tests: 115 passed (v0.4), 0 failed.**

## 1. Gaps / TODO (the real work left)

**Hardware bring-up (firmware/device)**
- Real I2S mic + I2C OLED on XIAO; flash & field-test (only Arduino/XIAO envs
  compile; native_test used for logic).
- BLE transport for G2/Omi end-to-end (RFCOMM + GATT). `device.py` bt/cable are stubs.
- Vibration motor feedback; low-batt auto-sleep; gyro gesture calibration.

**AI stack (quality)**
- Real faster-whisper / Deepgram on-device or edge box (stub today).
- LLM-based note extraction replacing the rule engine behind the same interface.
- Local vision via Ollama llava (wired, untested live).
- Conversation search / semantic index over notes.

**Features in PLAN not yet built**
- Navigation/GPS + maps, live translation adapter, music control, 24/7 recording
  (battery + stream store), teleprompter script source.

**Connectivity / UX**
- Push the glanceable banner over real BLE to the glasses (server path done; transport glue pending).
- Conversation history persistence in the agent (currently stateless per call).
- Companion app: settings *UI* for model/provider/key per tool, persona editor.

**Repo hygiene**
- `master` carries >100MB legacy binaries GitHub refuses; `cyclops` branch is the clean line.
- `c459b` (digigio persona/health) is the live memory root but is currently unmounted.

## 2. Prioritized roadmap (tracks)

**T1 — Make it real on hardware (highest value)**
1. Flash firmware to XIAO; wire I2S mic + OLED; field-test HOME/MENU/AGENT. ~[HW ONLY]~
2. **[DONE]** BLE transport: `BleLink` GATT central + `BleTransport` + streaming `Decoder`; RFCOMM `BluetoothTransport` + `CableTransport` stubs; PC loop closed. Offline-tested.
3. Stream the glanceable banner over BLE to G2/Omi glasses end-to-end. ~[G2 pending]~

**T2 — Make the AI actually good**
4. **[DONE]** real transcriber: faster-whisper (edge) + Deepgram/OpenAI (cloud), auto-selected; stub fallback.
5. **[DONE]** LLM extraction behind `Extractor` interface (rule/llm/auto); rule fallback on error.
6. Local vision live test against Ollama llava. ~[tool exists; live test pending]~

**T3 — Depth & stickiness**
7. **[DONE]** Agent conversation history + memory write-back; semantic/keyword note search.
8. Companion-app settings UI (per-tool model/provider/keys, persona editor).
9. Navigation, live translation, teleprompter script source, music control.

**T4 — Hardening**
10. Resolve `master` vs `cyclops` branch (filter-repo or promote `cyclops`).
11. Add CI for the firmware (`pio run -e native_test`) + Kotlin unit tests.
12. Backup `cyclops/` to a healthy drive.

## 3. How to run / verify today

- Agent/TUI: `cd cyclops && python3 shells/tui/cyclops_tui.py` (or `CYCLOPS_LOCAL=1`).
- Brain server: `./serve.sh` (or `python3 app/server.py`) → http://localhost:8080.
- Tests: `python3 tests/run_tests.py tests/test_*.py` → 115 passed.
- Firmware logic: `make test` (g++ Hud) + `make proto`.
- Android APK: push to `cyclops` branch → GitHub Actions builds debug+release artifact.

## 4. Principles (don't violate)

- One brain, thin clients. No agent logic in firmware/phone beyond MSG_CMD.
- Offline-first: every tool has a stub when no transport/network; tests run with zero keys and zero network.
- Secrets never committed; `.gitignore` blocks them.
- KISS/DRY; match surrounding code; verify before claiming done.

---
**[inferred]** §0, §1, §2, §3 are consolidated from `00-superplan.md` +
`PLAN.md` + `04-release-v0.4.md` (accurate). The "T1/T2/T3/T4" track grouping
and the `[DONE]` markings follow `00-superplan.md` §6 and `01-vision-best.md`
directly. Inferred only: exact wording and the §4 principles list (reasonable
reconstruction of the project's stated conventions).
