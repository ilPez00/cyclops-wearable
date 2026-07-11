"""Offline: P0-D Consent Mode (Omi-style privacy gate).

- consent tool toggles config.consent_mode
- capture + camera tools refuse when consent is OFF
- HudSim surfaces a REC / consent-off indicator
- firmware consent gate verified separately via `make test` (10/10)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.config import AgentConfig
from agent.tools.consent import make_consent_tool, consent_required
from agent.tools.wearable import make_capture_tool
from agent.tools.camera import make_camera_tool
from device.camera import FakeCamera
from shells.hud_sim import HudSim


def test_consent_tool_toggle():
    cfg = AgentConfig()
    t = make_consent_tool(cfg)
    assert "ON" in t.run({"action": "status"})
    out = t.run({"action": "off"})
    assert "OFF" in out and not cfg.consent_mode
    assert consent_required(cfg) is True
    assert "ON" in t.run({"action": "on"})
    assert consent_required(cfg) is False
    print("OK consent tool toggles config")


def test_capture_blocked_without_consent():
    cfg = AgentConfig()
    cfg.consent_mode = False
    t = make_capture_tool(cfg, session=None)
    out = t.run({"action": "capture", "media": "photo"})
    assert "consent OFF" in out
    # hud/notify are NOT gated
    make_capture_tool(cfg, session=None)  # reuse but action differs
    from agent.tools.wearable import make_hud_tool
    ht = make_hud_tool(cfg, session=None)
    assert "offline" in ht.run({"text": "hi"})  # hud still works
    print("OK capture refused when consent off; hud unaffected")


def test_camera_blocked_without_consent():
    cfg = AgentConfig()
    cfg.consent_mode = False
    t = make_camera_tool(cfg, session=None, source=FakeCamera())
    assert "consent OFF" in t.run({})
    print("OK camera refused when consent off")


def test_hud_sim_rec_and_consent_indicators():
    sim = HudSim()
    sim.set_rec(True)
    sim.set_consent(False)
    grid = sim.render()
    assert any("REC" in r for r in grid)
    assert any(" X" in r for r in grid)
    print("OK HudSim shows REC + consent-off indicator")


if __name__ == "__main__":
    test_consent_tool_toggle()
    test_capture_blocked_without_consent()
    test_camera_blocked_without_consent()
    test_hud_sim_rec_and_consent_indicators()
    print("PASS tests/test_consent.py")
