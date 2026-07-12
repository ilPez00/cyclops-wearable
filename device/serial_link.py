"""Wired v2-frame link to a CyclUno (or XIAO on USB) over a serial port.

Same shape as device/ble.py's BleLink, different pipe: the CyclUno dev unit
speaks the shared v2 framing over USB serial @115200, so the whole brain
pipeline (extractor, notes, HUD frames) is reused unchanged — the wire is the
only thing that differs from the BLE wearable.

pyserial is imported lazily inside open_port(); tests inject any file-like
duplex (`read(n) -> bytes`, `write(bytes)`) so the framing and routing logic
runs offline in CI with zero dependencies.
"""

from __future__ import annotations

import json
import threading

from brain.protocol import Decoder, encode

MSG_DISPLAY_CMD = 6
MSG_NOTE = 7
MSG_STATUS = 8
MSG_CMD = 9

BAUD = 115200


def open_port(port: str, baud: int = BAUD):
    """Open a real serial port (lazy pyserial import)."""
    try:
        import serial
    except ImportError as e:  # pragma: no cover - import guard
        raise RuntimeError("pyserial not installed: `pip install pyserial`") from e
    return serial.Serial(port, baud, timeout=0.2)


class SerialLink:
    """Frame router over any duplex device.

    Incoming: MSG_CMD -> on_cmd(act, arg); MSG_STATUS -> on_status(dict).
    Outgoing: send_note(text) / push_display(kind, data) as v2 frames.
    """

    def __init__(self, dev, on_cmd=None, on_status=None):
        self.dev = dev
        self.on_cmd = on_cmd
        self.on_status = on_status
        self.last_status: dict | None = None
        self._decoder = Decoder(self._on_frame)
        self._running = False
        self._thread: threading.Thread | None = None

    # -- lifecycle -----------------------------------------------------------
    def start(self):
        """Read loop on a daemon thread; returns self."""
        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop, name="cycluno-serial", daemon=True
        )
        self._thread.start()
        return self

    def close(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        try:
            self.dev.close()
        except Exception:
            pass

    def _read_loop(self):
        while self._running:
            try:
                chunk = self.dev.read(64)
            except Exception:
                break  # port vanished (unplugged): stop cleanly
            if chunk:
                self._decoder.feed(bytes(chunk))

    # -- incoming ------------------------------------------------------------
    def _on_frame(self, typ: int, payload: bytes):
        if typ == MSG_CMD:
            try:
                d = json.loads(payload.decode("utf-8"))
                act = int(d.get("a", 0))
            except (ValueError, TypeError):
                return  # malformed command: drop, never crash the link
            if self.on_cmd:
                self.on_cmd(act, str(d.get("arg", "")))
        elif typ == MSG_STATUS:
            try:
                self.last_status = json.loads(payload.decode("utf-8"))
            except ValueError:
                return
            if self.on_status:
                self.on_status(self.last_status)

    # -- outgoing ------------------------------------------------------------
    def send_note(self, text: str) -> int:
        """NOTE frame; the device shows it as a glanceable note."""
        frame = encode(MSG_NOTE, json.dumps({"text": text}).encode("utf-8"))
        return self.dev.write(frame)

    def push_display(self, kind: int, data: str) -> int:
        frame = encode(
            MSG_DISPLAY_CMD,
            json.dumps({"kind": kind, "data": data}).encode("utf-8"),
        )
        return self.dev.write(frame)


def connect(port: str, baud: int = BAUD, **cb) -> SerialLink:
    """Convenience: open a real port and start the link."""
    return SerialLink(open_port(port, baud), **cb).start()


__all__ = [
    "SerialLink",
    "connect",
    "open_port",
    "BAUD",
    "MSG_NOTE",
    "MSG_DISPLAY_CMD",
    "MSG_STATUS",
    "MSG_CMD",
]
