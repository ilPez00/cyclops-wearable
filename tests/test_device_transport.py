"""Offline tests for device transports + the device tool routing."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.tools.device import make_device_tool
from device.ble import BleLink, FakeBleBackend
from device.transport import (
    BluetoothTransport,
    CableTransport,
    FakeTransport,
    build_transport,
)


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


def test_resolve_transport_auto():
    import os

    from device.transport import resolve_transport

    saved = os.environ.pop("CYCLOPS_TRANSPORT", None)
    saved_tty = os.environ.pop("CYCLOPS_CABLE_TTY", None)
    saved_ble = os.environ.pop("CYCLOPS_BLE_NAME", None)
    try:
        # explicit env override always wins
        os.environ["CYCLOPS_TRANSPORT"] = "wifi"
        assert resolve_transport() == "wifi"
        del os.environ["CYCLOPS_TRANSPORT"]

        # a present tty -> cable
        import tempfile

        with tempfile.NamedTemporaryFile() as f:
            assert resolve_transport(tty=f.name) == "cable"

        # a configured BLE name with no cable -> ble (no ttyACM/USB in CI)
        import glob

        if not (glob.glob("/dev/ttyACM*") or glob.glob("/dev/ttyUSB*")):
            assert resolve_transport(name="CyclopsXIAO") == "ble"
            # nothing configured -> wifi fallback
            assert resolve_transport() == "wifi"
    finally:
        for k, v in (
            ("CYCLOPS_TRANSPORT", saved),
            ("CYCLOPS_CABLE_TTY", saved_tty),
            ("CYCLOPS_BLE_NAME", saved_ble),
        ):
            if v is not None:
                os.environ[k] = v


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

    from brain.hud_bridge import HudBridge
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber
    from device.transport import SerialFrameReader

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

    cap = Cap()
    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    br = HudBridge(cap, store=store, transcriber=StubTranscriber())
    reader = SerialFrameReader(br)

    # fragment the stream across chunks to prove buffering works
    reader.feed('{"a":1}\n{"a":2,"arg":"c')
    assert len(store.all()) == 0  # only the first complete line consumed
    reader.feed('iao note"}\n')  # completes the 2nd frame
    assert (
        len(store.all()) >= 1
    )  # transcribe action stored a note from the streamed frame
    assert cap.frames  # display frame emitted back
    os.remove(sp)


def test_ble_link_pair_subscribe_dispatch():
    import json
    import tempfile

    from brain.hud_bridge import HudBridge
    from brain.protocol import encode
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    br = HudBridge(Cap(), store=store, transcriber=StubTranscriber())
    backend = FakeBleBackend()
    link = BleLink(br, backend=backend)
    link.connect()
    assert link.paired and link.connected
    frame = encode(
        9, json.dumps({"a": 2, "arg": "Remind me to call mom by friday"}).encode()
    )
    backend.push(frame)
    assert any(n.type == "reminder" for n in store.all())
    os.remove(sp)


def test_ble_link_pc_to_peripheral_write():
    import io

    from brain.hud_bridge import HudBridge
    from brain.protocol import decode_frame

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
    import json
    import os
    import tempfile

    from brain.hud_bridge import HudBridge
    from brain.protocol import encode
    from brain.store import NoteStore
    from brain.transcriber import StubTranscriber
    from device.ble import FakeBleBackend
    from device.transport import build_transport

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

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


def test_ble_link_reconnect_backoff():
    # FlakyBleBackend fails once, then succeeds on 2nd try.
    from device.ble import BleLink, FlakyBleBackend

    class _Bridge:
        def dispatch(self, a, arg):
            pass

    backend = FlakyBleBackend(failures=1)
    link = BleLink(_Bridge(), backend=backend)
    link.connect(retries=3, backoff=0.01)  # backoff tiny for test speed
    assert link.connected and backend.attempts == 2
    print("OK ble link retries then connects")


def test_ble_link_connect_exhausts():
    from device.ble import BleLink, FlakyBleBackend

    class _Bridge:
        def dispatch(self, a, arg):
            pass

    backend = FlakyBleBackend(failures=5)
    link = BleLink(_Bridge(), backend=backend)
    try:
        link.connect(retries=2, backoff=0.01)
        assert False, "should have raised"
    except RuntimeError as e:
        assert "failed after 2" in str(e)
        assert not link.connected
    print("OK ble link raises after exhausting retries")


def test_bleak_backend_offline_contract():
    # Real-radio backend must be import-safe and enforce connect-before-write
    # without touching bleak at module load (bleak may be absent in CI).
    from device.ble import BleakBackend

    b = BleakBackend(name="CyclopsXIAO")
    assert not b.connected
    try:
        b.write(b"\x00")
        assert False, "write before connect must raise"
    except RuntimeError as e:
        assert "connect" in str(e)
    b.disconnect()  # no-op when never connected; must not raise
    print("OK BleakBackend offline contract (import-safe, write guarded)")
