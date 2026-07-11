"""Colmi R02 ring BLE client (phone side).

The ring is a Nordic nRF52832 device exposing HR/SpO/sleep/battery + a touch
button (tap/double/long/swipe). On the phone we run a BLE GATT client; here we
model the message handling and map gestures -> cyclops actions. Real BLE uses
android.bluetooth via the companion app; this module is the protocol/state logic.
"""
from __future__ import annotations

from .health import HealthSample, HealthStore
from .protocol_v2 import (
    MSG_HEALTH_SAMPLE,
    MSG_RING_GESTURE,
    build_health,
    encode,
    parse_health,
)

GESTURE_MAP = {0:"tap",1:"double",2:"long",3:"swipe"}

class RingClient:
    def __init__(self, health: HealthStore | None = None):
        self.health = health or HealthStore()
        self.last_gesture = None
    def on_health_bytes(self, payload: bytes):
        d = parse_health(payload)
        s = HealthSample(t=d.get("t",0), hr=d.get("hr",0), spo2=d.get("spo2",0),
                         sleep_stage=d.get("sl",0), batt_mv=d.get("batt",0))
        self.health.add(s)
        return s
    def on_gesture(self, g: int) -> str:
        name = GESTURE_MAP.get(g, "tap")
        self.last_gesture = name
        return name
    def gesture_frame(self, g: int) -> bytes:
        name = self.on_gesture(g)
        return encode(MSG_RING_GESTURE, f'{{"g":"{name}"}}'.encode())
