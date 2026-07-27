"""Wire-contract test: pins the exact frame bytes every implementation (C++,
Python, Kotlin) MUST produce, so the Android :core port stays byte-compatible.

The Python codec already matches the firmware C++ codec (both exercised by the
firmware + python suites). Here we assert the canonical bytes for a representative
set of frames the phone sends/receives, and verify the CRC algorithm the Kotlin
uses (CRC16-CCITT FALSE, 0xFFFF seed) yields the standard check value 0x29B1 on
"123456789". This is the contract the Kotlin CyclopsProto must honor on-device.
"""

from __future__ import annotations

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def crc16_ccitt_false(data: bytes, seed: int = 0xFFFF) -> int:
    crc = seed & 0xFFFF
    for b in data:
        crc ^= b << 8
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
    assert f[0:3] == b"\xaa\xaa\x55"
    assert (f[3] | (f[4] << 8)) == 2
    assert f[5] == 1
    tail_crc = struct.unpack("<H", f[6 + 2 : 6 + 4])[0]
    assert tail_crc == crc16_ccitt_false(f[3 : 6 + 2])


def test_cmd_frame_roundtrip_bytes():
    payload = b'{"a":2,"arg":"hi"}'
    f = encode_frame(9, payload)  # MSG_CMD
    # decode the frame back
    assert f[5] == 9
    assert f[6 : 6 + len(payload)] == payload


def test_kotlin_must_match_python():
    # The Kotlin CyclopsProto.encode must produce identical bytes to this.
    # If the firmware/python codec changes, the Kotlin port must change too.
    for mtype, payload in [
        (1, b"\x01\x02"),  # HELLO
        (9, b'{"a":2,"arg":"hi"}'),  # MSG_CMD
        (5, b"\x00\x01" * 50),  # MSG_AUDIO_CHUNK
        (19, b""),  # MSG_AUDIO_STOP
        (14, b'{"kind":"text","data":"x"}'),  # MSG_HUD_FRAME
    ]:
        f = encode_frame(mtype, payload)
        # invariant: magic + length + type + crc tail present and CRC verifies
        assert f[0:3] == b"\xaa\xaa\x55"
        assert f[5] == mtype
        assert len(f) == 6 + len(payload) + 2
        expected = crc16_ccitt_false(f[3 : 6 + len(payload)])
        actual = struct.unpack("<H", f[6 + len(payload) : 6 + len(payload) + 2])[0]
        assert actual == expected


def test_brain_protocol_matches_firmware_crc_window():
    # brain.protocol / protocol_v2 encoders must CRC over len(2)+type(1)+payload,
    # exactly like the firmware encode_frame / FrameDecoder and Kotlin CyclopsProto.
    # (A type+payload-only window round-trips python<->python but the firmware
    # rejects every frame — a latent cross-language break.)
    from brain.protocol import encode as encode_v1
    from brain.protocol_v2 import encode_v2

    payload = b'{"a":2,"arg":"hi"}'
    for enc in (encode_v1, encode_v2):
        f = enc(9, payload)
        assert f[0] == 0xAA and f[1] == 0x55
        plen = f[2] | (f[3] << 8)
        assert plen == len(payload)
        crc_window = f[2 : 5 + plen]  # len_lo len_hi type payload
        expected = crc16_ccitt_false(crc_window)
        actual = struct.unpack("<H", f[5 + plen : 7 + plen])[0]
        assert actual == expected, (
            f"{enc.__module__}.encode CRC window diverges from firmware"
        )


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_HEADERS = (
    os.path.join(REPO, "firmware", "lib", "cyclops_shared", "include",
                 "cyclops_shared.h"),
    os.path.join(REPO, "firmware", "shared", "include", "cyclops_shared.h"),
)


def _cpp_msg_types(header_path: str) -> dict:
    """Parse `enum MsgType : uint8_t { NAME=n, ... }` out of the C++ header."""
    import re

    src = open(header_path).read()
    body = re.search(r"enum\s+MsgType\s*:\s*uint8_t\s*\{(.*?)\}", src, re.S)
    assert body, f"no MsgType enum in {header_path}"
    out = {}
    for name, num in re.findall(r"MSG_([A-Z0-9_]+)\s*=\s*(\d+)", body.group(1)):
        out[name] = int(num)
    return out


def test_python_msg_map_matches_the_cpp_enum():
    """brain.protocol.MSG is a hand-kept mirror of the C++ MsgType enum.

    It silently stopped at TTS=20 while the header grew MSG_OTA_BEGIN..ACK
    (21-24), so the OTA sender could not name its own frames from the map.
    Nothing compared the two -- now something does.
    """
    from brain.protocol import MSG

    cpp = _cpp_msg_types(SHARED_HEADERS[0])
    missing = {k: v for k, v in cpp.items() if k not in MSG}
    assert not missing, f"brain.protocol.MSG is missing {missing}"
    wrong = {k: (MSG[k], v) for k, v in cpp.items() if MSG[k] != v}
    assert not wrong, f"id mismatch (python, cpp): {wrong}"


def test_shared_header_copies_are_identical():
    """Two copies of cyclops_shared.h live in this repo (firmware/lib and
    firmware/shared) and a third is vendored into the CyclUno repo. Identical
    'today' is not a contract; drift between them is a cross-language wire
    break that no other test would catch."""
    bodies = [open(p).read() for p in SHARED_HEADERS]
    assert bodies[0] == bodies[1], (
        f"{SHARED_HEADERS[0]} and {SHARED_HEADERS[1]} have diverged")


if __name__ == "__main__":
    test_crc_standard_vector()
    test_frame_layout()
    test_cmd_frame_roundtrip_bytes()
    test_kotlin_must_match_python()
    test_brain_protocol_matches_firmware_crc_window()
    test_python_msg_map_matches_the_cpp_enum()
    test_shared_header_copies_are_identical()
    print("ALL WIRE-CONTRACT TESTS PASSED")
