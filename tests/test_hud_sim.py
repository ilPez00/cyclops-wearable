"""Offline: HUD simulator decodes the real wire frames (DISPLAY_CMD + HUD_FRAME)
and renders a glanceable grid. Mirrors the firmware's parse contract so the
wearable UX is testable without hardware (premortem D1/D5)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.protocol_v2 import HUD_KINDS, build_hud
from shells.hud_sim import HudSim


def test_hud_frame():
    sim = HudSim()
    sim.feed_hud_frame(build_hud(HUD_KINDS.index("agent"),
                                 ["Meet Bob at 3pm", "bring the cable"], more=False))
    assert sim.mode == "agent"
    grid = sim.render()
    assert any("Meet Bob" in r for r in grid)
    print("OK HUD_FRAME agent answer rendered")


def test_display_cmd_progress_and_steps():
    sim = HudSim()
    sim.feed_display_cmd(b'{"kind":"progress","p":42}')
    sim.feed_display_cmd(b'{"kind":"step","tool":"device"}')
    sim.feed_display_cmd(b'{"kind":"step","tool":"web"}')
    assert sim.progress == 42
    assert sim.steps == ["device", "web"]
    grid = sim.render()
    assert any("42%" in r for r in grid)
    assert any("device" in r and "web" in r for r in grid)
    print("OK DISPLAY_CMD progress + steps rendered")


def test_display_cmd_text_note():
    sim = HudSim()
    sim.feed_display_cmd(b'{"kind":"text","text":"idea: wire ring HR to HUD"}')
    grid = sim.render()
    assert any("ring HR" in r for r in grid)
    print("OK DISPLAY_CMD text note rendered")


def test_health_status_bar():
    sim = HudSim()
    sim.set_health(hr=72, spo2=97, batt=80)
    grid = sim.render()
    assert any("HR72" in r and "S97%" in r and "B80%" in r for r in grid)
    print("OK health status bar rendered")


def test_grid_geometry():
    sim = HudSim(cols=21, rows=4)
    sim.feed_hud_frame(build_hud(HUD_KINDS.index("agent"), ["a", "b", "c", "d", "e"], more=True))
    grid = sim.render()
    assert len(grid) == 4
    assert all(len(r) == 21 for r in grid)
    print("OK grid is 4x21")


def test_profile_128x128_geometry():
    # The default XIAO S3 Sense target: 21x16 grid (mirrors St7735Screen).
    sim = HudSim(profile="128x128")
    assert (sim.cols, sim.rows) == (21, 16), sim.profile
    grid = sim.render()
    assert len(grid) == 16, f"expected 16 rows, got {len(grid)}"
    assert all(len(r) == 21 for r in grid)
    print("OK 128x128 profile is 21x16 (matches firmware St7735Screen)")


def test_profile_g2_geometry():
    sim = HudSim(profile="g2")
    assert (sim.cols, sim.rows) == (18, 4)
    grid = sim.render()
    assert len(grid) == 4 and all(len(r) == 18 for r in grid)
    print("OK g2 profile is 18x4")


if __name__ == "__main__":
    test_hud_frame()
    test_display_cmd_progress_and_steps()
    test_display_cmd_text_note()
    test_health_status_bar()
    test_grid_geometry()
    test_profile_128x128_geometry()
    test_profile_g2_geometry()
    print("PASS tests/test_hud_sim.py")
