"""Offline: P1-C G2/R1 gestures -> HUD input.

Covers the gesture protocol (encode/parse), the firmware dispatch (host gate
has its own block), and the Python bridge routing a RING_GESTURE frame:
nav gestures forward to the sink, `nod` triggers transcription.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.protocol_v2 import (build_ring_gesture, parse_ring_gesture,
                               MSG_RING_GESTURE, encode, decode, GEST)
from brain.hud_bridge import HudBridge, FrameReceiver


def test_gesture_protocol_roundtrip():
    for name in ("up", "down", "select", "back", "nod", "home"):
        payload = build_ring_gesture(name)
        d = parse_ring_gesture(payload)
        assert d["name"] == name, (name, d)
        assert d["code"] == GEST[name]
    # numeric input also works
    assert parse_ring_gesture(build_ring_gesture(2))["name"] == "down"
    print("OK gesture protocol round-trip (name<->code)")


def test_bridge_forwards_nav_gesture():
    class Cap:
        def __init__(self): self.frames = []
        def write(self, b): self.frames.append(b)
        def render_text(self, t): pass
    br = HudBridge(Cap())
    name = br.handle_gesture(build_ring_gesture("select"))
    assert name == "select"
    assert br.last_gesture == "select"
    # nav gesture forwarded to sink as b"G" + code
    assert any(f == b"G" + bytes([GEST["select"]]) for f in br.sink.frames)
    print("OK bridge forwards nav gesture to sink")


def test_bridge_nod_triggers_transcribe():
    class Cap:
        def __init__(self): self.frames = []
        def write(self, b): self.frames.append(b)
        def render_text(self, t): pass
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber
    store = NoteStore("/tmp/cyclops_gesture.jsonl")
    if os.path.exists("/tmp/cyclops_gesture.jsonl"): os.remove("/tmp/cyclops_gesture.jsonl")
    br = HudBridge(Cap(), store=store, transcriber=StubTranscriber())
    br.handle_gesture(build_ring_gesture("nod"))
    assert br.last_gesture == "nod"
    assert len(store.all()) >= 1
    print("OK bridge nod -> transcription captured")


def test_frame_receiver_routes_gesture():
    class Cap:
        def __init__(self): self.frames = []
        def write(self, b): self.frames.append(b)
        def render_text(self, t): pass
    br = HudBridge(Cap())
    fr = FrameReceiver(br)
    # build a RING_GESTURE v2 frame and stream it byte-by-byte
    frame = encode(MSG_RING_GESTURE, build_ring_gesture("home"))
    fr.feed(frame)
    assert br.last_gesture == "home"
    print("OK FrameReceiver routes RING_GESTURE -> handle_gesture")


if __name__ == "__main__":
    test_gesture_protocol_roundtrip()
    test_bridge_forwards_nav_gesture()
    test_bridge_nod_triggers_transcribe()
    test_frame_receiver_routes_gesture()
    print("PASS tests/test_gesture.py")
