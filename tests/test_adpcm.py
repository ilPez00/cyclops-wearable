"""ADPCM wire contract: brain/adpcm.py must be byte-identical to the C++
encoder in firmware/shared/include/adpcm.h (vectors pinned in both suites,
same style as the CRC/framing contract tests)."""

import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.adpcm import AdpcmEncoder, decode_chunk, encode_chunk

VECTORS = {
    # name: (pcm, expected_hex, expected_end_index)
    "silence16": ([0] * 16, "000000000000000000000000", 0),
    "ramp16": (list(range(-8000, 8000, 1000)), "c0e000007077777747100121", 60),
    "odd7": ([100, -200, 300, -400, 500, -600, 700], "64000001f0f7f707", 48),
    "extremes8": (
        [32767, -32768, 32767, -32768, 0, 0, 32767, -32768],
        "ff7f0000f0f2fff5",
        43,
    ),
}


def test_encoder_matches_cpp_vectors():
    for name, (pcm, want_hex, want_end) in VECTORS.items():
        enc, end = encode_chunk(pcm)
        assert enc.hex() == want_hex, f"{name}: {enc.hex()} != {want_hex}"
        assert end == want_end, f"{name}: end_index {end} != {want_end}"
    print("OK encoder byte-identical to C++ on all pinned vectors")


def test_decode_roundtrip_sample_counts():
    for name, (pcm, _, _) in VECTORS.items():
        enc, _ = encode_chunk(pcm)
        dec = decode_chunk(enc)
        assert len(dec) == 2 * len(pcm), f"{name}: pad flag broken"
    print("OK decode returns exactly the encoded sample count (odd incl.)")


def test_decode_pinned_reconstruction():
    enc, _ = encode_chunk(VECTORS["odd7"][0])
    dec = struct.unpack("<7h", decode_chunk(enc))
    assert list(dec) == [100, 89, 119, 56, 192, -101, 530]
    print("OK decoded samples match the C++ reconstruction")


def test_stream_quality_speech_grade():
    enc = AdpcmEncoder()
    sig = [int(8000 * math.sin(2 * math.pi * 440 * i / 16000)) for i in range(16000)]
    rec = []
    for off in range(0, len(sig), 472):
        chunk = enc.encode(sig[off : off + 472])
        pcm = decode_chunk(chunk)
        rec += struct.unpack(f"<{len(pcm) // 2}h", pcm)
    assert len(rec) == len(sig)
    tail_err = max(abs(a - b) for a, b in zip(sig[8000:], rec[8000:]))
    assert tail_err < 400, f"tail maxerr {tail_err} — adaption not warm?"
    print(f"OK warm-stream tail maxerr={tail_err} (speech-grade)")


def test_compression_ratio():
    pcm = [0] * 472  # 944 raw bytes
    chunk, _ = encode_chunk(pcm)
    assert len(chunk) == 4 + 236  # 4:1 minus the 4-byte header
    print("OK 4:1 compression (472 samples -> 240 bytes incl. header)")


def test_guards():
    assert encode_chunk([])[0] == b""
    assert decode_chunk(b"") == b""
    assert decode_chunk(b"\x00\x00\x00") == b""  # short header
    assert decode_chunk(b"\x00\x00\x00\x07\x11\x22") == b""  # bad pad byte
    print("OK guards (empty, short, malformed pad)")


def test_bytes_input_accepted():
    raw = struct.pack("<4h", 10, -10, 20, -20)
    enc_from_bytes, _ = encode_chunk(raw)
    enc_from_list, _ = encode_chunk([10, -10, 20, -20])
    assert enc_from_bytes == enc_from_list
    print("OK LE int16 bytes and int lists encode identically")
