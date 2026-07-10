# Cyclops — Compute Host (where the brain runs)

> **RECONSTRUCTED DOC** — original `docs/09-compute-host.md` (2026-06-20) lost
> on corrupted `/dev/sde2`, never bundled. Rebuilt 2026-07-10 from
> `docs/00-superplan.md` (one brain, three shells), `docs/30-agent-design.md`
> (models: cloud + local), `app/server.py`, `README.md`, and `android/.../MainActivity.kt`
> (transport selector, local_endpoint). **[inferred]** = reconstructed.

## 0. The brain is portable

The `agent/` core + `brain/` Python are **host-agnostic**. The same code runs
on whatever edge/cloud box you choose; the wearable + phone are thin clients.

## 1. Host options

| Host | How | Notes |
|------|------|-------|
| **Phone** (Android) | foreground `CyclopsService`, in-process or localhost brain | primary edge brain; BLE hub |
| **Laptop / desktop** | `python3 app/server.py` (or `./serve.sh`) → `:8080` | dev + TUI shell |
| **Edge box** (e.g. a Pi / NUC near you) | same stdlib server, LAN-reachable | offloads STT/LLM from phone |
| **Cloud (opt-in)** | model provider keys in `aikeys.py` / companion settings | only when you ask; never leaks keys |

## 2. Local vs cloud model routing

`agent/models.py` (`models.py` in `30-agent-design.md`):
- **cloud:** OpenRouter / OpenAI / Groq / … — key from the key store.
- **local:** Ollama / LM Studio / custom OpenAI-compatible endpoint — no key.
- **auto:** picks local if a reachable endpoint is configured, else cloud.

The companion app (`MainActivity.kt`) exposes a `local_endpoint` field +
`swLocal` switch + a `transport` spinner (wifi / bt / cable) so the phone
chooses where the brain lives per session.

## 3. Transcriber placement (T2.1)

- **Edge/on-device:** faster-whisper (if installed) — `get_transcriber()`
  auto-selects; no network.
- **Cloud:** Deepgram / OpenAI — language param; dead `APITranscriber` removed.
- **Stub:** deterministic fallback so offline tests never need keys/network.

## 4. Vision (T2#6)

Local vision via Ollama llava (wired; live smoke test probes a reachable VLM,
describes a real PNG, else skips offline — zero-dep). Cloud vision via the
`vision` tool's provider.

## 5. Server surface (`app/server.py`)

Stdlib, zero-dep:
- `GET /` dashboard (notes, ingest, extract, chat, agent, HUD mirror).
- `POST /api/notes`, `/api/extract`, `/api/search`, `/api/chat`,
  `/api/hud_cmd`, `/api/settings` (persona round-trips; persona→system_note
  sync on POST).
- Agent call streams tool ticks + a glanceable first line (the wearable banner).

## 6. Connectivity / transports (`tools/device.py`)

- **wifi:** HTTP to the brain server (default).
- **bt (RFCOMM):** `BluetoothTransport` stub — pending.
- **cable (ADB/serial):** `CableTransport` stub — pending; PC loop already
  closed via `SerialFrameReader` → `HudBridge`.

## 7. Privacy / data gravity

Local-first by architecture (premortem #9): raw audio/photos/health stay on the
host that captured them; only **extracted notes** leave, and only with consent.
Cloud is opt-in per feature. Keys never leave the device unless you configure them.

## 8. Not covered here

- Real BLE transport glue for G2/Omi (server path done; transport pending).
- Conversation history persistence in the agent (currently stateless per call).
- Companion settings *UI* polish (backend done; Android layout pending).

---
**[inferred]** Host table, model routing (cloud/local/auto), the transcriber
placement, the server endpoints, and the transport list are grounded in
committed `30-agent-design.md` / `04-release-v0.4.md` / `MainActivity.kt` /
`README.md` and should be accurate. Inferred only: the "edge box (Pi/NUC)"
example and the exact `/api/*` path enumeration beyond what release notes name.
