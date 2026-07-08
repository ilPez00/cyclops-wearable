# Cyclops — Premortem

Reverse post-mortem: assume it is 2026-09 and the Cyclops stack (Omi bead +
EvenRealities G2 + Colmi R02 ring + Android companion) has partially failed or
is flaky in the field. List the most likely *software/integration/design* causes.
Manual hardware actions (soldering, flashing, wiring the XIAO/I2S mic, charging,
wearing the ring) are explicitly OUT OF SCOPE here — those are tomorrow's bench work.

## 1. BLE topology collapses under 3 concurrent peers
The phone must hold BLE links to bead (audio), G2 (HUD), and ring (HR) at once.
Most phones cap stable concurrent BLE connections poorly; Android GATT caching +
bonding races cause silent drops. **Likely failure:** glasses stop receiving
notifications when ring starts streaming HR. **Mitigation:** bead is the hub that
talks to phone only; glasses + ring are phone-peripheral; phone fans out. Add a
connection watchdog + exponential-backoff reconnect. Keep HUD frames tiny (<20B).

## 2. Audio over BLE is too slow / drops words
Classic BLE (not LE Audio/ISO) cannot carry 16kHz PCM reliably. **Likely failure:**
transcription misses chunks, notes are garbled. **Mitigation:** bead buffers +
compresses (Opus or ADPCM) and streams in MTU-sized chunks; brain tolerates gaps;
do NOT promise real-time on classic BLE. Document that LE Audio needs newer phone.

## 3. Ring data never aligns to notes (no timestamp join)
HR/SpO arrive async from audio. **Likely failure:** "stress during that meeting"
impossible because clocks drift. **Mitigation:** all peers send UTC-anchored
timestamps from phone; brain stores ring samples in a time-series and joins on
window. Ring has no RTC, so phone pushes time sync on connect.

## 4. G2 HUD shows too much / scroll is unusable
G2 is 640x200 — ~4 short lines. **Likely failure:** notes overflow, user can't
read while walking. **Mitigation:** strict truncation + pagination; only 1 note
at a time + "more" cue; teleprompt mode scrolls slowly. Never push raw transcript.

## 5. LLM note extraction hallucinates actions
**Likely failure:** "buy milk" becomes a calendar event with wrong date.
**Mitigation:** extractor emits *candidates* with confidence; user confirms on
phone before anything is committed to calendar/contacts. Keep rule-based fallback.

## 6. Background audio capture killed by Android
**Likely failure:** bead connects but phone app loses mic/audio in background
(battery optimizer, scoped storage). **Mitigation:** foreground service +
persistent notification; request exact alarms; document OEM whitelist steps in app.

## 7. Protocol drift between bead/phone/brain
**Likely failure:** one side adds a field, others crash on parse. **Mitigation:**
single source-of-truth schema (protocol_v2.md), lenient parser (ignore unknown
keys), version field in HELLO, CI test that round-trips every message type.

## 8. Battery lies / no low-power state
**Likely failure:** bead dies mid-meeting, ring disconnects at 10%. **Mitigation:**
battery % from ADC on bead, from ring GATT; auto-pause transcription at <15%;
phone shows all three batteries on one screen.

## 9. Privacy leak — audio/health leaves device
**Likely failure:** transcripts + HR uploaded without consent. **Mitigation:**
local-first default; cloud opt-in per feature; ring health stays on phone unless
explicitly exported; clear "recording" LED + phone indicator.

## 10. No tests because "it needs hardware"
**Likely failure:** integration rots. **Mitigation:** everything has a host build
+ fake transports; CI runs the full pipeline with stub audio. Hardware is a
runtime detail, not a build blocker.

## Top 3 to vigilantly prevent
1. BLE fan-out topology (phone as hub) + reconnect watchdog.
2. UTC time-sync from phone so ring health joins notes.
3. Strict G2 HUD truncation + candidate-only LLM notes (confirm before commit).
