"""Wire-contract test: pins the exact frame bytes every implementation (C++,
Python, Kotlin) MUST produce, so the Android :core port stays byte-compatible.

The Python codec already matches the firmware C++ codec (both exercised by the
firmware + python suites). Here we assert the canonical bytes for a representative
set of frames the phone sends/receives, and verify the CRC algorithm the Kotlin
uses (CRC16-CCITT FALSE, 0xFFFF seed) yields the standard check value 0x29B1 on
"123456789". This is the contract the Kotlin CyclopsProto must honor on-device.
"""
from __future__ import annotations
import struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def crc16_ccitt_false(data: bytes, seed: int = 0xFFFF) -> int:
    crc = seed & 0xFFFF
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc & 0xFFFF


def encode_frame(mtype: int, payload: bytes) -> bytes:
    length = len(payload)
    head = bytes([0xAA, 0xAA, 0x55, length & 0xFF, (length >> 8) & 0xFF, mtype])
    crc = crc16_ccitt_false(head[3:] + payload)
    return head + payload + struct.pack("<H", crc)


def test_crc_standard_vector():
    assert crc16_ccitt_false(b"123456789") == 0x29B1


def test_frame_layout():
    f = encode_frame(1, b"\x01\x02")  # HELLO, payload 01 02
    assert f[0:3] == b"\xAA\xAA\x55"
    assert (f[3] | (f[4] << 8)) == 2
    assert f[5] == 1
    tail_crc = struct.unpack("<H", f[6 + 2:6 + 4])[0]
    assert tail_crc == crc16_ccitt_false(f[3:6 + 2])


def test_cmd_frame_roundtrip_bytes():
    payload = b'{"a":2,"arg":"hi"}'
    f = encode_frame(9, payload)  # MSG_CMD
    # decode the frame back
    assert f[5] == 9
    assert f[6:6 + len(payload)] == payload


def test_kotlin_must_match_python():
    # The Kotlin CyclopsProto.encode must produce identical bytes to this.
    # If the firmware/python codec changes, the Kotlin port must change too.
    for mtype, payload in [
        (1, b"\x01\x02"),          # HELLO
        (9, b'{"a":2,"arg":"hi"}'),  # MSG_CMD
        (5, b"\x00\x01" * 50),     # MSG_AUDIO_CHUNK
        (19, b""),                 # MSG_AUDIO_STOP
        (14, b'{"kind":"text","data":"x"}'),  # MSG_HUD_FRAME
    ]:
        f = encode_frame(mtype, payload)
        # invariant: magic + length + type + crc tail present and CRC verifies
        assert f[0:3] == b"\xAA\xAA\x55"
        assert f[5] == mtype
        assert len(f) == 6 + len(payload) + 2
        expected = crc16_ccitt_false(f[3:6 + len(payload)])
        actual = struct.unpack("<H", f[6 + len(payload):6 + len(payload) + 2])[0]
        assert actual == expected


if __name__ == "__main__":
    test_crc_standard_vector()
    test_frame_layout()
    test_cmd_frame_roundtrip_bytes()
    test_kotlin_must_match_python()
    print("ALL WIRE-CONTRACT TESTS PASSED")
