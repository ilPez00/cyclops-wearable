# Cyclops — Re-Premortem, Competitive Landscape & Upgrade Proposals

Date: 2026-07-09. Scope: honest "what kills this project" + what OpenGlass / Omi /
EvenRealities G2 / Brilliant Labs Monocle do better, and concrete upgrades.

## 1. Re-premortem — how Cyclops dies (and fixes)

Reverse-engineer failure, then pre-empt it.

| # | Death mode | Likelihood | Fix (already partly done / to do) |
|---|-----------|-----------|------------------------------------|
| D1 | **Hardware never verified on metal** — no PlatformIO locally; XIAO firmware only host-gate-tested (g++), never flashed. A "wearable" that has never worn is vaporware. | HIGH | CI `xiao_st7735` compiles; add a **desktop HUD simulator** (P0-A) + a real flash test on hardware; treat host gate as necessary-not-sufficient. |
| D2 | **Power/thermal collapse** — XIAO + screen + I2S mic + BLE *server* + BLE *central* (ring) all at once. No measured runtime. | MED | Power budget; duty-cycle the ring BLE central (poll 1 Hz, sleep radio); make screen the only always-on draw; document a Li-Po capacity target. |
| D3 | **Privacy blowback** — always-on audio + camera + unencrypted ring HR within 1 m of strangers. | MED | On-device-by-default; **consent LED** + "Consent Mode" (Omi bar); TLS to brain; ring data never leaves phone without explicit opt-in (documented in docs/30). |
| D4 | **Triple-codebase drift** — C firmware / Kotlin companion / Python brain diverge on the wire format. | MED | Shared protocol tests (ring already 3-way: Python/C/Kotlin). Extend to ALL frame types via one cross-impl assert suite. |
| D5 | **No daily-use loop** — lots of features, no "I reach for it every morning" moment. | HIGH | Anchor on 3 loops: (1) capture→candidate note, (2) live translate, (3) glanceable agent answer. Make them 1-tap, not menu-dives. |
| D6 | **Cloud-only, offline-broken** — transcription/LLM stubs need keys; "offline" is a no-op. | MED | Ship a real local Whisper + small LLM path; measure latency; make offline the *default*, cloud opt-in. |
| D7 | **Display too small to matter** — 128×32 OLED can't carry an agent answer. | HIGH | Make **EvenRealities G2 the primary display** (576×288/eye, green) via an SDK plugin; tiny OLED becomes fallback. HUD protocol is already G2-shaped. |
| D8 | **Context loss between sessions** — recursive work abandoned. | LOW | This loop + `docs/00-superplan.md` as source of truth; commit-per-step. |

## 2. Competitive landscape (grounded)

| Project | Hardware | Display | Audio/Input | Open? | What it does better than Cyclops | Gap vs Cyclops |
|---------|----------|---------|------------|-------|----------------------------------|---------------|
| **OpenGlass** (BasedHardware) | XIAO ESP32-S3 Sense + cam, ~$25 | none (phone) | cam + mic | Yes (MIT) | Ships on the **same MCU as Cyclops wearable**; life-logging camera+VLM pipeline; dead-cheap. | Cyclops has no camera ingest yet; OpenGlass has no agent/notes brain. |
| **Omi** (BasedHardware) | $29 pendant | none (phone) | BLE audio (Opus 16k), screen cap | Yes (MIT) | Mature ecosystem (13k★), **Consent Mode**, devkit audio frames, desktop+wearable, plugin community. | Cyclops lacks a consent model + a plugin marketplace; Omi has no ring/health. |
| **EvenRealities G2** | $400 glasses | 576×288/eye microLED green | 4-mic 16k PCM, touchpads | SDK (closed HW, open plugins) | **Real glanceable HUD**, teleprompt/translate/health built in, R1 ring control, BLE 5.2. | Cyclops's tiny OLED can't compete; but Cyclops can *become* a G2 plugin. |
| **Brilliant Labs Monocle/Halo** | 15g, 720p cam, microOLED 640×400 | 20° FOV OLED | cam + bone-conduction | Yes (Nocturne OS) | True open AR (camera+display), hackable. | Heavier/shorter battery; Cyclops is lighter-weight + has the agent brain. |

**Takeaways:**
- Cyclops's differentiator is the **agent brain + notes + ring health** stitched across wearable+phone. Nobody else has all three.
- The display problem is solved by *borrowing* G2 (don't build glasses). The camera problem is solved by *borrowing* OpenGlass (same XIAO). The consent problem is solved by copying Omi.
- Cyclops should be the **integrator**, not the hardware maker.

## 3. Proposed upgrades (prioritized)

### P0 — close致命 gaps (do first)
- **P0-A Desktop HUD simulator.** Terminal/pygame renderer driven by the SAME `CyclopsProto` `MSG_HUD_FRAME` / `DISPLAY_CMD` frames the firmware emits. Makes the UX testable with zero hardware and catches D1/D5. *Cheap, verifiable now.*
- **P0-B OpenGlass camera reuse.** `device/camera.py`: pull frames from the XIAO Sense cam (HTTP/RTP) or phone cam → `vision` tool. Reuses the MCU we already target. Kills D6 camera gap.
- **P0-C G2 as primary display.** Package Cyclops HUD as an `even_hub_sdk` plugin (`.ehpk`) that renders `DISPLAY_CMD` frames on the G2. Turns tiny-OLED weakness (D7) into a strength. Companion builds frames; G2 shows them.
- **P0-D Consent + privacy LED.** Hardware record indicator (LED on REC) + "Consent Mode" toggle (Omi bar). Addresses D3.

### P1 — differentiation
- **P1-A Omi audio ingestion.** Companion reads Omi BLE audio (Opus) → brain transcription, so Cyclops works with the $29 Omi instead of the XIAO mic. Widens hardware support.
- **P1-B Real local-first pipeline.** Bundle tiny Whisper + phi/mini LLM; measure latency; offline = default, cloud = opt-in. Closes D6.
- **P1-C G2/R1 gestures → input.** Map G2 swipe up/down/press + R1 ring tap to `Hud` nav (already shaped for it). 
- **P1-D Unified health frame.** Merge COLMI R02 + G2 R1 + Omi into one `MSG_HEALTH_SAMPLE`; render on HUD/companion.

### P2 — reach
- **P2-A Brilliant Labs Halo/Monocle** support as an open AR alternative (camera+microOLED). Heavier, lower priority.
- **P2-B Multi-source agent context.** Fuse phone screen + wearable + ring + camera into one agent memory (Omi does screen+audio; Cyclops adds wearable+ring+camera).
- **P2-C Plugin/share marketplace.** Omi's community momentum comes from plugins; let users publish note-agents.

## 4. This turn

Implemented **P0-A (HUD simulator)** — see `shells/hud_sim.py` + `tests/test_hud_sim.py`.
It decodes the exact `DISPLAY_CMD` JSON the firmware `Hud::apply_display_cmd` parses and
renders a glanceable terminal grid, so the HUD UX is exercisable without flashing the XIAO.
Other P0/P1 items are proposed; say the word and I'll build the next one.
