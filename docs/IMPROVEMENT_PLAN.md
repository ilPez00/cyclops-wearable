# Cyclops — Improvement Plan

Local-first AI wearable: glasses/ring capture → phone "brain" (Python) →
notes / lifeOS / agent / HUD. Firmware (XIAO ESP32) + Android companion +
`brain/` pipeline + `agent/` loop. This plan has three parts: a premortem
(what kills it), a dev plan (what to build), and a business plan (why it
earns).

---

## 1. Premortem — "It's 12 months out and Cyclops failed. Why?"

Ranked by likelihood × blast radius.

### P0 — The brain's HTTP API is unauthenticated on the LAN
`app/server.py` binds `0.0.0.0:8080` with **no auth on any route**. Anyone on
the same WiFi can:
- `POST /api/agent` — the agent has a **terminal tool**. That's remote code
  execution on the phone/host, no credentials.
- `GET /api/notes`, `/api/transcript`, `/api/memory` — read everything the
  wearer ever captured.
- `POST /api/settings` — overwrite `provider` / `api_key` / `endpoint`, i.e.
  redirect the wearer's LLM traffic (and spend) to an attacker endpoint.

The `sightings.py` SSRF guard is careful and correct — but it's a locked
window next to an open front door. **This is the single most likely cause of
a real-world incident.** Coffee-shop WiFi is the threat model, and it's wide
open today.

### P1 — Silent failure culture hides real bugs
`except Exception: pass` appears ~20× across `brain/`. The `bridge = None`
scoping bug (just fixed) survived precisely because every downstream reader
degraded silently to "HOME / no data" instead of erroring. The inbound
Telegram note bug (just fixed) dropped **every** note for the same reason.
Each swallowed exception is a bug that ships and a support ticket that can't
be diagnosed. This is a slow bleed, not a bang — which is why it's dangerous.

### P2 — Secrets and captures sit in plaintext
`~/.cyclops/notes.jsonl`, `sightings.jsonl`, and `profile.json` (which holds
`api_key`) are plaintext on disk. The zero-photo design is a genuinely strong
privacy story — undermined the moment the derived text log and the API key
next to it are readable by any process or backup that touches the home dir.

### P3 — Firmware BLE stability under real load
Recent commits moved `ACT_PHOTO`'s camera+WiFi work off the BLE callback
stack — good, but it signals the callback stack was overrun before. On-demand
capture + audio streaming + HUD frames share one BLE link. If it wedges in the
field, the wearer sees a frozen HUD and blames the product, not the stack.

### P4 — "Stub or real?" ambiguity ships broken silently
`_get_vision_fn`'s own docstring documents a footgun: `make_vision_tool`
stays permanently stubbed unless `session` is passed explicitly. That's one
missed kwarg between "vision works" and "vision silently does nothing." The
same auto-select-backend pattern (transcriber, LLM, extractor) has the same
failure mode: misconfiguration presents as "quietly degraded," never as an
error.

---

## 2. Development Plan

### Now — ship the safety floor (days, not weeks)
1. **Auth the brain API.** Bearer token (`CYCLOPS_TOKEN`), `hmac.compare_digest`
   check in `H._send`'s dispatch, fail-closed. Bind `127.0.0.1` by default;
   require the token to bind `0.0.0.0` — mirror the exact pattern
   `aion/agents/node.py::_bind_host` already uses. The companion app already
   holds config; ship the token through it.
2. **Gate the terminal tool behind HITL.** `brain/hitl.py::GateBook` already
   exists and already guards `ACT_SSH`. Route `/api/agent` runs that invoke the
   terminal/shell tool through the same gate. Never auto-exec from a network
   request.
3. **Kill silent-failure debt where it hides state bugs.** Replace bare
   `except: pass` with `log.warning(...)` in the note/store/bridge paths. Keep
   fail-closed behavior; make it *observable*. Add a `/health` field per
   subsystem (transcriber/vision/llm = real|stub) so "quietly degraded" becomes
   visible.

### Next — harden and de-risk (weeks)
4. **Encrypt at rest.** Age/libsodium-seal `notes.jsonl` + `sightings.jsonl`;
   move `api_key` out of `profile.json` into an OS keystore (Android Keystore
   on the phone side, `keyring` on desktop).
5. **BLE backpressure test harness.** Extend the existing `FrameReceiver`
   fake-transport tests with a saturation scenario (concurrent audio + photo +
   HUD) and assert no dropped/duplicated frames. Turn the field-stability
   worry into a regression test.
6. **Explicit backend selection.** Make `make_vision_tool` (and the transcriber
   auto-select) **raise** on "asked for real, got stub" instead of returning a
   stub, unless `allow_stub=True` is passed. Fail loud in prod, stub only in
   tests.

### Later — the product moat (months)
7. **On-device small-model path.** `gguf_backend.py` exists; make local
   transcription+extraction the default so the wearer's raw audio never leaves
   the phone. This *is* the pitch — lean into it.
8. **lifeOS as the retention hook.** The `_cyclops_sink` vault integration is
   the sticky surface: a searchable, private, growing memory. Make it first-
   class (query UI, timeline, entity graph) rather than an optional import.

### Testing / CI
Add a CI gate: `py_compile` all of `brain/` + `agent/`, run the existing
`tests/`, and a lint that **flags new bare `except: pass`**. The two bugs
found this session were a scoping error and a silently-swallowed constructor
error — both catchable by cheap static checks.

---

## 3. Business Plan

### What it is
A privacy-first AI wearable **you own end to end**: capture happens on cheap
open hardware (XIAO ESP32 + a ring), intelligence runs on *your* phone, and
raw media is discarded by design (zero-photo memory — only text tags persist).
No cloud account required to function.

### Who buys it and why
- **Privacy-conscious professionals** (lawyers, clinicians, journalists) who
  legally cannot stream audio/video to a vendor cloud. Local-first is a
  compliance feature, not a nice-to-have.
- **Quantified-self / builder crowd** who want a hackable Omi/Limitless
  alternative that isn't a subscription black box.
- **Accessibility** — live transcription + teleprompter + translation HUD is
  directly useful to hard-of-hearing users.

### Wedge
The category (Omi, Limitless, Rewind) is **cloud-by-default**. Cyclops's wedge
is one sentence: *"the wearable that forgets the photo and keeps only what it
learned — on hardware you control."* That's a defensible, non-me-too position
the moment P0/P2 above are closed (you can't sell privacy with an open API).

### Model
- **Hardware, at cost or small margin** — commodity ESP32 + ring, BOM is low.
  Hardware is the funnel, not the profit.
- **lifeOS Pro** (the money): local-first sync, encrypted multi-device memory,
  advanced agent/vault features. One-time or low monthly — priced as "own your
  data," explicitly *not* "rent your memories."
- **Open core**: firmware + brain open source (trust is the product), Pro
  features and hosted-optional sync paid.

### Sequence to first dollar
1. Close P0 + P2 (can't charge for privacy you don't have).
2. Ship the lifeOS query UI (the retention surface) — see dev plan #8.
3. Sell a small **maker batch / kit** to the QS + builder community as design
   partners. Their bug reports fund the hardening; their testimonials are the
   privacy proof.
4. Convert design partners to lifeOS Pro. Expand to the compliance segment
   only once encryption + auth are audited.

### Biggest business risk
Same as the #1 premortem item: one publicized "stranger on the café WiFi read
my notes / ran code on my phone" incident ends a *privacy* brand permanently.
Security is not a feature here — it is the whole company. Fund it first.
