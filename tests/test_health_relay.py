"""Offline: P2-C phone -> wearable health relay.

Fuses ring vitals in the companion and relays a MSG_HEALTH_SAMPLE frame; the
fake transport records what would be pushed, and the parse mirror matches the
firmware Hud.on_health_sample contract (zero = absent).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.protocol_v2 import MSG_HEALTH_SAMPLE
from device.health_fuse import HealthAggregator
from device.health_relay import parse_wearable_health, relay_health


def test_relay_builds_health_sample():
    sent = []

    def send(mtype, payload):
        sent.append((mtype, bytes(payload)))

    agg = HealthAggregator().from_colmi(hr=74, spo2=97, battery=88, ts=1)
    payload = relay_health(agg, send, ts=1000)
    assert sent, "relay must push a frame"
    assert sent[0][0] == MSG_HEALTH_SAMPLE
    d = parse_wearable_health(payload)
    assert d["hr"] == 74 and d["spo2"] == 97 and d["ring_batt"] == 88
    print("OK relay pushes MSG_HEALTH_SAMPLE with fused vitals:", d)


def test_relay_zero_means_absent():
    sent = []
    agg = HealthAggregator().from_colmi(hr=74, spo2=97, battery=88, ts=1)
    # a follow-up partial sample with hr only, spo2/batt=0 (absent)
    agg.from_g2(hr=80, spo2=0, battery=0, ts=2)
    payload = relay_health(agg, lambda m, p: sent.append((m, bytes(p))), ts=1001)
    d = parse_wearable_health(payload)
    assert d["hr"] == 80
    assert d["spo2"] == 97  # unchanged (0 treated as absent)
    assert d["ring_batt"] == 88
    print("OK relay zero-field treated as absent (mirrors firmware)")


def test_relay_empty_safe():
    sent = []
    payload = relay_health(
        HealthAggregator(), lambda m, p: sent.append((m, bytes(p))), ts=0
    )
    d = parse_wearable_health(payload)
    assert d["hr"] == 0 and d["spo2"] == 0 and d["ring_batt"] == 0
    print("OK relay empty-safe zeroed frame")


if __name__ == "__main__":
    test_relay_builds_health_sample()
    test_relay_zero_means_absent()
    test_relay_empty_safe()
    print("PASS tests/test_health_relay.py")
