import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.hud_bridge import HudBridge
from brain.protocol import encode, MSG
from brain.protocol_v2 import encode, decode, ACT_TRANSCRIBE_START, ACT_TRANSLATE, ACT_HEALTH, ACT_TELEPROMPTER, ACT_CAMERA, ACT_IMAGE_ANALYSIS, ACT_SSH, ACT_CONFIRM_YES
from brain.transcriber import StubTranscriber
from brain.store import NoteStore


class Cap:
    def __init__(self): self.frames=[]
    def write(self, b): self.frames.append(b)

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
    from brain.hud_bridge import HudBridge, FrameReceiver, MSG_CMD
    from brain.protocol_v2 import encode
    from brain.protocol import MSG
    cap = Cap()
    br = HudBridge(cap)
    # firmware builds the same frame the MCU would: MSG_CMD with translate action
    payload = json.dumps({"a": ACT_TRANSLATE, "arg": "ciao"}).encode()
    frame = encode(MSG_CMD, payload)
    rcv = FrameReceiver(br)
    rcv.feed(frame)
    assert any(b"TR:" in f for f in cap.frames), "bridge should have emitted a translate frame"
