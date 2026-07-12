"""IMA ADPCM (DVI4) mono codec — Python mirror of firmware/shared/include/adpcm.h.

Same wire format, same integer math, byte-identical output on the same input
(asserted by tests/test_adpcm.py, mirroring the CRC/framing contract tests):

    [0..1] int16 LE  predictor seed (first sample)
    [2]    uint8     step index seed
    [3]    uint8     pad flag: 1 = odd sample count (last high nibble unused)
    [4..]  packed 4-bit codes, low nibble first

Each chunk is self-contained, so a lost BLE notify costs only its own ~30 ms
window. 4 bits/sample = 4:1 vs PCM16 (32 KB/s -> 8 KB/s at 16 kHz).
"""

from __future__ import annotations

import struct

INDEX_TABLE = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8]

STEP_TABLE = [
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    16,
    17,
    19,
    21,
    23,
    25,
    28,
    31,
    34,
    37,
    41,
    45,
    50,
    55,
    60,
    66,
    73,
    80,
    88,
    97,
    107,
    118,
    130,
    143,
    157,
    173,
    190,
    209,
    230,
    253,
    279,
    307,
    337,
    371,
    408,
    449,
    494,
    544,
    598,
    658,
    724,
    796,
    876,
    963,
    1060,
    1166,
    1282,
    1411,
    1552,
    1707,
    1878,
    2066,
    2272,
    2499,
    2749,
    3024,
    3327,
    3660,
    4026,
    4428,
    4871,
    5358,
    5894,
    6484,
    7132,
    7845,
    8630,
    9493,
    10442,
    11487,
    12635,
    13899,
    15289,
    16818,
    18500,
    20350,
    22385,
    24623,
    27086,
    29794,
    32767,
]

AUDIO_CODEC_PCM16 = 0
AUDIO_CODEC_ADPCM = 1


def _clamp_index(i: int) -> int:
    return 0 if i < 0 else (88 if i > 88 else i)


def _encode_sample(sample: int, predictor: int, index: int) -> tuple[int, int, int]:
    step = STEP_TABLE[index]
    diff = sample - predictor
    code = 0
    if diff < 0:
        code = 8
        diff = -diff
    if diff >= step:
        code |= 4
        diff -= step
    if diff >= step >> 1:
        code |= 2
        diff -= step >> 1
    if diff >= step >> 2:
        code |= 1
    delta = step >> 3
    if code & 4:
        delta += step
    if code & 2:
        delta += step >> 1
    if code & 1:
        delta += step >> 2
    predictor = predictor - delta if code & 8 else predictor + delta
    predictor = max(-32768, min(32767, predictor))
    return code, predictor, _clamp_index(index + INDEX_TABLE[code])


def _decode_sample(code: int, predictor: int, index: int) -> tuple[int, int, int]:
    step = STEP_TABLE[index]
    delta = step >> 3
    if code & 4:
        delta += step
    if code & 2:
        delta += step >> 1
    if code & 1:
        delta += step >> 2
    predictor = predictor - delta if code & 8 else predictor + delta
    predictor = max(-32768, min(32767, predictor))
    return predictor, predictor, _clamp_index(index + INDEX_TABLE[code])


def encode_chunk(pcm: list[int] | bytes, seed_index: int = 0) -> tuple[bytes, int]:
    """Encode PCM16 samples (ints, or LE int16 bytes) to one chunk.

    Returns (chunk_bytes, end_index). Feed end_index back as seed_index for
    the next chunk to keep the adaption warm across a stream.
    """
    if isinstance(pcm, (bytes, bytearray)):
        pcm = list(struct.unpack(f"<{len(pcm) // 2}h", bytes(pcm[: len(pcm) // 2 * 2])))
    index = _clamp_index(seed_index)
    if not pcm:
        return b"", index
    predictor = pcm[0]
    out = bytearray(struct.pack("<hBB", predictor, index, len(pcm) & 1))
    nibbles = 0
    for i, s in enumerate(pcm):
        code, predictor, index = _encode_sample(s, predictor, index)
        if i % 2 == 0:
            nibbles = code  # low nibble first
        else:
            nibbles |= code << 4
            out.append(nibbles)
    if len(pcm) % 2:
        out.append(nibbles)
    return bytes(out), index


def decode_chunk(data: bytes) -> bytes:
    """Decode one self-contained chunk back to LE PCM16 bytes."""
    if len(data) < 4 or data[3] > 1:
        return b""
    predictor = struct.unpack_from("<h", data, 0)[0]
    index = _clamp_index(data[2])
    out = bytearray()
    nib = (len(data) - 4) * 2 - data[3]  # pad flag drops the last nibble
    for i in range(nib):
        byte = data[4 + (i >> 1)]
        code = (byte >> 4) if i & 1 else (byte & 0x0F)
        sample, predictor, index = _decode_sample(code, predictor, index)
        out += struct.pack("<h", sample)
    return bytes(out)


class AdpcmEncoder:
    """Stateful stream encoder: carries the step index across chunks."""

    def __init__(self):
        self.index = 0

    def encode(self, pcm: list[int] | bytes) -> bytes:
        chunk, self.index = encode_chunk(pcm, seed_index=self.index)
        return chunk


__all__ = [
    "encode_chunk",
    "decode_chunk",
    "AdpcmEncoder",
    "AUDIO_CODEC_PCM16",
    "AUDIO_CODEC_ADPCM",
]
