# Cyclops — The Best Possible Version (VISION + recursive build plan)

> Not what exists today — what Cyclops *becomes*. This is the target the
> recursive implementation loop converges on. Each track below is a
> self-contained unit: design -> implement -> test (offline) -> commit.

## The dream, in one paragraph
Cyclops is the **always-on personal AI layer** you wear and carry. A tiny
XIAO ESP32-S3 Sense on your glasses captures the world (mic, cam, gyro,
health ring). Your phone is the edge brain: it transcribes speech locally
(faster-whisper), runs or routes the agent (Ollama on-device *or* your cloud
keys), and streams a **glanceable answer** to your glasses HUD in <1s. Your
desktop TUI and the Android app are the same brain, different windows. It
remembers you (persona/health/memory), respects your privacy (local-first,
keys never leave the device unless you choose), and you can **build it
yourself** — every part is open, testable offline, and flashes to the XIAO
from a single command.

## Pillars of "best possible"
1. **Sub-second glanceable loop**: speak → local STT → agent → HUD banner, all
   on-device, <1s perceived latency.
2. **One brain, three windows**: wearable / phone / desktop share `agent/`.
3. **Local-first, cloud-optional**: flips to cloud only when you ask; never
   leaks keys.
4. **Privacy by architecture**: raw audio/photos stay on-device; only
   extracted notes leave, and only with your consent.
5. **Spatial + temporal memory**: knows *where* and *when* things happened
   (photos/voice/places), searches conversations semantically.
6. **Full wearable control**: HUD text, haptic notify, capture, teleprompter,
   navigation, live translate, music — Omi + EvenRealities G2 parity.
7. **Self-hostable & flashable**: `make flash` puts the firmware on the XIAO;
   `make app` builds the APK; all offline-testable.
8. **Composable by the owner**: 17+ tools, each toggleable; persona/system
   prompt editable; skills loadable from disk.

## Recursive build tracks (each: design→impl→test→commit)
- **T1 Hardware truth**: flash XIAO, I2S mic + OLED, BLE transport (close
  bt/cable stubs), stream HUD banner over BLE to G2/Omi. [highest value]
- **T2 Real AI**: faster-whisper (edge) + Deepgram (cloud) transcriber; LLM
  extraction; live Ollama vision; semantic note search.
- **T3 Depth**: agent conversation history + memory write-back; companion-app
  settings UI (per-tool model/provider/keys, persona editor); navigation,
  live translate, teleprompter source, music control.
- **T4 Hardening**: promote `cyclops` branch / filter-repo `master`; CI for
  firmware + Kotlin; backup to c459b.

## Success metric per track
A track is "done" only when: offline tests pass, the new path has an ad-hoc
verification, and it's committed to the `cyclops` branch. Hardware tracks add
a `pio run -e <env>` compile gate where the SDK is available.

## Start
Begin with **T1.1**: close the firmware↔device transport gap (RFCOMM/BLE) and
the `device.py` bt/cable stubs, with offline tests, so the wearable can
actually receive the agent's glanceable banner. Then T1.2 firmware flash
prep, then T2 real STT/LLM.
