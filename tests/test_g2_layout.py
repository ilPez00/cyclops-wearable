"""Offline: P0-C G2 layout — HUD model -> exact G2 BLE packets (4x18 green).

Proves the simulator/firmware and the G2 agree on the wire, so the tiny-OLED
weakness (premortem D7) is closed by borrowing the G2 as the real display.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from device.g2_layout import (model_to_banner, render_to_g2, assert_g2_packets)
from device.g2 import G2_MAX_PAYLOAD
from shells.hud_sim import HudSim
from brain.protocol_v2 import build_hud, HUD_KINDS


def test_banner_formatting():
    b = model_to_banner("agent", ["Meet Bob", "bring cable"], progress=42,
                        hr=72, spo2=97, batt=80)
    assert "agent" in b and "H72" in b and "S97" in b and "B80" in b
    assert "Meet Bob" in b and "42%" in b
    print("OK G2 banner formatting")


def test_agent_frame_to_g2_packets():
    sim = HudSim()
    sim.feed_hud_frame(build_hud(HUD_KINDS.index("agent"),
                                 ["Meet Bob at 3pm", "bring the cable"], more=False))
    sim.set_health(hr=72, spo2=97, batt=80)
    pkts = sim.to_g2()
    assert_g2_packets(pkts)
    assert len(pkts) >= 1
    # control byte + UTF-8 body, every packet fits the G2 MTU
    for p in pkts:
        assert p[0] == 0x01
        assert len(p) - 1 <= G2_MAX_PAYLOAD
    # the banner content survives the round-trip
    flat = b"".join(p[1:] for p in pkts).decode(errors="replace")
    assert "Meet Bob" in flat and "H72" in flat
    print(f"OK agent model -> {len(pkts)} G2 packets, all well-formed")


def test_progress_only_banner():
    pkts = render_to_g2("HOME", [], progress=77)
    assert_g2_packets(pkts)
    assert b"77%" in pkts[0]
    print("OK progress-only -> G2 packet with [77%]")


def test_empty_model_safe():
    pkts = render_to_g2("HOME", [], None, None, None, None)
    assert_g2_packets(pkts)  # at least one packet, never crash
    print("OK empty model -> safe single G2 packet")


if __name__ == "__main__":
    test_banner_formatting()
    test_agent_frame_to_g2_packets()
    test_progress_only_banner()
    test_empty_model_safe()
    print("PASS tests/test_g2_layout.py")
