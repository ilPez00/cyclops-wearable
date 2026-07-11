"""End-to-end demo: simulate the device feeding audio to the brain, which
extracts smart notes and pushes them to the screen + store + dashboard.

Run:  python3 demo.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from brain.display import G2GlassesSink, LocalScreenSink
from brain.pipeline import Pipeline
from brain.store import NoteStore
from brain.transcriber import StubTranscriber
from device.simulator import DeviceSim

TMP = "/tmp/cyclops_demo.jsonl"


class FakeSerial:
    def __init__(self):
        self.frames = []

    def write(self, b):
        self.frames.append(b)


def main():
    if os.path.exists(TMP):
        os.remove(TMP)
    store = NoteStore(TMP)
    serial = FakeSerial()
    screen = LocalScreenSink(serial)  # XIAO HUD
    glasses = G2GlassesSink(serial)  # G2 variant
    captured = []

    def on_note(n):
        captured.append(n)
        screen.render(n)  # -> device display frame
        glasses.render(n)  # -> G2 HUD frame

    dev = DeviceSim()
    p = Pipeline(store, transcriber=StubTranscriber(), on_note=on_note)

    print("=== Cyclops demo: audio -> brain -> notes -> screen ===")
    samples = [
        "Remind me to send the invoice to Marco by friday",
        "We decided to ship the MVP next week",
        "Idea: add a vibration alert when a task is captured",
        "Call the dentist to book an appointment tomorrow",
    ]
    for s in samples:
        print(f"\n[AUDIO] {s}")
        notes = p.process_text(s)
        for n in notes:
            dev.add_note(f"{n.type}: {n.text}")
        for line in dev.screen():
            print("  HUD |", line)

    # simulate input events
    print("\n[INPUT] scroll down twice, then btn_a (record)")
    dev.wheel(1)
    dev.wheel(1)
    dev.btn_a()
    for line in dev.screen():
        print("  HUD |", line)

    print(
        f"\n=== Stored {len(store.all())} notes; frames to device: {len(serial.frames)} ==="
    )
    md = store.dump_markdown("/tmp/cyclops_demo.md")
    print("Markdown export:")
    print(md)
    print("\nDemo OK.")


if __name__ == "__main__":
    main()
