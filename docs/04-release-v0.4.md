# Cyclops v0.4 — Release Notes

**Tag:** `v0.4` · **Date:** 2026-07-09 · **Repo:** `ilPez00/cyclops-wearable` (master)

## What changed this cycle

Every offline-verifiable feature track is now closed. The wearable AI
note-taker loop runs end-to-end (device → brain → notes → glanceable HUD),
with the companion app and firmware building green on CI.

### Tracks closed
- **T1.1** — PC loop closed: `SerialFrameReader` pumps newline-JSON serial
  frames into `HudBridge` (note stored + display frame back).
- **T1.2** — Real BLE GATT central link (`BleLink`: scan/connect/subscribe →
  `Decoder` → `HudBridge`); wired into the agent `ble` transport. Plus **G2
  glasses HUD transport** (`G2Transport` + `G2HudSink`): brain banner → G2
  BLE characteristic, chunked to MTU.
- **T2.1** — Real cloud transcriber (Deepgram/OpenAI) with language param;
  dead `APITranscriber` removed.
- **T2.5** — LLM extraction wired as the auto-selected backend in live +
  extract + server paths; end-to-end pipeline glue test.
- **T2#6** — Local vision live smoke test (probes a reachable local VLM,
  describes a real PNG, else skips offline — zero-dep).
- **T3.1** — Semantic/keyword note search (`store.search` + `/api/search`).
- **T3.2** — Companion settings persist (`persona` round-trips; `persona` →
  `system_note` sync on settings POST).

### Bugs fixed
- `firmware`: `<cstdlib>` → `<stdlib.h>` (AVR/Arduino portability).
- `android`: `CyclopsApi.putSettings` passed a `String` to `post()` which
  expects `URL`; `CyclopsProto.encode` buffer size `8 + len`; non-null param
  pairs.
- `agent/config`: added `persona` field so companion settings round-trip.

## Verification
- **Python:** 115 tests pass (was 26 at loop start).
- **Firmware:** 8 PlatformIO envs + `native_test` all SUCCESS.
- **Android:** `:core` Kotlin tests + debug/release APKs SUCCESS.
- **CI:** both GitHub workflows green (Cyclops CI + Build Companion APK).

## T4 — git hygiene
- `git fsck --full`: clean, 0 dangling objects.
- Branch reconciled: single `master` is the source of truth (the
  `ilPez00/cyclops` repo was left untouched per instruction).
- Tagged `v0.4` with full release notes.
- **Backup:** `git bundle` → `/home/gio/cyclops-wearable-v0.4.bundle` (root fs)
  and `/mnt/sde1/cyclops-wearable-v0.4.bundle` (separate physical disk).
  Bundle clone-verified (full history + tag intact).
  - NOTE: the originally-planned `c459b` (sdf) backup target is the
    known-dead disk (ext4 metadata corruption, user declined repair) — skipped.
  - NOTE: the working disk `sde2` (7d36e554, where the repo lives) is now
    throwing write I/O errors and is degrading. The `/mnt/sde1` and root-fs
    bundles are the live off-disk copies. **Recommend copying the sde1 bundle
    to a third location ASAP.**

## Remaining (hardware/UI-bound — not verifiable headless)
- T1.1#1 — flash XIAO firmware + bench-test pins on metal.
- T3.8 — companion-app settings *UI* (backend done; needs Android layout).
- T4 — promote `cyclops` branch / filter-repo master: already single `master`,
  nothing to promote.
