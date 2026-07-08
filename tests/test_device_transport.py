"""Offline tests for device transports + the device tool routing."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from device.transport import (FakeTransport, WifiTransport, BluetoothTransport,
                              CableTransport, build_transport)
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
