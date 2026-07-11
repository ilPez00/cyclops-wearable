"""EvenRealities G2 glasses HUD transport (BLE central).

The G2 are a thin dedicated HUD: the brain streams a glanceable banner and the
glasses render it on the right lens. This module is the *transport* only — it
takes already-rendered text (from :class:`brain.hud_bridge.HudBridge`) and
delivers it over BLE to the G2 GATT characteristic. The radio is pluggable
behind :class:`G2Backend` so the framing + write/subscribe logic is fully
testable offline with :class:`FakeG2Backend` (no Bluetooth hardware needed).

G2 BLE (per the open G1/G2 reverse-engineering; override via env if yours differ):
  service      fee3cccc-...   (CYCLOPS_G2_SRVC)
  char (write) fee3dd11-...   (CYCLOPS_G2_CHAR)
Text packets: a leading 0x01 control byte + UTF-8 payload (<= G2_MAX_PAYLOAD).
"""

from __future__ import annotations

import os

G2_SRVC = os.environ.get("CYCLOPS_G2_SRVC", "fee3cccc-9c78-4d5e-8247-1b3a6c0e1f2a")
G2_CHAR = os.environ.get("CYCLOPS_G2_CHAR", "fee3dd11-9c78-4d5e-8247-1b3a6c0e1f2b")
G2_MAX_PAYLOAD = int(os.environ.get("CYCLOPS_G2_MAX", "18"))
G2_TX_CONTROL = 0x01  # start-of-text marker the G2 firmware expects


class G2Backend:
    """Radio abstraction for the G2. Implement with `bleak` for real hardware."""

    def connect(self, timeout=20):
        raise NotImplementedError

    def write(self, data: bytes):
        raise NotImplementedError

    def disconnect(self):
        pass


class FakeG2Backend(G2Backend):
    """In-memory G2 radio. Records every packet the bridge would send."""

    def __init__(self):
        self.connected = False
        self.packets = []

    def connect(self, timeout=20):
        self.connected = True

    def write(self, data: bytes):
        assert self.connected, "write before connect"
        self.packets.append(bytes(data))

    def disconnect(self):
        self.connected = False


def build_g2_packet(text: str) -> bytes:
    """Render one glanceable line into a G2 BLE packet (control byte + UTF-8)."""
    payload = text.encode("utf-8")[:G2_MAX_PAYLOAD]
    return bytes([G2_TX_CONTROL]) + payload


def split_g2(text: str) -> list[bytes]:
    """Split a (possibly multi-line) banner into <=MAX_PAYLOAD G2 packets."""
    lines = [ln for ln in text.split("\n") if ln][:4] or [text]
    out = []
    for ln in lines:
        # chunk long lines so each packet fits the G2 MTU
        while ln:
            out.append(build_g2_packet(ln[:G2_MAX_PAYLOAD]))
            ln = ln[G2_MAX_PAYLOAD:]
    return out


class G2Transport(G2Backend if False else object):
    """Deliver glanceable banners to the G2 glasses over BLE.

    Usable directly:

        g2 = G2Transport(backend=FakeG2Backend())
        g2.connect()
        g2.show("Turn left in 200m")     # -> G2 BLE packets
        g2.close()
    """

    name = "g2"

    def __init__(
        self, backend: G2Backend | None = None, srvc: str = G2_SRVC, char: str = G2_CHAR
    ):
        self.backend = backend
        self.srvc = srvc
        self.char = char
        self._connected = False

    def connect(self, timeout: int = 20):
        if self.backend is None:
            self.backend = _default_backend(self.srvc, self.char)
        self.backend.connect(timeout=timeout)
        self._connected = True
        return self

    def show(self, text: str) -> int:
        """Send a glanceable banner. Returns the number of G2 packets sent."""
        if not self._connected:
            self.connect()
        pkts = split_g2(text)
        for p in pkts:
            self.backend.write(p)
        return len(pkts)

    def close(self):
        if self.backend is not None:
            self.backend.disconnect()
        self._connected = False


class G2HudSink:
    """A brain ``Sink`` that mirrors HUD frames onto the G2 glasses.

    Implements both ``write(frame_bytes)`` (for HUD_FRAME/DISPLAY_CMD payloads)
    and ``render_text(text)`` (for plain banners), so it drops into
    :class:`brain.hud_bridge.HudBridge` as ``sink=``. Text is converted to a
    glanceable banner; binary display frames are decoded best-effort.
    """

    def __init__(
        self, transport: G2Transport | None = None, backend: G2Backend | None = None
    ):
        self.transport = transport or G2Transport(backend=backend)
        self.last = []

    def connect(self):
        self.transport.connect()
        return self

    def render_text(self, text: str):
        n = self.transport.show(text)
        self.last.append(("text", text, n))

    def write(self, frame: bytes):
        # best-effort: pull a banner out of DISPLAY_CMD/HUD_FRAME payloads
        try:
            from brain.protocol import decode_frame
            from brain.protocol_v2 import parse_hud

            d = decode_frame(frame)
            if d:
                typ, payload = d
                if typ in (14,):  # HUD_FRAME
                    hud = parse_hud(payload)
                    banner = " ".join(hud.get("lines", [])) or payload.decode(
                        errors="replace"
                    )
                else:
                    import json

                    obj = json.loads(payload.decode(errors="replace"))
                    banner = obj.get("data") or obj.get("text") or str(obj)
            else:
                banner = frame.decode(errors="replace")
        except Exception:
            banner = frame.decode(errors="replace")
        self.transport.show(banner)

    def close(self):
        self.transport.close()


def _default_backend(srvc, char):
    try:
        from ._bleak_backend import G2BleakBackend

        return G2BleakBackend(srvc, char)
    except Exception:
        raise RuntimeError(
            "no BLE backend for G2: install `bleak` + a BT adapter, "
            "or inject a FakeG2Backend for tests"
        )
