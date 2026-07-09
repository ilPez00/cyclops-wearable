"""Offline tests for device transports + the device tool routing."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from device.transport import (FakeTransport, WifiTransport, BluetoothTransport,
                              CableTransport, build_transport)
from device.ble import BleLink, FakeBleBackend
from agent.config import AgentConfig
from agent.tools.device import make_device_tool


def test_fake_transport():
    f = FakeTransport()
    f.add_note("buy milk")
    assert f.request("/api/notes")[0]["text"] == "buy milk"
    f.send_cmd(7, "audio")
    assert f.cmds[-1] == (7, "audio")
    f.push_hud("turn left")
    assert f.huds[-1] == "turn left"


def test_bt_serial_file():
    import tempfile
    p = tempfile.mktemp(suffix=".log")
    bt = BluetoothTransport(serial_file=p)
    out = bt.push_hud("hello glasses")
    assert "file" in out
    bt.close()
    lines = open(p, encoding="utf-8").read().strip().splitlines()
    assert json.loads(lines[-1]) == {"a": 14, "arg": "hello glasses"}


def test_cable_tty_missing_is_safe():
    c = CableTransport(tty="")  # no link
    out = c.send_cmd(14, "x")
    assert "queued" in out


def test_build_transport_unknown():
    try:
        build_transport("warp")
        assert False, "should raise"
    except ValueError:
        pass


def test_device_tool_routes_hud_over_fake():
    cfg = AgentConfig()
    f = FakeTransport()
    tool = make_device_tool(cfg, transport=f)
    out = tool.run({"action": "hud", "text": "meeting in 5"})
    assert "fake: hud" in out
    assert f.huds[-1] == "meeting in 5"


def test_device_tool_status_per_transport():
    cfg = AgentConfig()
    for kind in ("wifi", "bt", "cable"):
        t = build_transport(kind, config=cfg)
        tool = make_device_tool(cfg, transport=t)
        out = tool.run({"action": "status"})
        assert kind in out


def test_device_tool_capture_sends_camera_cmd():
    cfg = AgentConfig()
    f = FakeTransport()
    tool = make_device_tool(cfg, transport=f)
    tool.run({"action": "capture", "media": "photo"})
    assert f.cmds[-1] == (7, "photo")

def test_serial_reader_closes_loop_into_bridge():
    import tempfile
    from device.transport import SerialFrameReader
    from brain.hud_bridge import HudBridge
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber

    class Cap:
        def __init__(self): self.frames = []
        def write(self, b): self.frames.append(b)

    cap = Cap()
    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    br = HudBridge(cap, store=store, transcriber=StubTranscriber())
    reader = SerialFrameReader(br)

    # fragment the stream across chunks to prove buffering works
    reader.feed('{"a":1}\n{"a":2,"arg":"c')
    assert len(store.all()) == 0  # only the first complete line consumed
    reader.feed('iao note"}\n')      # completes the 2nd frame
    assert len(store.all()) >= 1  # transcribe action stored a note from the streamed frame
    assert cap.frames  # display frame emitted back
    os.remove(sp)


def test_ble_link_pair_subscribe_dispatch():
    import tempfile, json
    from brain.hud_bridge import HudBridge
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber
    from brain.protocol import encode

    class Cap:
        def __init__(self): self.frames = []
        def write(self, b): self.frames.append(b)

    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    br = HudBridge(Cap(), store=store, transcriber=StubTranscriber())
    backend = FakeBleBackend()
    link = BleLink(br, backend=backend)
    link.connect()
    assert link.paired and link.connected
    frame = encode(9, json.dumps({"a": 2, "arg": "Remind me to call mom by friday"}).encode())
    backend.push(frame)
    assert any(n.type == "reminder" for n in store.all())
    os.remove(sp)


def test_ble_link_pc_to_peripheral_write():
    from brain.hud_bridge import HudBridge
    from brain.protocol import decode_frame
    import io

    br = HudBridge(io.StringIO())
    backend = FakeBleBackend()
    link = BleLink(br, backend=backend)
    link.connect()
    out = link.send_cmd(1, "ping")
    assert "wrote cmd 1" in out
    assert backend.written
    typ, payload = decode_frame(backend.written[-1])
    assert typ == 9 and b"ping" in payload


def test_device_tool_routes_ble_transport():
    import tempfile, json
    from device.ble import FakeBleBackend
    from device.transport import build_transport
    from brain.hud_bridge import HudBridge
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber
    from brain.protocol import encode
    import io, os

    class Cap:
        def __init__(self): self.frames = []
        def write(self, b): self.frames.append(b)

    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    br = HudBridge(Cap(), store=store, transcriber=StubTranscriber())
    backend = FakeBleBackend()
    # build the ble transport wired to our bridge via the backend
    t = build_transport("ble", bridge=br, backend=backend)
    t.connect()
    # PC -> wearable: glanceable HUD text becomes a MSG_CMD(14) frame
    out = t.push_hud("meeting in 5")
    assert "wrote cmd 14" in out and backend.written
    # wearable -> PC: a NOTIFY CMD frame is decoded and stored as a note
    frame = encode(9, json.dumps({"a": 2, "arg": "idea: ship the demo"}).encode())
    backend.push(frame)  # peripheral NOTIFY -> decoded -> bridge -> note stored
    assert len(store.all()) >= 1
    t.close()
    os.remove(sp)


def test_g2_transport_sends_packets():
    from device.g2 import G2Transport, FakeG2Backend
    be = FakeG2Backend()
    g2 = G2Transport(backend=be)
    g2.connect()
    n = g2.show("Turn left in 200m")
    assert n >= 1 and be.connected
    assert be.packets[0][0] == 1
    assert b"Turn left" in be.packets[0]
    g2.close()


def test_g2_sink_as_bridge_sink():
    import tempfile
    from device.g2 import G2HudSink, FakeG2Backend
    from brain.hud_bridge import HudBridge
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber

    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    be = FakeG2Backend()
    sink = G2HudSink(backend=be)
    br = HudBridge(sink, store=store, transcriber=StubTranscriber())
    br.push_hud("Meeting with marco at 5")
    assert be.packets, "G2 should have received at least one packet"
    assert any(b"marco" in pk for pk in be.packets)
    if os.path.exists(sp):
        os.remove(sp)
