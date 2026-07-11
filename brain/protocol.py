"""Python mirror of the device wire protocol (see protocol/protocol.md)."""

from __future__ import annotations

import struct

MAGIC1, MAGIC2 = 0xAA, 0x55
MSG = {
    "HELLO": 1,
    "HEARTBEAT": 2,
    "INPUT_EVENT": 3,
    "AUDIO_META": 4,
    "AUDIO_CHUNK": 5,
    "DISPLAY_CMD": 6,
    "NOTE": 7,
    "STATUS": 8,
    "CMD": 9,
    "ACK": 10,
    "PEER_HELLO": 11,
    "TIME_SYNC": 12,
    "HEALTH_SAMPLE": 13,
    "HUD_FRAME": 14,
    "RING_GESTURE": 15,
    "AUDIO_COMPRESSED": 16,
    "CONFIRM": 17,
    "PEER_STATUS": 18,
    "AUDIO_STOP": 19,
    "TTS": 20,
}


def crc16_ccitt_false(data, seed=0xFFFF):
    crc = seed
    for b in data:
        crc ^= b << 8
        crc = crc % 0x10000
        for _ in range(8):
            if crc >= 0x8000:
                crc = ((crc << 1) ^ 0x1021) % 0x10000
            else:
                crc = (crc << 1) % 0x10000
    return crc


def encode(typ, payload):
    if len(payload) > 1024:
        raise ValueError("payload too long")
    # CRC covers len(2)+type(1)+payload — same window as the firmware
    # encode_frame/FrameDecoder and Kotlin CyclopsProto (wire contract).
    window = struct.pack("<H", len(payload)) + bytes([typ]) + payload
    crc = crc16_ccitt_false(window)
    return bytes([MAGIC1, MAGIC2]) + window + struct.pack("<H", crc)


def decode_frame(frame):
    if len(frame) < 7 or frame[0] != MAGIC1 or frame[1] != MAGIC2:
        return None
    plen = struct.unpack("<H", frame[2:4])[0]
    typ = frame[4]
    payload = frame[5 : 5 + plen]
    crc_recv = struct.unpack("<H", frame[5 + plen : 7 + plen])[0]
    crc = crc16_ccitt_false(frame[2 : 5 + plen])
    if crc != crc_recv:
        return None
    return (typ, payload)


class Decoder:
    """Streaming frame decoder (mirrors the Kotlin/Firmware Decoder).

    Feed arbitrary chunks of bytes; `on_frame(typ, payload)` is called once per
    complete, CRC-valid frame. Robust to fragmentation and interleaving.
    """

    S_M1, S_M2, S_LEN_LO, S_LEN_HI, S_BODY, S_CRC_LO, S_CRC_HI = range(7)

    def __init__(self, on_frame):
        self.on_frame = on_frame
        self.buf = bytearray()
        self.got = 0
        self.plen = 0
        self.len_lo = 0
        self.pending_crc_lo = 0
        self.state = self.S_M1

    def feed(self, data: bytes):
        for b in data:
            self._byte(b)

    def _byte(self, b):
        if self.state == self.S_M1:
            if b == MAGIC1:
                self.state = self.S_M2
        elif self.state == self.S_M2:
            self.state = self.S_LEN_LO if b == MAGIC2 else self.S_M1
        elif self.state == self.S_LEN_LO:
            self.len_lo = b
            self.state = self.S_LEN_HI
        elif self.state == self.S_LEN_HI:
            self.plen = self.len_lo | (b << 8)
            self.got = 0
            self.buf = bytearray()
            self.state = self.S_BODY
        elif self.state == self.S_BODY:
            self.buf.append(b)
            self.got += 1
            if self.got >= self.plen + 1:  # +1 type byte
                self.state = self.S_CRC_LO
        elif self.state == self.S_CRC_LO:
            self.pending_crc_lo = b
            self.state = self.S_CRC_HI
        elif self.state == self.S_CRC_HI:
            typ = self.buf[0]
            payload = bytes(self.buf[1:])
            crc_recv = self.pending_crc_lo | (b << 8)
            window = struct.pack("<H", self.plen) + bytes(self.buf)  # len+type+payload
            if crc16_ccitt_false(window) == crc_recv:
                self.on_frame(typ, payload)
            self._reset()

    def _reset(self):
        self.state = self.S_M1
        self.buf = bytearray()
        self.got = 0
        self.plen = 0
        self.len_lo = 0
        self.pending_crc_lo = 0
