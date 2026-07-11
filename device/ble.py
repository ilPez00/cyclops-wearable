"""Bluetooth LE link to the Cyclops wearable (GATT central).

The XIAO/Arduino runs a NimBLE *peripheral* exposing one service with a
NOTE characteristic (Nordic-UART style: READ | NOTIFY | WRITE). The phone/PC
is the *central*: it scans for the service UUID, connects, subscribes to
NOTIFY, and pipes every incoming frame through a streaming :class:`Decoder`
into a :class:`HudBridge`. Commands are written back as frames.

The actual radio is pluggable behind :class:`BleBackend` so the *pairing,
subscribe, dispatch and write* logic is fully testable offline with
:class:`FakeBleBackend` (no bluez / no hardware required).
"""
from __future__ import annotations

import json
import os

# Shared with firmware/xiao (NimBLE UUIDs) and Android CyclopsService.
SRVC_UUID = os.environ.get("CYCLOPS_BLE_SRVC",
                           "4fafc201-1fb5-459e-8fcc-c5c9c331914b")
NOTE_UUID = os.environ.get("CYCLOPS_BLE_NOTE",
                           "beb5483e-36e1-4688-b7f5-ea07361b26a8")
DEVICE_NAME = os.environ.get("CYCLOPS_BLE_NAME", "CyclopsXIAO")


class BleBackend:
    """Radio abstraction. Implement with `bleak` for real hardware.

    A backend connects to the peripheral, subscribes to NOTIFY on the NOTE
    characteristic, and calls ``on_bytes(chunk)`` for every notification. Writes
    go back as raw bytes on the same characteristic.
    """
    def connect(self, on_bytes, timeout=20):
        raise NotImplementedError
    def write(self, data: bytes):
        raise NotImplementedError
    def disconnect(self):
        pass


class FakeBleBackend(BleBackend):
    """In-memory backend: you push bytes in, it delivers them to the link's
    ``on_bytes`` callback; writes are captured in ``written`` for assertions."""
    def __init__(self):
        self.on_bytes = None
        self.connected = False
        self.paired = False
        self.written = []

    def connect(self, on_bytes, timeout=20):
        self.on_bytes = on_bytes
        self.connected = True
        self.paired = True

    def write(self, data: bytes):
        assert self.connected, "write before connect"
        self.written.append(bytes(data))
        return len(data)

    def push(self, data: bytes):
        """Simulate a NOTIFY from the peripheral -> central callback."""
        assert self.on_bytes is not None, "not connected"
        self.on_bytes(bytes(data))

    def disconnect(self):
        self.connected = False


class BleLink:
    """GATT-central link: pairs, subscribes to NOTIFY, decodes v2 wire frames
    (``AA 55 <len> <typ><payload> <crc>`` — see ``brain.protocol``) and dispatches
    them to a :class:`HudBridge`, and writes command frames back to the wearable.

    Speaks the SAME v2 binary protocol as the firmware and the Android
    ``CyclopsService`` so there is a single source of truth across the three
    codebases (no plain-JSON divergence).
    """

    def __init__(self, bridge, backend: "BleBackend | None" = None,
                 srvc=SRVC_UUID, note=NOTE_UUID, timeout=20):
        self.bridge = bridge
        self.backend = backend or FakeBleBackend()
        self.srvc = srvc
        self.note = note
        self.timeout = timeout
        self.paired = False
        self.connected = False
        from brain.protocol import Decoder
        self._decoder = Decoder(self._on_frame)

    def connect(self):
        self.backend.connect(on_bytes=self._on_bytes, timeout=self.timeout)
        self.connected = True
        self.paired = True
        return self

    def _on_bytes(self, chunk: bytes):
        # Streaming v2 decode — robust to fragmentation/interleaving.
        self._decoder.feed(chunk)

    def _on_frame(self, typ: int, payload: bytes):
        # A v2 CMD (typ=9) frame carries an INNER command as JSON
        # {"a":<ACT_*>, "arg":"..."} (the firmware/HUD command contract).
        # Unwrap it so the bridge gets the real action; fall back to a raw
        # dispatch(typ, text) for non-JSON payloads.
        try:
            inner = json.loads(payload.decode("utf-8", "replace"))
            if isinstance(inner, dict) and "a" in inner:
                self.bridge.dispatch(int(inner["a"]), str(inner.get("arg", "")))
                return
        except Exception:
            pass
        arg = payload.decode("utf-8", "replace")
        try:
            self.bridge.dispatch(typ, arg)
        except Exception:
            pass

    def send_cmd(self, cmd: int, arg: str = "") -> str:
        import json

        from brain.protocol import encode
        payload = json.dumps({"a": cmd, "arg": arg}).encode("utf-8")
        frame = encode(9, payload)
        self.backend.write(frame)
        return f"wrote cmd {cmd} ({len(frame)}B)"

    def push_hud(self, text: str) -> str:
        # HUD_FRAME = 14 in the v2 protocol.
        return self.send_cmd(14, text)

    def close(self):
        self.backend.disconnect()
        self.connected = False


class BleTransport:
    """Transport adapter wrapping :class:`BleLink` so the device layer can drive
    the BLE link through the unified transport interface (``send_cmd`` / ``close``).

    Created by ``device.transport.build_transport(kind="ble")``. Keeps the radio
    pluggable behind ``backend`` (real ``bleak`` or :class:`FakeBleBackend` for
    offline tests) — same shape as the rest of the transport family.
    """

    name = "ble"

    def __init__(self, bridge=None, backend=None, srvc="", note="", name="",
                 timeout=20):
        self.bridge = bridge
        self.link = BleLink(bridge=bridge, backend=backend,
                            srvc=srvc or SRVC_UUID, note=note or NOTE_UUID,
                            timeout=timeout)
        self.device_name = name or DEVICE_NAME

    def connect(self):
        self.link.connect()
        return self

    def send_cmd(self, act: int, arg: str = "") -> str:
        return self.link.send_cmd(act, arg)

    def push_hud(self, text: str) -> str:
        return self.link.send_cmd(14, text)

    def request(self, path: str) -> dict:
        return {"ok": True, "transport": "ble",
                "note": "streaming link; use wifi for REST"}

    def close(self):
        self.link.close()


__all__ = ["BleBackend", "FakeBleBackend", "BleLink", "BleTransport",
           "SRVC_UUID", "NOTE_UUID", "DEVICE_NAME"]
