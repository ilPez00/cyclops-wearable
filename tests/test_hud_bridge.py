import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.hud_bridge import HudBridge
from brain.protocol import MSG
from brain.protocol_v2 import (
    ACT_AGENT,
    ACT_CAMERA,
    ACT_CONFIRM_YES,
    ACT_HEALTH,
    ACT_IMAGE_ANALYSIS,
    ACT_PHOTO,
    ACT_SSH,
    ACT_TELEPROMPTER,
    ACT_TRANSCRIBE_START,
    ACT_TRANSLATE,
    ACT_VIDEO,
    ACT_VOICE_CMD,
    ACT_VOICE_NOTE,
    decode,
    encode,
)
from brain.store import NoteStore
from brain.transcriber import StubTranscriber


class Cap:
    def __init__(self): self.frames=[]
    def write(self, b): self.frames.append(b)


class SpeakSink:
    """Sink that implements speak() + records TTS frames (the audio-out path)."""
    def __init__(self): self.frames=[]; self.spoken=[]
    def write(self, b): self.frames.append(b)
    def speak(self, text): self.spoken.append(text)

def test_each_action_returns_frame():
    if os.path.exists("/tmp/cyclops_hb.jsonl"): os.remove("/tmp/cyclops_hb.jsonl")
    store = NoteStore("/tmp/cyclops_hb.jsonl")
    cap = Cap()
    br = HudBridge(cap, store=store, transcriber=StubTranscriber())
    # transcribe -> note stored + frame
    br.dispatch(ACT_TRANSCRIBE_START)
    assert len(store.all()) >= 1
    assert any(b"TRANSCRIBE" in f or b"DISPLAY_CMD" in f for f in cap.frames)
    # translate
    cap2 = Cap(); br.sink = cap2; br.dispatch(ACT_TRANSLATE, "ciao riunione")
    assert any(b"TR:" in f for f in cap2.frames)
    # health
    cap3 = Cap(); br.sink = cap3; br.dispatch(ACT_HEALTH)
    # teleprompter -> hud frame
    cap4 = Cap(); br.sink = cap4; br.dispatch(ACT_TELEPROMPTER)
    assert len(cap4.frames) >= 1
    # camera / image / ssh / confirm
    for a in (ACT_CAMERA, ACT_IMAGE_ANALYSIS, ACT_SSH, ACT_CONFIRM_YES):
        c = Cap(); br.sink = c; br.dispatch(a)
        assert len(c.frames) >= 1

def test_cmd_roundtrip_parse():
    # firmware emits MSG_CMD; bridge parses it back
    cap = Cap()
    br = HudBridge(cap)
    payload = json.dumps({"a": ACT_TRANSLATE, "arg": "ciao"}).encode()
    frame = encode(MSG["CMD"], payload)
    typ, pl = decode(frame)
    assert typ == MSG["CMD"]
    res = br.handle_cmd(pl)
    assert res[0] == "translate"

def test_frame_receiver_end_to_end():
    # simulate the firmware emitting a v2 MSG_CMD frame over a byte stream
    from brain.hud_bridge import MSG_CMD, FrameReceiver, HudBridge
    from brain.protocol import MSG
    from brain.protocol_v2 import encode
    cap = Cap()
    br = HudBridge(cap)
    # firmware builds the same frame the MCU would: MSG_CMD with translate action
    payload = json.dumps({"a": ACT_TRANSLATE, "arg": "ciao"}).encode()
    frame = encode(MSG_CMD, payload)
    rcv = FrameReceiver(br)
    rcv.feed(frame)
    assert any(b"TR:" in f for f in cap.frames), "bridge should have emitted a translate frame"

def test_audio_capture_roundtrip():
    from brain.hud_bridge import MSG_CMD, FrameReceiver, HudBridge
    from brain.protocol import MSG, encode
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber
    if os.path.exists("/tmp/cyclops_audio.jsonl"): os.remove("/tmp/cyclops_audio.jsonl")
    cap = Cap()
    store = NoteStore("/tmp/cyclops_audio.jsonl")
    br = HudBridge(cap, store=store, transcriber=StubTranscriber())
    rcv = FrameReceiver(br)
    # device announces 16-bit/16k then streams 100 bytes of fake PCM, then stops
    meta = bytes([16,0, 16000&255, (16000>>8)&255, 1,0,0,0])
    rcv.feed(encode(MSG["AUDIO_META"], meta))
    rcv.feed(encode(MSG["AUDIO_CHUNK"], b"\x00\x01"*50))
    rcv.feed(encode(MSG["AUDIO_STOP"], b""))
    assert len(store.all()) >= 1, "transcribe on STOP should store a note"
    assert any(b"TRANSCRIBE" in f for f in cap.frames)
    os.remove("/tmp/cyclops_audio.jsonl")

def test_auto_transcriber_returns_transcriber():
    from brain.transcriber import StubTranscriber, Transcriber, get_transcriber
    # auto must never raise and must return a usable Transcriber
    t = get_transcriber("auto")
    assert isinstance(t, Transcriber)
    # explicit stub stays stub (deterministic, used in tests)
    assert isinstance(get_transcriber("stub"), StubTranscriber)

def test_bridge_uses_injected_transcriber():
    cap = Cap()
    from brain.transcriber import StubTranscriber
    br = HudBridge(cap, transcriber=StubTranscriber())
    assert br.trans is not None
    # dispatch transcribe stores a note and emits a frame
    if os.path.exists("/tmp/cyclops_inj.jsonl"): os.remove("/tmp/cyclops_inj.jsonl")
    from brain.store import NoteStore
    br2 = HudBridge(cap, store=NoteStore("/tmp/cyclops_inj.jsonl"), transcriber=StubTranscriber())
    br2.dispatch(ACT_TRANSCRIBE_START)
    assert len(br2.store.all()) >= 1
    os.remove("/tmp/cyclops_inj.jsonl")

def test_new_capture_actions_emit_frames():
    cap = Cap()
    br = HudBridge(cap, transcriber=StubTranscriber())
    for a in (ACT_PHOTO, ACT_VIDEO):
        c = Cap(); br.sink = c; br.dispatch(a)
        assert len(c.frames) >= 1, "photo/video must emit a frame"

def test_voice_note_stores_and_speaks():
    if os.path.exists("/tmp/cyclops_vn.jsonl"): os.remove("/tmp/cyclops_vn.jsonl")
    sink = SpeakSink()
    br = HudBridge(sink, store=NoteStore("/tmp/cyclops_vn.jsonl"), transcriber=StubTranscriber())
    res = br.dispatch(ACT_VOICE_NOTE)
    assert res[0] == "voice_note"
    assert len(br.store.all()) >= 1, "voice note should store a transcript"
    assert sink.spoken and "saved" in sink.spoken[-1], "voice note should TTS an ack"
    os.remove("/tmp/cyclops_vn.jsonl")

def test_voice_cmd_is_interactive_speaks_answer():
    # B-long: spoken question -> agent -> spoken answer (audio-out)
    sink = SpeakSink()
    br = HudBridge(sink, agent=_FakeAgent("The meeting is at 3pm."), transcriber=StubTranscriber())
    res = br.dispatch(ACT_VOICE_CMD)
    assert res[0] == "voice_cmd"
    assert any("3pm" in s for s in sink.spoken), "answer should be spoken back (audio-out)"
    # generic sink without speak() must still emit a TTS frame, not crash
    cap = Cap(); br2 = HudBridge(cap, agent=_FakeAgent("ok"), transcriber=StubTranscriber())
    br2.dispatch(ACT_VOICE_CMD)
    assert any(MSG["TTS"] and b"ok" in f for f in cap.frames), "TTS frame emitted when no speak()"

class _FakeAgent:
    def __init__(self, ans): self.ans = ans; self.progress_cb = None
    def run(self, prompt):
        return type("R", (), {"text": self.ans, "steps": []})()
