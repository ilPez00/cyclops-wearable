# Cyclops

A wearable AI note-taker: XIAO ESP32-S3 Sense HUD (screen + wheel + buttons +
gyro) that captures audio, sends it to a "brain" (Python) for transcription and
smart-note extraction, and displays glanceable notes back on the device, or
forwards them to EvenRealities G2 glasses / Omi-Pebble style HUDs.

Inspired by feature sets from EvenRealities G2 (HUD glasses: navigation,
translation, notification, teleprompt, music, glanceable text) and the
Omi / Pebble wearable (24/7 audio, transcription, memory, app, web).

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
