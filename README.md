# Cyclops

A wearable AI note-taker: XIAO ESP32-S3 Sense HUD (screen + wheel + buttons +
gyro) that captures audio, sends it to a "brain" (Python) for transcription and
smart-note extraction, and displays glanceable notes back on the device, or
forwards them to EvenRealities G2 glasses / Omi-Pebble style HUDs.

Inspired by feature sets from EvenRealities G2 (HUD glasses: navigation,
translation, notification, teleprompt, music, glanceable text) and the
Omi / Pebble wearable (24/7 audio, transcription, memory, app, web).


> **TL;DR.** Open wearable AI note-taker: XIAO ESP32-S3 HUD firmware (C++/PlatformIO),
> local-first Python brain (transcription → smart notes), Android companion, wire protocol
> with CRC framing. **Runs and tests without hardware, pip or API keys:** zero-dep test
> suite 9/9 PASS + end-to-end demo OK on a fresh checkout (2026-11-21). Hardware footage
> and BOM: pending (not claimed here).

## Layout
```
protocol/   wire protocol spec (device <-> brain)
device/     C++ firmware (XIAO) + host simulator + battery + gestures + CLI
brain/      Python: transcriber, extractor, store, pipeline, display sinks
app/        stdlib web dashboard (no pip needed)
tests/      zero-dep test runner (run_tests.py)
firmware/   PlatformIO project for seeed_xiao_esp32s3 (+ native test env)
demo.py     end-to-end demo (audio -> notes -> screen)
```

## Run (no hardware, no pip, no API keys)
```
python3 tests/run_tests.py tests/test_brain.py tests/test_device.py
python3 demo.py
python3 device/cli.py g2        # glasses variant
python3 device/cli.py pebble    # omi-pebble variant
python3 app/server.py 8080      # web dashboard
```

## Features
- Wire protocol with CRC framing (C++ + Python mirrors).
- Local-first transcription: faster-whisper if installed, else deterministic stub.
- Smart-note extraction: task / reminder (due-date parsing) / decision / idea / summary.
- Display sinks: local HUD (DISPLAY_CMD frames), G2 glasses (NOTE frames), console.
- Input: scrollwheel, 2 buttons, gyro gestures (nod/shake).
- Battery monitor + low-power flag.
- Persistence: JSONL + Markdown export. Web dashboard.
- Three variants: local (XIAO HUD), g2 (glasses), pebble (audio-first).

## Build firmware
```
pio run -e seeed_xiao_esp32s3     # flash to XIAO
pio run -e native                 # host unit-test build
```
(PlatformIO optional; the C++ is verified host-side via g++ already.)


## Verified 2026-11-21

Fresh public checkout/release, run on a clean host (pansa, 12-core Linux):

- `python3 tests/run_tests.py tests/test_brain.py tests/test_device.py`: **9/9 PASS** (CRC roundtrip, extractor categories, G2 trim, screen sink, pipeline e2e, stub transcriber, device modes, battery).
- `python3 demo.py`: Demo OK — audio→notes→screen, due-date parsing verified in output.

Method + full logs: portfolio audit verification log (private hub); reproduction commands in this README.
