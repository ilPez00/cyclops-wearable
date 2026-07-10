# Cyclops — Brain (Python)

> **RECONSTRUCTED DOC** — original `docs/03-brain.md` (2026-06-15) lost on
> corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from `brain/`
> source (`store.py`, `transcriber.py`, `extractor.py`, `llm_extractor.py`,
> `pipeline.py`, `hud_bridge.py`, `protocol_v2.py`, `ring_client.py`,
> `health.py`, `display.py`, `bridge.py`, `aikeys.py`) and `docs/00-superplan.md`,
> `04-release-v0.4.md`. **[inferred]** = reconstructed.

## 0. Role

The **brain** is the edge/cloud compute half. It runs off the phone or a
laptop (or an edge box). It receives audio/health/note events from the device,
transcribes, extracts smart notes, stores them, and streams glanceable results
back to the wearable / G2 glasses / phone. Local-first: raw audio + health stay
on-device unless cloud opt-in.

## 1. Modules

| File | Role |
|------|------|
| `transcriber.py` | STT: faster-whisper (edge) / Deepgram / OpenAI (cloud) via `get_transcriber()`; deterministic stub fallback. `APITranscriber` dead-code removed (v0.4). |
| `extractor.py` | Rule-based note extractor (task / reminder w/ due-date / decision / idea / summary). Interface `Extractor`. |
| `llm_extractor.py` | LLM extraction behind same `Extractor` interface; `get_extractor`(rule/llm/auto); rule fallback on LLM error. |
| `store.py` | `NoteStore`: JSONL + markdown export, no external deps. `add`/`add_many`/`search` (semantic+keyword, T3.1). |
| `pipeline.py` | end-to-end glue: audio → transcribe → extract → store → display. Glue test in v0.4. |
| `hud_bridge.py` | `HudBridge`: receives `MSG_CMD` (via `SerialFrameReader` / `BleLink` `Decoder`) → store note + push `DISPLAY_CMD`/`HUD_FRAME` back. Glanceable banner + live REC timer + confirm flow. |
| `bridge.py` | generic transport bridge (serial/ble/websocket). |
| `protocol.py` / `protocol_v2.py` | CPython mirror of the wire protocol (framing + CRC16, v2 peers/time-sync/health/HUD frames). Constants match `firmware/shared` 1:1. |
| `ring_client.py` | reads COLMI R02 over bleak (import-safe: bleak lazy-loaded inside `connect()`). |
| `health.py` | ring-aware health time-series + join to notes on UTC window. |
| `display.py` | sinks: local HUD / G2 / console. |
| `aikeys.py` | provider key store (.env precedence); unit-tested (`test_aikeys.py`). |

## 2. Server (`app/server.py`)

Stdlib, zero-dep web dashboard + JSON API on `http://localhost:8080`. Endpoints
(v0.4+): `/api/notes`, `/api/extract`, `/api/search`, `/api/chat`,
`/api/hud_cmd`, `/api/settings` (persona round-trips; persona→system_note sync
on POST). Run: `./serve.sh` or `python3 app/server.py`.

## 3. Transcription (T2.1)

`get_transcriber()` auto-selects: local faster-whisper when installed, else
cloud (Deepgram/OpenAI) using a configured key, else the deterministic stub so
offline tests never need network/keys. Language param supported.

## 4. Extraction (T2.5)

`Extractor` interface; `get_extractor(rule|llm|auto)`. LLM backend emits
**candidates with confidence** (premortem #5) — user confirms on phone before
anything commits to calendar/contacts. Rule engine is the always-available
fallback.

## 5. Storage & search (T3.1)

`NoteStore` appends JSONL (`~/.cyclops/notes.jsonl`) and exports markdown.
`store.search` supports semantic + keyword over notes; exposed at `/api/search`.

## 6. Verification

- Python suite: **115 tests pass** at v0.4 (was 26 at loop start).
  Relevant: `test_brain.py`, `test_pipeline.py`, `test_bridge.py`,
  `test_hud_bridge*.py`, `test_extractor_unified.py`, `test_llm_extractor.py`,
  `test_search.py`, `test_colmi_r02.py` (6), `test_v2.py`,
  `test_wire_contract.py`, `test_transcriber_cloud.py`, `test_aikeys.py`.
- Offline: every tool/test runs with zero keys and zero network (stub fallbacks).

## 7. Not headless-verifiable

- Live faster-whisper / Deepgram transcription quality.
- Local Ollama llava vision (wired, smoke-tested offline, untested live).
- Ring health join accuracy vs reference clock.

---
**[inferred]** Module table, server endpoints list, and verification counts come
from committed code + `04-release-v0.4.md` and should be accurate. Inferred:
exact endpoint paths beyond those named in release notes; the precise
`/api/hud_cmd` vs `/api/chat` split is a reasonable reconstruction.
