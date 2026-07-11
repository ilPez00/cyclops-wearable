"""Offline: P1-D unified health frame — fuse COLMI R02 + Omi + G2/R1."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.protocol_v2 import parse_health
from device.health_fuse import HealthAggregator, Reading


def test_multi_source_fusion():
    agg = HealthAggregator()
    agg.from_colmi(hr=72, spo2=97, battery=80, ts=100)
    agg.from_omi(hr=75, ts=200)          # newer HR wins
    agg.from_g2(spo2=98, battery=55, ts=300)  # newer SpO2 wins
    snap = agg.snapshot()
    assert snap["hr"] == 75, snap
    assert snap["spo2"] == 98, snap
    assert snap["batt"] == 80          # ring drives fused batt
    assert snap["batteries"] == {"ring": 80, "g2": 55}
    print("OK multi-source fusion (newest field wins, ring batt)")


def test_stale_reading_ignored():
    agg = HealthAggregator()
    agg.from_omi(hr=75, ts=200)
    agg.from_colmi(hr=60, ts=100)  # older -> ignored
    assert agg.hr == 75
    print("OK stale reading ignored")


def test_round_trip_frame():
    agg = HealthAggregator().from_colmi(hr=66, spo2=95, battery=42, ts=5)
    frame = agg.to_frame(ts=5)
    d = parse_health(frame)
    assert d["hr"] == 66 and d["spo2"] == 95 and d["batt"] == 42 and d["t"] == 5
    print("OK round-trips through HEALTH_SAMPLE:", d)


def test_empty_safe():
    agg = HealthAggregator()
    d = parse_health(agg.to_frame())
    assert d["hr"] == 0 and d["batt"] == 0
    print("OK empty aggregator -> zeroed safe frame")


def test_battery_source_override():
    agg = HealthAggregator(battery_source="g2")
    agg.from_g2(battery=55, ts=1)
    assert agg.batt == 55
    print("OK battery_source override selects g2")


def test_health_tool_vitals():
    import json

    from agent.config import AgentConfig
    from agent.tools.health import make_health_tool
    agg = HealthAggregator().from_colmi(hr=70, spo2=96, battery=88, ts=1)
    t = make_health_tool(AgentConfig(), aggregator=agg)
    snap = json.loads(t.run({"action": "vitals"}))
    assert snap["hr"] == 70 and snap["spo2"] == 96 and snap["batt"] == 88
    print("OK health tool vitals action -> fused snapshot")


if __name__ == "__main__":
    test_multi_source_fusion()
    test_stale_reading_ignored()
    test_round_trip_frame()
    test_empty_safe()
    test_battery_source_override()
    test_health_tool_vitals()
    print("PASS tests/test_health_fuse.py")
