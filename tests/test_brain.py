import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo root
from brain.transcriber import StubTranscriber
from brain.extractor import extract, Note
from brain.store import NoteStore
from brain.pipeline import Pipeline
from brain.protocol import encode, decode_frame, MSG, crc16_ccitt_false
from brain.display import ConsoleSink, G2GlassesSink, LocalScreenSink

TMP = "/tmp/cyclops_test_notes.jsonl"

class FakeTransport:
    def __init__(self): self.sent = []
    def write(self, b): self.sent.append(b)

def test_crc_roundtrip():
    f = encode(MSG["HELLO"], b'{"v":1}')
    assert decode_frame(f) == (MSG["HELLO"], b'{"v":1}')
    bad = bytearray(f); bad[6] ^= 0xFF
    assert decode_frame(bytes(bad)) is None

def test_stub_transcriber_runs():
    t = StubTranscriber()
    out = t.transcribe(b"\x00\x00" * 100)
    assert isinstance(out, str) and len(out) > 0

def test_extractor_categories():
    notes = extract("Remind me to send the invoice by friday. We decided to ship the MVP next week. Idea: add a vibration alert.")
    types = {n.type for n in notes}
    assert "reminder" in types and "decision" in types and "idea" in types
    rem = [n for n in notes if n.type == "reminder"][0]
    assert rem.due is not None

def test_pipeline_end_to_end():
    if os.path.exists(TMP): os.remove(TMP)
    store = NoteStore(TMP)
    captured = []
    p = Pipeline(store, transcriber=StubTranscriber(), on_note=captured.append)
    notes = p.process_text("I need to call Marco. We decided to launch on monday.")
    assert len(notes) >= 2
    assert len(captured) == len(notes)
    assert len(store.all()) == len(notes)
    store.dump_markdown("/tmp/cyclops_test.md")
    assert os.path.exists("/tmp/cyclops_test.md")

def test_g2_display_trim():
    from brain.protocol_v2 import parse_hud
    t = FakeTransport()
    sink = G2GlassesSink(t)
    n = Note("x", "task", "a"*100, due=None)
    sink.render(n)
    assert len(t.sent) == 1
    d = parse_hud(t.sent[0])
    assert d["kind"] == 0 and len(d["lines"][0]) <= 18

def test_local_screen_sink():
    t = FakeTransport()
    sink = LocalScreenSink(t)
    sink.render_text("hello")
    assert len(t.sent) == 1
    typ, payload = decode_frame(t.sent[0])
    assert typ == MSG["DISPLAY_CMD"]
