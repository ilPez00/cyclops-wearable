"""Cyclops device CLI — runs a target variant headlessly for testing/demo.

Modes:
  local   -> XIAO HUD (screen + wheel + buttons)  [default]
  g2      -> EvenRealities G2 glasses HUD over BLE-style sink
  pebble  -> Omi/Pebble wearable mode (audio-first, mic + minimal feedback)

This is the behavioral twin of device/src/device.cpp; the firmware compiles the
same UI/input model on real hardware.
"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.store import NoteStore
from brain.transcriber import StubTranscriber
from brain.pipeline import Pipeline
from brain.display import LocalScreenSink, G2GlassesSink, ConsoleSink
from device.simulator import DeviceSim
from device.battery import BatteryMonitor
from device.gestures import GestureDetector

def run(mode="local", texts=None):
    texts = texts or [
        "Remind me to water the plants by saturday",
        "We decided to refactor the audio pipeline",
        "Idea: cache transcripts locally for privacy",
    ]
    store = NoteStore(f"/tmp/cyclops_{mode}.jsonl")
    serial = type("S", (), {"frames": [], "write": lambda self,b: self.frames.append(b)})()
    if mode == "g2": sink = G2GlassesSink(serial)
    elif mode == "pebble": sink = ConsoleSink()
    else: sink = LocalScreenSink(serial)
    dev = DeviceSim()
    batt = BatteryMonitor()
    gest = GestureDetector()
    captured = []
    def on_note(n):
        captured.append(n); sink.render(n); dev.add_note(f"{n.type}: {n.text}")
    p = Pipeline(store, transcriber=StubTranscriber(), on_note=on_note)
    print(f"=== Cyclops [{mode}] ===")
    for t in texts:
        p.process_text(t)
    if mode == "local":
        for line in dev.screen(): print("HUD |", line)
    # simulate a nod gesture toggling record + battery check
    g = gest.push(0.1, 0.9, 0.0); dev.gesture(g) if g else None
    mv = batt.read_mv()
    print(f"battery: {batt.percent(mv)}% ({mv}mv) low={batt.is_low(mv)}")
    print(f"notes: {len(store.all())}  frames_to_device: {len(serial.frames)}")
    return store, serial, dev

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"
    run(mode)
