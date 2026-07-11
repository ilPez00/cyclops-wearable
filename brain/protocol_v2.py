"""Python mirror of protocol v2 (see protocol/protocol_v2.md)."""

from __future__ import annotations

import json
import struct

MSGV2 = {
    "PEER_HELLO": 11,
    "TIME_SYNC": 12,
    "HEALTH_SAMPLE": 13,
    "HUD_FRAME": 14,
    "RING_GESTURE": 15,
    "AUDIO_COMPRESSED": 16,
    "CONFIRM": 17,
    "PEER_STATUS": 18,
}
PEERS = ("bead", "glasses", "ring", "phone", "brain")
HUD_KINDS = ("note", "notify", "teleprompter", "clear", "agent")

# Ring/glasses gesture ids (G2 R1 tap/swipe, COLMI wheel) -> HUD nav.
GEST = {"up": 1, "down": 2, "select": 3, "back": 4, "nod": 5, "home": 6}
GEST_NAME = {v: k for k, v in GEST.items()}

# HUD action ids (mirror of firmware/lib/cyclops_shared/include/hud.h Action)
ACT_NOTES = 1
ACT_TRANSCRIBE_START = 2
ACT_TRANSLATE = 3
ACT_HEALTH = 4
ACT_NAV = 5
ACT_TELEPROMPTER = 6
ACT_CAMERA = 7
ACT_IMAGE_ANALYSIS = 8
ACT_SSH = 9
ACT_SETTINGS = 10
ACT_CONFIRM_YES = 11
ACT_CONFIRM_NO = 12
ACT_SELECT = 13
ACT_AGENT = 14
ACT_AGENT_ABORT = 15
ACT_PHOTO = 16
ACT_VIDEO = 17
ACT_VOICE_NOTE = 18
ACT_VOICE_CMD = 19
ACT_OK = 20
ACT_BACK = 21
ACT_CONSENT_TOGGLE = 22


# numeric constants for convenience
MSG_PEER_HELLO = MSGV2["PEER_HELLO"]
MSG_TIME_SYNC = MSGV2["TIME_SYNC"]
MSG_HEALTH_SAMPLE = MSGV2["HEALTH_SAMPLE"]
MSG_HUD_FRAME = MSGV2["HUD_FRAME"]
MSG_RING_GESTURE = MSGV2["RING_GESTURE"]
MSG_AUDIO_COMPRESSED = MSGV2["AUDIO_COMPRESSED"]
MSG_CONFIRM = MSGV2["CONFIRM"]
MSG_PEER_STATUS = MSGV2["PEER_STATUS"]


from .protocol import MAGIC1, MAGIC2, crc16_ccitt_false  # noqa: E402


def encode(typ, payload):
    if isinstance(payload, str):
        payload = payload.encode()
    # CRC covers len(2)+type(1)+payload — firmware/Kotlin wire-contract window
    window = struct.pack("<H", len(payload)) + bytes([typ]) + payload
    crc = crc16_ccitt_false(window)
    return bytes([MAGIC1, MAGIC2]) + window + struct.pack("<H", crc)


def decode(frame):
    from .protocol import decode_frame

    return decode_frame(frame)


# ---- HUD frame (compact, no JSON, matches C++ build_hud_frame) ----
def build_hud(kind: int, lines: list, more: bool = False) -> bytes:
    out = f"K{kind}\n".encode()
    for ln in lines[:4]:
        s = ln[:18]
        out += b"L" + s.encode() + b"\n"
    out += b"M" + (b"1" if more else b"0") + b"\n"
    return out


def parse_hud(payload: bytes) -> dict:
    text = payload.decode(errors="replace")
    kind = None
    lines = []
    more = False
    for raw in text.split("\n"):
        if not raw:
            continue
        tag = raw[0]
        val = raw[1:]
        if tag == "K":
            kind = int(val)
        elif tag == "L":
            lines.append(val)
        elif tag == "M":
            more = val == "1"
    return {"kind": kind, "lines": lines, "more": more}


def build_hud_agent(text: str, more: bool = False) -> bytes:
    """Wrap a multi-line agent answer into an HUD 'agent' frame (Omi/G2 style)."""
    lines = [ln for ln in text.split("\n") if ln][:4]
    return build_hud(HUD_KINDS.index("agent"), lines, more)


# ---- HEALTH sample ----
def build_health(t, hr, spo2, sleep_stage, batt_mv) -> bytes:
    return f"t={t},hr={hr},spo2={spo2},sl={sleep_stage},batt={batt_mv}".encode()


def parse_health(payload: bytes) -> dict:
    d = {}
    for kv in payload.decode(errors="replace").split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            d[k] = int(v)
    return d


# ---- RING/glasses gesture ----
def build_ring_gesture(gesture) -> bytes:
    """Encode a gesture (name or id) as a RING_GESTURE payload."""
    code = GEST[gesture] if isinstance(gesture, str) else int(gesture)
    return bytes([code])


def parse_ring_gesture(payload: bytes) -> dict:
    code = payload[0] if payload else 0
    return {"code": code, "name": GEST_NAME.get(code, "?")}


def peer_hello(peer, caps, fw="0.1", v=2) -> bytes:
    return json.dumps({"v": v, "peer": peer, "caps": list(caps), "fw": fw}).encode()


def time_sync(utc_ms: int, acc_ms: int = 50) -> bytes:
    return json.dumps({"t": utc_ms, "acc": acc_ms}).encode()
