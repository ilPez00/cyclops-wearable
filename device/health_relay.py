"""Phone -> wearable health relay (P2-C).

When the COLMI R02 / G2 R1 ring is connected to the *phone* (not directly to
the XIAO), the companion fuses vitals (see health_fuse) and relays them to the
wearable over the existing BLE link as a MSG_HEALTH_SAMPLE frame, so the HUD
shows live HR even though the ring never touched the XIAO.

The send path is injectable (frame -> bytes callable) so the relay is fully
testable without Bluetooth: a fake transport records the frames it would push.
"""

from __future__ import annotations

from brain.protocol_v2 import MSG_HEALTH_SAMPLE, parse_health


def relay_health(aggregator, send_frame, ts: int = 0) -> bytes:
    """Build a HEALTH_SAMPLE from a fused aggregator and push it to the wearable.

    ``send_frame(msg_type, payload)`` is the injectable transport (real code
    calls encode_frame + BLE notify). Returns the payload that was sent.
    """
    payload = aggregator.to_frame(ts)
    send_frame(MSG_HEALTH_SAMPLE, payload)
    return payload


def parse_wearable_health(payload: bytes) -> dict:
    """What the wearable decodes on the other end (mirror of Hud.on_health_sample)."""
    d = parse_health(payload)
    return {
        "hr": d.get("hr", 0) or 0,
        "spo2": d.get("spo2", 0) or 0,
        "ring_batt": d.get("batt", 0) or 0,
    }
