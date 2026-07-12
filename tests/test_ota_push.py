"""OTA sender: offline tests against a spec-faithful fake of ota.h's receiver.

FakeOtaDevice mirrors OtaReceiver's observable behavior (state machine, seq
discipline, size/CRC verification, status codes) so the sender's framing and
flow control are exercised end-to-end with zero hardware.
"""

import json
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.ota_push import (
    DEFAULT_CHUNK,
    MSG_OTA_BEGIN,
    MSG_OTA_CHUNK,
    MSG_OTA_END,
    OtaError,
    OtaSender,
    begin_payload,
    parse_ack,
)
from brain.protocol import Decoder


class FakeOtaDevice:
    """Decodes sender frames, mirrors OtaReceiver semantics, emits ACKs."""

    def __init__(self, sender, corrupt_crc=False, drop_acks=0):
        self.dec = Decoder(self._on_frame)
        self.sender = sender
        self.corrupt_crc = corrupt_crc
        self.drop_acks = drop_acks  # swallow the first N ACKs (timeout path)
        self.image = bytearray()
        self.active = False
        self.size = self.crc = self.next_seq = 0
        self.committed = False

    def write(self, frame: bytes):
        self.dec.feed(bytes(frame))

    def _ack(self, seq, st):
        if self.drop_acks > 0:
            self.drop_acks -= 1
            return
        self.sender.on_ack(json.dumps({"seq": seq, "st": st}).encode())

    def _on_frame(self, typ, payload):
        if typ == MSG_OTA_BEGIN:
            if self.active:
                return self._ack(0, 1)  # BUSY
            self.size, self.crc, _chunk = struct.unpack("<III", payload[:12])
            self.image = bytearray()
            self.next_seq = 0
            self.active = True
            return self._ack(0, 0)
        if typ == MSG_OTA_CHUNK:
            if not self.active:
                return self._ack(0, 2)  # BAD_STATE
            seq = struct.unpack("<I", payload[:4])[0]
            if seq != self.next_seq:
                return self._ack(seq, 3)  # BAD_SEQ
            self.image += payload[4:]
            if len(self.image) > self.size:
                self.active = False
                return self._ack(seq, 4)  # OVERFLOW
            self.next_seq += 1
            return self._ack(seq, 0)
        if typ == MSG_OTA_END:
            if not self.active:
                return self._ack(0, 2)
            self.active = False
            if len(self.image) != self.size:
                return self._ack(self.next_seq, 5)  # SIZE_MISMATCH
            want = self.crc + 1 if self.corrupt_crc else self.crc
            if (zlib.crc32(bytes(self.image)) & 0xFFFFFFFF) != want:
                return self._ack(self.next_seq, 6)  # CRC_MISMATCH
            self.committed = True
            return self._ack(self.next_seq, 0)


def _wire(**dev_kw):
    sender = OtaSender(send=lambda f: dev.write(f), chunk=64)
    dev = FakeOtaDevice(sender, **dev_kw)
    return sender, dev


def test_push_happy_path_commits_image():
    sender, dev = _wire()
    image = bytes(range(256)) * 3  # 768 B -> 12 chunks of 64
    n = sender.push(image, timeout=1.0)
    assert n == 12
    assert dev.committed and bytes(dev.image) == image
    assert sender.progress == 1.0
    print("OK full image streams, verifies and commits")


def test_crc_mismatch_raises():
    sender, dev = _wire(corrupt_crc=True)
    try:
        sender.push(b"x" * 100, timeout=1.0)
        assert False, "should raise on CRC mismatch"
    except OtaError as e:
        assert e.status == 6 and "CRC_MISMATCH" in str(e)
    assert not dev.committed
    print("OK CRC mismatch surfaces as OtaError(CRC_MISMATCH)")


def test_ack_timeout_raises():
    sender, dev = _wire(drop_acks=1)  # BEGIN ack swallowed
    try:
        sender.push(b"y" * 10, timeout=0.15)
        assert False, "should time out"
    except OtaError as e:
        assert e.status is None and "timeout" in str(e)
    print("OK lost ACK raises timeout instead of hanging")


def test_busy_receiver_rejects_second_begin():
    sender, dev = _wire()
    dev.active = True  # session already in flight
    try:
        sender.push(b"z" * 10, timeout=1.0)
        assert False
    except OtaError as e:
        assert e.status == 1 and "BUSY" in str(e)
    print("OK BUSY receiver rejects a second session")


def test_begin_payload_layout_matches_ota_h():
    image = b"firmware!"
    p = begin_payload(image, chunk=224)
    size, crc, chunk = struct.unpack("<III", p)
    assert size == len(image) and chunk == 224
    assert crc == (zlib.crc32(image) & 0xFFFFFFFF)
    print("OK BEGIN payload is [size][crc32][chunk] little-endian")


def test_parse_ack_rejects_garbage():
    assert parse_ack(b'{"seq":7,"st":0}') == (7, 0)
    try:
        parse_ack(b"not json")
        assert False
    except ValueError:
        pass
    print("OK ACK parser strict on garbage")


def test_default_chunk_is_mtu_safe():
    assert DEFAULT_CHUNK + 4 + 7 <= 247  # seq header + frame overhead
    print("OK default chunk fits a 247 B notify budget")
