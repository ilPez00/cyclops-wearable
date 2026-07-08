import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.protocol_v2 import build_hud, parse_hud, build_health, parse_health, encode, decode, peer_hello
from brain.health import HealthStore, HealthSample
from brain.ring_client import RingClient
from brain.display import G2GlassesSink, ArduinoSink, LocalScreenSink, ConsoleSink
from brain.store import NoteStore
from brain.pipeline import Pipeline
from brain.transcriber import StubTranscriber

class FakeT:
    def __init__(self): self.sent=[]
    def write(self, b): self.sent.append(b)

def test_hud_roundtrip():
    f = build_hud(0, ["Buy milk", "Call mom"], more=True)
    d = parse_hud(f)
    assert d["kind"]==0 and d["lines"]==["Buy milk","Call mom"] and d["more"] is True

def test_health_roundtrip():
    b = build_health(1717000000000, 72, 98, 2, 3900)
    d = parse_health(b)
    assert d["hr"]==72 and d["spo2"]==98 and d["batt"]==3900

def test_health_join():
    hs = HealthStore("/tmp/cyclops_health_test.jsonl")
    if os.path.exists("/tmp/cyclops_health_test.jsonl"): os.remove("/tmp/cyclops_health_test.jsonl")
    hs = HealthStore("/tmp/cyclops_health_test.jsonl")
    now = int(time.time()*1000)
    hs.add(HealthSample(t=now-1000, hr=80))
    hs.add(HealthSample(t=now+1000, hr=84))
    assert hs.avg_hr_around(now) == 82

def test_ring_client():
    rc = RingClient(HealthStore("/tmp/cyclops_ring_test.jsonl"))
    if os.path.exists("/tmp/cyclops_ring_test.jsonl"): os.remove("/tmp/cyclops_ring_test.jsonl")
    rc = RingClient(HealthStore("/tmp/cyclops_ring_test.jsonl"))
    s = rc.on_health_bytes(build_health(int(time.time()*1000), 70, 97, 0, 3800))
    assert s.hr == 70
    g = rc.on_gesture(2)
    assert g == "long"
    fr = rc.gesture_frame(2)
    assert decode(fr)[0] == 15  # MSG_RING_GESTURE

def test_g2_sink_trim():
    t = FakeT(); sink = G2GlassesSink(t)
    from brain.extractor import Note
    sink.render(Note("x","task","a"*100))
    assert len(t.sent)==1
    d = parse_hud(t.sent[0])
    assert d["kind"]==0 and len(d["lines"])==1

def test_pipeline_health_enrich():
    if os.path.exists("/tmp/cyclops_ph.jsonl"): os.remove("/tmp/cyclops_ph.jsonl")
    if os.path.exists("/tmp/cyclops_pn.jsonl"): os.remove("/tmp/cyclops_pn.jsonl")
    hs = HealthStore("/tmp/cyclops_ph.jsonl")
    now = int(time.time()*1000); hs.add(HealthSample(t=now, hr=90))
    store = NoteStore("/tmp/cyclops_pn.jsonl")
    p = Pipeline(store, transcriber=StubTranscriber(), health=hs)
    notes = p.process_text("I need to call Marco")
    assert any("bpm" in n.text for n in notes)

def test_peer_hello():
    b = peer_hello("bead", ["mic","ble"])
    assert b'"peer": "bead"'.split(b" ")[1] in b or b'"peer": "bead"'.replace(b" ",b"") in b
