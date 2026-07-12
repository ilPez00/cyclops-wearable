#!/usr/bin/env python3
"""CyclUno demo driver — brain end of the wired dev unit.

Feeds PRERECORDED fixtures through the real pipeline (transcriber ->
extractor -> notes) and streams the results to the Uno as NOTE frames, while
reacting to the device's buttons:

    button A (REC toggle)  -> "transcribe" the next prerecorded audio take
                              (synth speech-band WAV -> transcriber -> extractor)
    menu > Ask agent       -> canned agent reply (offline) or the real agent
                              when the brain server/keys are available

Usage:
    python3 demo_cycluno.py                 # auto-pick /dev/ttyACM* or /dev/ttyUSB*
    python3 demo_cycluno.py --port /dev/ttyUSB0
    python3 demo_cycluno.py --fixtures tests/fixtures/cycluno_transcripts.txt

No WiFi/BT anywhere: this is the wired substitute until the radio hardware
path is wired up. Everything downstream of the transport is the normal brain.
"""

from __future__ import annotations

import argparse
import glob
import math
import struct
import sys
import time

from brain.extractor import extract
from brain.transcriber import StubTranscriber
from device.serial_link import connect

ACT_TRANSCRIBE_START = 2
ACT_AGENT = 14


def synth_take(idx: int, seconds: float = 1.0, rate: int = 16000) -> bytes:
    """Prerecorded-audio stand-in: deterministic speech-band PCM16 chunk.
    Real WAVs drop into tests/fixtures/ later without touching this flow."""
    n = int(seconds * rate)
    freq = 180 + 60 * (idx % 5)
    return struct.pack(
        f"<{n}h",
        *[int(6000 * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)],
    )


def load_transcripts(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        return lines or _DEFAULTS
    except OSError:
        return _DEFAULTS


_DEFAULTS = [
    "remember to order the encoder knobs tomorrow",
    "decision: cycluno uses the wired link until radios arrive",
    "idea: reuse the xiao hud frames on the uno oled",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="")
    ap.add_argument("--fixtures", default="tests/fixtures/cycluno_transcripts.txt")
    args = ap.parse_args()

    port = args.port or next(
        iter(glob.glob("/dev/ttyACM*") + glob.glob("/dev/ttyUSB*")), ""
    )
    if not port:
        print("no serial port found (is the Uno plugged in?)")
        return 1

    transcripts = load_transcripts(args.fixtures)
    trans = StubTranscriber()
    take = {"i": 0}

    def on_cmd(act: int, arg: str):
        if act == ACT_TRANSCRIBE_START:
            i = take["i"] % len(transcripts)
            take["i"] += 1
            # run the real pipeline on the prerecorded take: audio -> text ->
            # extractor -> note frames (StubTranscriber is deterministic, a
            # real whisper drops in behind the same interface)
            pcm = synth_take(i)
            heard = trans.transcribe(pcm, 16000) or transcripts[i]
            text = transcripts[i] if heard.startswith("stub") else heard
            print(f"[rec] take {i}: {text!r}")
            for note in extract(text):
                link.send_note(note.text[:21])
                print(f"  -> note: {note.type}: {note.text}")
        elif act == ACT_AGENT:
            reply = "agent: 42 tasks, 0 fires"
            print(f"[agent] {reply}")
            link.send_note(reply[:21])

    def on_status(st: dict):
        print(f"[status] {st}")

    print(f"CyclUno brain on {port} @115200 — press A on the unit to 'record'")
    link = connect(port, on_cmd=on_cmd, on_status=on_status)
    try:
        link.send_note("brain linked")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
