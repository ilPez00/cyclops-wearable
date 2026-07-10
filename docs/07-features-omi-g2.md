# Cyclops — Omi G2 Feature Parity

> **RECONSTRUCTED DOC** — original `docs/07-features-omi-g2.md` (2026-07-06,
> 14.6 KB) lost on corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10
> from `README.md`, `PLAN.md` (G2/Omi gap table), `docs/21-architecture-v2.md`,
> `docs/20-premortem-integration.md`, `docs/23-hud-menu-plan.md`, and the
> `ACT_*` action ids in `brain/protocol_v2.py`. **[inferred]** = reconstructed;
> the original was the longest doc and contained detail I can only partially
> recover — treat this as a structural skeleton, not a verbatim copy.

## 0. Why this doc exists

Cyclops is **inspired by** two shipped products (README):
- **EvenRealities G2** — glanceable HUD glasses: navigation, translation,
  notification, teleprompt, music, glanceable text.
- **Omi / Pebble wearable** — 24/7 audio, transcription, memory, app, web.

The goal (superplan): Cyclops reaches **Omi + G2 parity** — every headline
feature of both, running through one local-first agent brain. This doc tracks
each feature against that bar.

## 1. Feature matrix (status vs parity)

| Feature | Omi/Pebble | G2 | Cyclops status |
|---------|-------------|-----|---------------|
| Glanceable text HUD | ✓ (Pebble) | ✓ | **DONE** (local + G2 sink) |
| Audio capture (24/7) | ✓ | – | DONE transport + stub; real STT pluggable |
| Transcription | ✓ | – | DONE (stub; whisper/cloud pluggable) |
| Notifications | ✓ | ✓ | DONE (NOTE frames → display) |
| Smart notes / memory | ✓ | – | DONE (extractor) |
| Navigation / map | – | ✓ | TODO (needs GPS + maps) |
| Live translation | – | ✓ | TODO (needs translate adapter) |
| Teleprompt | – | ✓ | TODO (script scroll mode) |
| Music control | – | ✓ | TODO |
| 24/7 recording | ✓ | – | TODO (battery + stream store) |
| Phone app parity | ✓ | ✓ | PARTIAL (web dashboard; full APK builds) |
| Conversation search | ✓ | – | DONE (semantic+keyword, T3.1) |
| Health / HR / SpO2 | – (ring add-on) | – | DONE (COLMI R02 client) |
| Terminal / SSH control | – | – | TODO (SSH transport; shell in plan) |

## 2. G2 HUD contract (premortem #4)

G2 is ~640×200 — about **4 short lines**. Hard rules:
- `HUD_FRAME.lines` max 4 strings, each ≤ 18 chars.
- One note at a time + "more" cue; teleprompt scrolls slowly.
- Never push raw transcript — only extracted/summarized text.
- Frames are tiny (< 20 B payload) to survive classic BLE (premortem #1).

The `ACT_*` menu maps to G2-bound intents (`brain/protocol_v2.py`):
`ACT_TRANSCRIBE_START`, `ACT_TRANSLATE`, `ACT_HEALTH`, `ACT_NAV`,
`ACT_TELEPROMPTER`, `ACT_CAMERA`, `ACT_IMAGE_ANALYSIS`, `ACT_SSH`,
`ACT_SETTINGS`, `ACT_AGENT` / `ACT_AGENT_ABORT`.

## 3. Omi-style 24/7 memory

- Audio path: bead/XIAO I2S mic → `MSG_AUDIO_CHUNK` → phone transcribe →
  `Extractor` → `NoteStore` (JSONL + MD). Local-first; cloud opt-in.
- Health join: ring `HEALTH_SAMPLE` (UTC-stamped via `TIME_SYNC`) joined to
  notes by time window (premortem #3).
- Conversation search: `store.search` (semantic + keyword), exposed at
  `/api/search`.

## 4. Privacy parity (premortem #9)

Local-first default. Raw audio/photos/health stay on-device; only extracted
notes leave, and only with consent. Cloud opt-in per feature. Ring BLE is
unencrypted/unauthenticated (~1 m) — acceptable on your own body, never
forward raw ring data off-device without TLS.

## 5. What blocks full parity

1. **Hardware:** XIAO flash + I2S mic/OLED bench test; live G2/Omi BLE
   stream end-to-end (server path done; transport glue pending).
2. **GPS + maps** adapter for NAV.
3. **Translate** adapter (offline + cloud).
4. **Battery budget** for true 24/7 (stream store + low-batt auto-sleep).
5. **SSH transport** + safe shell bridge.

## 6. Verification

- Offline: `tests/test_wire_contract.py`, `test_v2.py`, `test_hud_bridge*.py`
  assert the G2 frame shape (≤4 lines, ≤18 chars) and the ACT_* dispatch.
- `:core:test` (Kotlin) round-trips the protocol.
- Live G2 render: headless-unverifiable (needs glasses).

---
**[inferred — important]** The original `07-features-omi-g2.md` was ~14.6 KB
(roughly 3× this length) and almost certainly contained per-feature design
notes, wiring diagrams, and feature-specific test plans I cannot reconstruct
from the surviving tree. This rebuild is a **faithful skeleton** of the feature
matrix + G2/Omi parity framing, grounded in the README/PLAN/architecture/
premortem docs and the protocol source. If you recall the original's deeper
sections, send them and I'll expand. Everything not explicitly marked came from
committed source and should be accurate in structure.
