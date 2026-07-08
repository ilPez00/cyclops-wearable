"""Python mirror of the device wire protocol (see protocol/protocol.md)."""
from __future__ import annotations
import struct

MAGIC1, MAGIC2 = 0xAA, 0x55
MSG = {"HELLO":1,"HEARTBEAT":2,"INPUT_EVENT":3,"AUDIO_META":4,"AUDIO_CHUNK":5,
       "DISPLAY_CMD":6,"NOTE":7,"STATUS":8,"CMD":9,"ACK":10}

def crc16_ccitt_false(data, seed=0xFFFF):
    crc = seed
    for b in data:
        crc ^= (b << 8)
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
    body = bytes([typ]) + payload
    crc = crc16_ccitt_false(body)
    return bytes([MAGIC1, MAGIC2]) + struct.pack("<H", len(payload)) + body + struct.pack("<H", crc)

def decode_frame(frame):
    if len(frame) < 7 or frame[0] != MAGIC1 or frame[1] != MAGIC2:
        return None
    plen = struct.unpack("<H", frame[2:4])[0]
    typ = frame[4]
    payload = frame[5:5+plen]
    crc_recv = struct.unpack("<H", frame[5+plen:7+plen])[0]
    crc = crc16_ccitt_false(bytes([typ]) + payload)
    if crc != crc_recv:
        return None
    return (typ, payload)
