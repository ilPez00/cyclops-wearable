"""Offline: P0-B OpenGlass/XIAO camera capture + vision pipeline.

Uses FakeCamera (no hardware) and an injectable HTTP session so the whole
capture -> base64 -> vision path is exercised without a real camera/network.
"""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.config import AgentConfig
from agent.tools.camera import make_camera_tool
from device.camera import FakeCamera, OpenGlassCamera


def test_camera_registered_in_registry():
    from agent.tools import build_registry
    reg = build_registry(AgentConfig())
    assert "camera" in reg.names()
    print("OK camera tool registered")


def test_fake_camera_capture_no_analyze():
    cfg = AgentConfig()
    cam = FakeCamera(b"\xff\xd8JPEGDATA\xff\xd9")
    tool = make_camera_tool(cfg, session=None, source=cam)  # offline: returns bytes info
    out = tool.run({})
    assert "captured frame" in out and "JPEGDATA" not in out  # base64, not raw
    assert "12 bytes" in out  # len(b'\xff\xd8JPEGDATA\xff\xd9') == 12
    print("OK fake camera capture (no analyze) -> base64 len reported")


def test_fake_camera_analyze_offline_stub():
    cfg = AgentConfig(local_mode=True)
    cam = FakeCamera(b"\xff\xd8ABCD\xff\xd9")
    tool = make_camera_tool(cfg, session=None, source=cam)
    out = tool.run({"analyze": True, "prompt": "what?"})
    assert "offline: vision would analyze frame" in out
    print("OK fake camera analyze -> offline vision stub")


class FakeResp:
    def __init__(self, payload): self._p = payload
    def json(self): return self._p


def test_fake_camera_analyze_with_vision_session():
    cfg = AgentConfig(local_mode=True, local_base_url="http://localhost:11434/v1")
    cam = FakeCamera(b"\xff\xd8VISION\xff\xd9")

    class S:
        def post(self, url, data=None, headers=None, timeout=None):
            return FakeResp({"choices": [{"message": {"content": "a red apple on a table"}}]})

    tool = make_camera_tool(cfg, session=S(), source=cam)
    out = tool.run({"analyze": True, "prompt": "describe"})
    assert "red apple" in out
    print("OK fake camera analyze -> vision returns description")


def test_openglass_camera_offline_returns_none():
    cam = OpenGlassCamera("192.168.1.99", 8080, session=None)  # no session
    assert cam.capture() is None
    print("OK OpenGlass camera offline -> None (safe)")


if __name__ == "__main__":
    test_camera_registered_in_registry()
    test_fake_camera_capture_no_analyze()
    test_fake_camera_analyze_offline_stub()
    test_fake_camera_analyze_with_vision_session()
    test_openglass_camera_offline_returns_none()
    print("PASS tests/test_camera_tool.py")
