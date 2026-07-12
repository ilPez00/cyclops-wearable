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

from brain.adpcm import AdpcmEncoder
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
