# docs/39 — Egress audit (docs/41 §4)

Rule (docs/37 §A): outside services are sources and sinks of the ledger,
never its owners. Enumerated 2026-09-19 by grepping network callers in
`brain/` + `agent/`. Export path is the only unconfirmed egress.

## Provider chat endpoints (sink: inference, config-driven)

- `agent/models.py`, `brain/llm_extractor.py`, `agent/tools/vision.py`,
  `agent/tools/camera.py` → provider `/chat/completions` (endpoint from
  settings/aikeys, default `api.openai.com`). Sink. Keys never leave the
  box except as Bearer to the chosen provider.
- `brain/jev.py` → `api.typesafe.ai/v1/systemone`. Sink, read-only oracle
  (state+questions in, probabilities out). No ledger content beyond the
  asked state.

## Cloud tools (sink, per-call)

- `brain/transcriber.py` → cloud transcription endpoint (config).
  Audio leaves the box per transcription call.
- `brain/translator.py` → LibreTranslate/MyMemory/DeepL (config).
  Text leaves per translate call.
- `agent/tools/web.py` → `duckduckgo.com/html` (search tool).
  Queries leave per search.

## Auth (sink, device flow)

- `brain/oauth_device.py` → `openrouter.ai/auth` + `/api/v1/auth/keys`.
  OAuth device flow only; no secrets on device.

## LAN (not egress)

- `agent/tools/brain.py` → `base() + path` (brain server, LAN).
- `brain/sightings.py` → fetches the wearable's announced capture URL
  (LAN camera). Bytes discarded after tagging.

## Plugin index (sink, explicit)

- `agent/plugins.py::sync_index` → operator-provided index URL.
  Explicit pull only, never automatic.

## Vendor sinks (outbound acts, HITL-gated)

- `brain/display_telegram.py` → Telegram via TGPmini (sink).
- `brain/obsidian.py` → local vault files (not network).
- `agent/tools/whatsapp.py` → export-file parse (import, local).

## Exceptions (documented, accepted)

- None currently owner-classified. Any future integration that needs the
  network, the PC, or a vendor account to answer a question is a bug
  (docs/37 §A), filed as such.
