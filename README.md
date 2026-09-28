# Cyclops

A wearable AI note-taker. **MVP (docs/43):** XIAO ESP32-S3 *Sense* — all onboard
hardware (OV2640 camera, PDM mic, microSD, WiFi/BLE) — plus a 128×32 I2C OLED, an
MPU-class accelerometer on the shared bus, battery sense and **ONE button**.
The device is a thin client: it sends `MSG_CMD` and renders what the brain
streams back; the phone/brain does transcription, extraction, retrieval and
tools, and `physis-next` is the memory substrate behind it.

Inspired by feature sets from EvenRealities G2 (HUD glasses: navigation,
translation, notification, teleprompt, music, glanceable text) and the
Omi / Pebble wearable (24/7 audio, transcription, memory, app, web).

## Layout
```
protocol/   wire protocol spec (device <-> brain) + generated ACT ids
firmware/   PlatformIO projects: xiao/ (MVP + Feather), mini4/, native host gates
device/     host-side BLE/USB transport, Colmi R02 ring, Omi + G2 sinks, simulator
brain/      Python: transcriber, extractor, store, events ledger, claims, pipeline
agent/      agent loop + tools (terminal/web/vision/hud/physis/…)
app/        stdlib web dashboard + JSON API (one self-contained dashboard.html)
android/    companion APK (thin client over the same API)
tests/      zero-dep test runner (run_tests.py)
```

## Run (no hardware, no pip, no API keys)
```
python3 tests/run_tests.py tests/test_brain.py tests/test_device.py
python3 demo.py
python3 device/cli.py g2        # glasses variant
python3 device/cli.py pebble    # omi-pebble variant
python3 app/server.py 8080      # web dashboard
```

The dashboard binds `0.0.0.0` so the phone can reach it, and `POST /api/agent`
carries the terminal tool — so **every route except `/health` is token-gated
for non-loopback callers**. Loopback (this machine, tests, `adb reverse`) needs
nothing. From another device, open the URL the server prints once:

```
http://<host>:8080/?token=<contents of ~/.cyclops/token>
```

That sets a `SameSite=Strict` cookie; scripts can send `X-Cyclops-Token`
instead. `CYCLOPS_TOKEN` overrides the file. `CYCLOPS_ALLOW_INSECURE_LAN=1`
disables the gate entirely — only on a network you control end to end. The
token crosses plain HTTP in clear, so front it with TLS/tailscale off-LAN.

## Features
- Wire protocol with CRC framing (C++ + Python + Kotlin mirrors, parity-tested).
- Local-first transcription: faster-whisper if installed, else deterministic stub.
- Smart-note extraction: task / reminder (due-date parsing) / decision / idea / summary.
- **Event ledger** (`brain/events.py`): one append-only stream of
  `Event{ts, duration_s, source, kind, body, locator}`; writers append in
  addition to their own store (docs/34 §1a/§1b).
- **Cited Ask** (`GET|POST /api/ask`): evidence is retrieved first and the answer
  must carry claim/event ids — `cited:false` plus a warning when it does not.
- Display sinks: local HUD (DISPLAY_CMD frames), G2 glasses (NOTE/HUD_FRAME), console.
- Input (MVP): one button (tap / double-tap / hold ≥600 ms) + accelerometer
  (tilt-scroll, nod, shake, presence, posture). Two-button boards keep the 2×3 grid.
- Firmware serves **JSON only** — `/status`, `/audio.wav`, `/stream` (MJPEG);
  the companion app is the single UI surface.
- Battery monitor + low-power flag; BLE OTA (`brain/ota_push.py` ⇄ `ota.h`).
- Persistence: JSONL + Markdown export, Obsidian vault sink, physis-next memory.
- Dashboard: 11 tabs (Activity, Timeline, Notes, Ask, Device, Physis, Entities,
  Progress, Proposals, Files, Usage), one self-contained file, zero CDN.
- Three variants: local (XIAO HUD), g2 (glasses), pebble (audio-first).

## Build firmware
```
pio run -e xiao_128x32_i2c         # MVP: XIAO S3 Sense, I2C OLED, one button
pio run -d firmware/mini4          # 4-part dev unit (src_dir = src)
cd firmware && make test && make proto   # host gates, no board needed
```
(PlatformIO optional; the shared C++ is verified host-side via g++ already.)
Bench bringup: `pio run -e xiao_selftest` (SD/camera/mic report over serial).
