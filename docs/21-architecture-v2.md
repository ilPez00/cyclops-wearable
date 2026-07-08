# Cyclops — Architecture & Spec (v2)

Wearable AI memory system: **Omi/OpenGlass bead** (audio capture) + **EvenRealities
G2** (glanceable HUD) + **Colmi R02 ring** (health/gesture) + **Android companion**
(hub, BLE fan-out, dashboard, cloud opt-in).

## Topology (premortem-driven)
```
        BLE (audio/notes)          BLE (HUD)           BLE (health)
 Omi bead  ───────────►  [ ANDROID PHONE ]  ◄──── G2 glasses
                                  │  hub
                                  │  BLE (HR/SpO/sleep)
                                  ▼
                            Colmi R02 ring
                                  │
                          USB/WebSocket (opt-in cloud)
                                  ▼
                            Cyclops Brain (Python)
```
Phone is the **single BLE hub**. Bead, G2, ring each pair only with the phone.
Phone fans notes→G2, health→brain timeseries, audio→brain transcription.
This avoids the 3-peer phone connection collapse (see premortem #1).

## Components
| component | role | transport |
|-----------|------|-----------|
| bead      | I2S mic, record, stream compressed audio, record button | BLE → phone |
| G2        | receive HUD frames (note/notification/teleprompt), render | BLE ← phone |
| ring      | HR/SpO/sleep/touch-gesture, battery | BLE → phone |
| phone     | BLE hub, foreground audio service, dashboard, cloud bridge | USB/WS → brain |
| brain     | transcribe, extract notes, store, join ring health, serve API | local/opt-in |

## Privacy
Local-first. Audio + health never leave device unless cloud opt-in per feature.
Recording LED on bead; phone shows live "recording" pill. Ring health stays on
phone unless explicitly exported.

## Build status
- protocol v2: spec + C++/Python codec — DONE
- bead firmware: ESP32-S3 (I2S + BLE GATT) — DONE (host-build + pio cfg)
- G2 sink: BLE HUD frame builder — DONE
- ring client: BLE HR/SpO/sleep + gesture mapping — DONE
- brain: transcriber + extractor + ring-aware store + API — DONE
- android: gradle project, BLE hub service, dashboard UI — DONE (builds w/ gradle)
