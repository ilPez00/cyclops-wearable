"""OTA-over-BLE sender — the phone/PC side of firmware/shared/include/ota.h.

The receiver (OtaReceiver, verified by `make proto`) speaks:

    -> MSG_OTA_BEGIN (21)  [size:u32][crc32:u32][chunk:u32]   little-endian
    -> MSG_OTA_CHUNK (22)  [seq:u32][data...]                 strictly seq 0..n
    -> MSG_OTA_END   (23)  (empty)                            verify + commit
    <- MSG_OTA_ACK   (24)  {"seq":n,"st":code}                per message

Stop-and-wait flow control: every BEGIN/CHUNK/END must be ACKed with st=OK
before the next message goes out — BLE notifies are unordered under loss, and
the receiver hard-rejects out-of-order seq anyway, so windowing buys nothing.

Transport-agnostic: `send` is any callable taking one encoded frame (e.g.
``BleLink.backend.write`` or a serial pipe); incoming MSG_OTA_ACK payloads are
fed to ``on_ack`` from the caller's receive path. Fully offline-testable.
"""

from __future__ import annotations

import json
import struct
import threading
import zlib

from .protocol import encode

MSG_OTA_BEGIN = 21
MSG_OTA_CHUNK = 22
MSG_OTA_END = 23
MSG_OTA_ACK = 24

# Receiver status codes (ota.h OtaStatus).
OTA_OK = 0
OTA_STATUS_NAMES = {
    0: "OK",
    1: "BUSY",
    2: "BAD_STATE",
    3: "BAD_SEQ",
    4: "OVERFLOW",
    5: "SIZE_MISMATCH",
    6: "CRC_MISMATCH",
    7: "FLASH_ERR",
}

DEFAULT_CHUNK = 224  # data bytes per CHUNK; +4 seq +7 framing stays MTU-safe


class OtaError(RuntimeError):
    """Raised when the receiver rejects a step or an ACK times out."""

    def __init__(self, step: str, status: int | None, seq: int | None = None):
        self.step, self.status, self.seq = step, status, seq
        name = (
            OTA_STATUS_NAMES.get(status, str(status))
            if status is not None
            else "timeout"
        )
        super().__init__(
            f"OTA {step} failed: {name}" + (f" (seq {seq})" if seq is not None else "")
        )


def begin_payload(image: bytes, chunk: int = DEFAULT_CHUNK) -> bytes:
    return struct.pack("<III", len(image), zlib.crc32(image) & 0xFFFFFFFF, chunk)


def chunk_payload(seq: int, data: bytes) -> bytes:
    return struct.pack("<I", seq) + data


def parse_ack(payload: bytes) -> tuple[int, int]:
    """MSG_OTA_ACK json -> (seq, status). Raises ValueError on garbage."""
    d = json.loads(payload.decode("utf-8"))
    return int(d["seq"]), int(d["st"])


class OtaSender:
    """Drives one OTA session over any frame transport.

    Usage:
        sender = OtaSender(send=link.backend.write)
        # route incoming MSG_OTA_ACK payloads to sender.on_ack(payload)
        sender.push(image_bytes, timeout=5.0)
    """

    def __init__(self, send, chunk: int = DEFAULT_CHUNK):
        self.send = send
        self.chunk = int(chunk)
        self._ack = None  # (seq, status) of the latest ACK
        self._evt = threading.Event()
        self.progress = 0.0  # 0..1, updated per acked chunk

    # -- receive path (call from the transport's frame dispatcher) ----------
    def on_ack(self, payload: bytes) -> None:
        try:
            self._ack = parse_ack(bytes(payload))
        except (ValueError, KeyError):
            return  # garbage ACK: ignore, the timeout will surface it
        self._evt.set()

    # -- send path -----------------------------------------------------------
    def _step(self, step: str, typ: int, payload: bytes, timeout: float):
        self._evt.clear()
        self._ack = None
        self.send(encode(typ, payload))
        if not self._evt.wait(timeout):
            raise OtaError(step, None)
        seq, st = self._ack
        if st != OTA_OK:
            raise OtaError(step, st, seq)
        return seq

    def push(self, image: bytes, timeout: float = 5.0) -> int:
        """Send a full image. Returns the number of chunks on success.
        Raises OtaError on any rejection/timeout (receiver self-aborts)."""
        if not image:
            raise ValueError("empty image")
        self.progress = 0.0
        self._step("begin", MSG_OTA_BEGIN, begin_payload(image, self.chunk), timeout)
        total = (len(image) + self.chunk - 1) // self.chunk
        for seq in range(total):
            data = image[seq * self.chunk : (seq + 1) * self.chunk]
            self._step(f"chunk {seq}", MSG_OTA_CHUNK, chunk_payload(seq, data), timeout)
            self.progress = (seq + 1) / total
        self._step("end", MSG_OTA_END, b"", timeout)
        return total


__all__ = [
    "OtaSender",
    "OtaError",
    "begin_payload",
    "chunk_payload",
    "parse_ack",
    "MSG_OTA_BEGIN",
    "MSG_OTA_CHUNK",
    "MSG_OTA_END",
    "MSG_OTA_ACK",
    "OTA_OK",
    "OTA_STATUS_NAMES",
    "DEFAULT_CHUNK",
]
