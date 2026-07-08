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
    decoder exactly as a radio would. Lets tests exercise the full central
    logic without Bluetooth."""
    def __init__(self):
        self.on_bytes = None
        self.written = []
        self.connected = False

    def connect(self, on_bytes, timeout=20):
        self.on_bytes = on_bytes
        self.connected = True

    def write(self, data: bytes):
        assert self.connected, "write before connect"
        self.written.append(bytes(data))

    def push(self, data: bytes):
        """Simulate an incoming NOTIFY from the peripheral."""
        assert self.on_bytes is not None
        self.on_bytes(bytes(data))

    def disconnect(self):
        self.connected = False


class BleLink:
    """GATT central: scans -> connects -> subscribes -> decodes -> bridge.

    Usage::

        link = BleLink(bridge, backend=FakeBleBackend())
        link.connect()                 # pairs + subscribes
        backend.push(encode(MSG_CMD, b'{"a":2}'))   # peripheral -> PC
        link.send_cmd(9, '{"a":1}')    # PC -> peripheral
        link.close()
    """

    def __init__(self, bridge, backend: BleBackend | None = None,
                 srvc: str = SRVC_UUID, note: str = NOTE_UUID,
                 name: str = DEVICE_NAME):
        from brain.protocol import Decoder
        self.bridge = bridge
        self.backend = backend
        self.srvc = srvc
        self.note = note
        self.name = name
        self._dec = Decoder(self._on_frame)
        self.connected = False
        self.paired = False

    # -- public -------------------------------------------------------------
    def connect(self, timeout: int = 20):
        if self.backend is None:
            self.backend = _default_backend(self.srvc, self.note, self.name)
        # "pairing" = discover service + subscribe to NOTIFY (one-shot here)
        self.backend.connect(self._dec.feed, timeout=timeout)
        self.connected = True
        self.paired = True
        return self

    def send_cmd(self, act: int, arg: str = "") -> str:
        import json
        from brain.protocol import encode
        frame = encode(9, json.dumps({"a": act, "arg": arg}).encode())
        self.backend.write(frame)
        return f"ble: wrote cmd {act} ({len(frame)} bytes)"

    def close(self):
        if self.backend is not None:
            self.backend.disconnect()
        self.connected = False

    # -- internals ----------------------------------------------------------
    def _on_frame(self, typ: int, payload: bytes):
        # mirror Android CyclopsService: bytes already decoded; hand to bridge
        try:
            self.bridge.handle_cmd(payload)
        except Exception:
            # a frame the bridge can't route (e.g. raw DISPLAY_CMD/STATUS JSON)
            # is not fatal — drop it like the firmware does for unknown types
            pass


def _default_backend(srvc, note, name):
    """Real backend when `bleak` is installed; else a safe no-op stub."""
    try:
        from ._bleak_backend import BleakBackend
        return BleakBackend(srvc, note, name)
    except Exception:
        return _StubNoRadio(srvc, note, name)


class _StubNoRadio(BleBackend):
    """No Bluetooth stack available. Reports (does not crash) so the agent
    keeps working headless."""
    def connect(self, on_bytes, timeout=20):
        raise RuntimeError(
            "no BLE backend: install `bleak` and ensure a BT adapter, or "
            "inject a FakeBleBackend for tests")
    def write(self, data: bytes):
        raise RuntimeError("no BLE backend")


# ---- Transport adapter (so the agent's `bt` path uses real GATT) ----------
class BleTransport(BleBackend if False else object):
    """Thin adapter exposing the wearable over GATT as a Transport.

    send_cmd/push_hud serialize to a MSG_CMD frame written to the NOTE
    characteristic; incoming NOTIFY frames are decoded and dispatched to the
    bridge. Offline-testable by passing a FakeBleBackend.
    """

    name = "ble"

    def __init__(self, bridge=None, backend=None, srvc: str = SRVC_UUID,
                 note: str = NOTE_UUID, name: str = DEVICE_NAME):
        from brain.hud_bridge import HudBridge
        from brain.store import NoteStore
        from io import StringIO
        self._bridge = bridge or HudBridge(StringIO())
        self._link = BleLink(self._bridge, backend=backend, srvc=srvc,
                             note=note, name=name)
        self._connected = False

    def connect(self, timeout: int = 20):
        self._link.connect(timeout=timeout)
        self._connected = True
        return self

    def send_cmd(self, act: int, arg: str = "") -> str:
        if not self._connected:
            self.connect()
        return self._link.send_cmd(act, arg)

    def push_hud(self, text: str) -> str:
        # ACT_AGENT(14) streams glanceable text to the wearable
        return self.send_cmd(14, text)

    def request(self, path: str) -> dict:
        return {"ok": True, "transport": "ble",
                "note": "streaming link; use wifi for REST"}

    def close(self):
        self._link.close()
        self._connected = False
