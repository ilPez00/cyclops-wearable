"""Offline: HudBridge.handle_audio decodes ADPCM per the META codec byte.

The firmware announces the codec in MSG_AUDIO_META byte[5] (0=PCM16 raw,
1=IMA ADPCM). ADPCM chunks must be decoded to PCM16 before accumulation so
the transcriber always receives raw PCM. No network/keys/device involved.
"""

import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.adpcm import AdpcmEncoder, decode_chunk, encode_chunk
from brain.hud_bridge import MSG_AUDIO_CHUNK, MSG_AUDIO_META, MSG_AUDIO_STOP, HudBridge


class PcmCapTranscriber:
    """Captures the PCM handed to transcribe(); returns a fixed phrase."""

    def __init__(self):
        self.pcm = None
        self.rate = None

    def transcribe(self, pcm, rate=16000):
        self.pcm = bytes(pcm)
        self.rate = rate
        return "captured"


class NullSink:
    def render_text(self, t):
        pass

    def write(self, b):
        pass


def _meta(codec, rate=16000, bits=16):
    return bytes([bits & 0xFF, bits >> 8, rate & 0xFF, rate >> 8, 1, codec, 0, 0])


def _sine(n, amp=2000):
    return [int(amp * math.sin(2 * math.pi * i / 64)) for i in range(n)]


def test_adpcm_chunks_are_decoded_before_transcription():
    tr = PcmCapTranscriber()
    br = HudBridge(NullSink(), transcriber=tr)
    br.handle_audio(MSG_AUDIO_META, _meta(codec=1))
    enc = AdpcmEncoder()
    pcm = _sine(1024)
    for off in range(0, len(pcm), 256):
        br.handle_audio(MSG_AUDIO_CHUNK, enc.encode(pcm[off : off + 256]))
    kind, txt = br.handle_audio(MSG_AUDIO_STOP, b"")
    assert kind == "transcribed" and txt == "captured"
    assert tr.rate == 16000
    got = struct.unpack(f"<{len(tr.pcm) // 2}h", tr.pcm)
    assert len(got) == len(pcm), "decoded sample count must match the capture"
    # lossy codec: warm-stream reconstruction must track the signal closely
    tail_err = max(abs(a - b) for a, b in zip(pcm[256:], got[256:]))
    assert tail_err < 300, f"tail maxerr {tail_err}"
    print("OK ADPCM chunks decoded to PCM before the transcriber")


def test_pcm16_codec_passes_through_unchanged():
    tr = PcmCapTranscriber()
    br = HudBridge(NullSink(), transcriber=tr)
    br.handle_audio(MSG_AUDIO_META, _meta(codec=0))
    raw = struct.pack("<8h", *range(8))
    br.handle_audio(MSG_AUDIO_CHUNK, raw)
    br.handle_audio(MSG_AUDIO_STOP, b"")
    assert tr.pcm == raw
    print("OK codec=0 accumulates raw bytes untouched")


def test_legacy_short_meta_defaults_to_raw_pcm():
    tr = PcmCapTranscriber()
    br = HudBridge(NullSink(), transcriber=tr)
    # pre-codec firmware: 5-byte META (bits, rate, channels) — no codec byte
    br.handle_audio(MSG_AUDIO_META, bytes([16, 0, 0x80, 0x3E, 1]))
    raw = struct.pack("<4h", 1, -1, 2, -2)
    br.handle_audio(MSG_AUDIO_CHUNK, raw)
    br.handle_audio(MSG_AUDIO_STOP, b"")
    assert tr.pcm == raw, "old firmware must keep the raw-PCM path"
    print("OK legacy 5-byte META keeps raw-PCM default")


def test_codec_resets_per_meta():
    tr = PcmCapTranscriber()
    br = HudBridge(NullSink(), transcriber=tr)
    br.handle_audio(MSG_AUDIO_META, _meta(codec=1))
    br.handle_audio(MSG_AUDIO_STOP, b"")  # flush adpcm session
    # next session announces raw again — decoder must not stick on ADPCM
    br.handle_audio(MSG_AUDIO_META, _meta(codec=0))
    raw = struct.pack("<4h", 7, -7, 9, -9)
    br.handle_audio(MSG_AUDIO_CHUNK, raw)
    br.handle_audio(MSG_AUDIO_STOP, b"")
    assert tr.pcm == raw
    print("OK codec follows each META (no sticky state)")



# --- multi-chunk sequence contract ---------------------------------------------
# Per-chunk coverage already exists above; what was missing is the *sequence*:
# the step index must carry across chunk boundaries (warm adaption), each chunk
# must still decode standalone, and the firmware/host pair must agree on the
# codec byte. Chunk header is [0..1] int16 LE predictor, [2] step index,
# [3] pad flag -- firmware/shared/include/adpcm.h.

def _mean_abs_err(chunks, pcm):
    # decode_chunk handles exactly one self-contained chunk, so decode per
    # chunk and concatenate -- decoding the joined buffer would silently yield
    # only the first chunk.
    raw = b"".join(decode_chunk(c) for c in chunks)
    got = struct.unpack(f"<{len(raw) // 2}h", raw)
    assert len(got) == len(pcm), f"decoded {len(got)} samples, expected {len(pcm)}"
    return sum(abs(a - b) for a, b in zip(got, pcm)) // len(pcm)


def test_step_index_continues_across_chunk_boundaries():
    # Chunks stay self-contained (a lost notify costs one window) but the step
    # index must be fed forward, or every chunk restarts cold. Measured here on
    # a quiet->loud onset over 2048 samples: mean abs error 34 warm vs 65 cold,
    # because a cold encoder overestimates the step size until it adapts. The
    # 0.7x bound sits under the measured 0.52x with margin.
    pcm = [
        int((400 if i < 1024 else 9000) * math.sin(2 * math.pi * i / 48))
        for i in range(2048)
    ]
    seed, warm, cold = 0, [], []
    for off in range(0, len(pcm), 256):
        chunk, seed = encode_chunk(pcm[off : off + 256], seed)
        warm.append(chunk)
        cold.append(encode_chunk(pcm[off : off + 256], 0)[0])

    assert warm != cold, "feeding the step index forward changed nothing"
    warm_err, cold_err = _mean_abs_err(warm, pcm), _mean_abs_err(cold, pcm)
    assert warm_err * 10 < cold_err * 7, (
        f"continuity not effective: warm={warm_err} cold={cold_err}"
    )
    for off in range(0, len(pcm), 256):
        standalone, _ = encode_chunk(pcm[off : off + 256], 0)
        assert len(decode_chunk(standalone)) == 256 * 2, "chunk must decode alone"


def test_full_sequence_roundtrips_through_the_bridge():
    tr = PcmCapTranscriber()
    br = HudBridge(NullSink(), transcriber=tr)
    br.handle_audio(MSG_AUDIO_META, _meta(codec=1))
    pcm = _sine(2048, amp=2500)
    for off in range(0, len(pcm), 256):
        br.handle_audio(MSG_AUDIO_CHUNK, encode_chunk(pcm[off : off + 256])[0])
    kind, txt = br.handle_audio(MSG_AUDIO_STOP, b"")
    assert kind == "transcribed" and txt == "captured"
    got = struct.unpack(f"<{len(tr.pcm) // 2}h", tr.pcm)
    assert len(got) == len(pcm), "8-chunk sequence must yield every sample"


def test_sequence_survives_a_dropped_chunk():
    # A lost BLE notify costs only its own window: the next chunk is still
    # self-contained and the stream continues.
    tr = PcmCapTranscriber()
    br = HudBridge(NullSink(), transcriber=tr)
    br.handle_audio(MSG_AUDIO_META, _meta(codec=1))
    pcm = _sine(2048, amp=2500)
    enc = AdpcmEncoder()
    chunks = [enc.encode(pcm[o : o + 256]) for o in range(0, len(pcm), 256)]
    for i, c in enumerate(chunks):
        if i == 3:
            continue# notify lost
        br.handle_audio(MSG_AUDIO_CHUNK, c)
    kind, _ = br.handle_audio(MSG_AUDIO_STOP, b"")
    assert kind == "transcribed"
    got = struct.unpack(f"<{len(tr.pcm) // 2}h", tr.pcm)
    assert len(got) == len(pcm) - 256, "only the dropped chunk's samples are lost"
