"""Omi audio ingestion (P1-A) — companion reads Omi BLE audio -> brain STT.

The Omi pendant streams 16 kHz audio (Opus over BLE). This module owns the
*source* abstraction + the *ingest* loop that feeds the brain Transcriber, so
Cyclops works with the $29 Omi instead of (or alongside) the XIAO mic.

Offline-safe by design:
  * OmiAudioSource is injectable. FakeOmiSource emits PCM16 chunks for tests,
    no Bluetooth / Opus decoder required.
  * BleOmiSource is import-safe: it only imports `bleak`/`opuslib` when used,
    and raises a clear error if they are missing.
  * Omi GATT UUIDs are configurable via env (CYCLOPS_OMI_SRVC / CYCLOPS_OMI_AUDIO)
    because the exact audio characteristic depends on the Omi firmware build;
    the defaults are placeholders to be verified against your device.

Audio capture is privacy-sensitive: callers MUST gate start() on Consent Mode
(see agent/tools/consent.py).
"""

from __future__ import annotations

import base64
import os

# --- Omi BLE (verify against your Omi firmware; override via env) ----------
OMI_SERVICE_UUID = os.environ.get(
    "CYCLOPS_OMI_SRVC", "19B10000-E8F2-537E-4F6C-D104768A1214"
)
OMI_AUDIO_UUID = os.environ.get(
    "CYCLOPS_OMI_AUDIO", "19B10001-E8F2-537E-4F6C-D104768A1214"
)
OMI_RATE = 16000


def decode_opus(opus_bytes: bytes, rate: int = OMI_RATE) -> bytes:
    """Decode one Opus frame to PCM16. Requires `opuslib` (optional dep)."""
    try:
        import opuslib
    except Exception as e:
        raise RuntimeError(
            "opuslib not installed; install it or feed PCM16 "
            "directly to the ingest loop"
        ) from e
    dec = opuslib.Decoder(rate, 1)
    return dec.decode(opus_bytes, OMI_RATE // 50)  # 20 ms frame


class OmiAudioSource:
    """Yields raw PCM16 chunks (16 kHz, mono, little-endian) via callback."""

    def __init__(self, rate: int = OMI_RATE):
        self.rate = rate
        self._cb = None
        self.running = False

    def start(self, on_chunk) -> None:
        self._cb = on_chunk
        self.running = True
        self._run()

    def _run(self):
        raise NotImplementedError

    def stop(self):
        self.running = False


class FakeOmiSource(OmiAudioSource):
    """Test source: emits N synthetic PCM16 chunks then stops."""

    def __init__(
        self, chunks: int = 3, samples_per_chunk: int = 160, rate: int = OMI_RATE
    ):
        super().__init__(rate)
        self.chunks = chunks
        self.samples_per_chunk = samples_per_chunk

    def _run(self):
        import struct

        for _ in range(self.chunks):
            if not self.running:
                break
            pcm = b"".join(struct.pack("<h", 0) for _ in range(self.samples_per_chunk))
            if self._cb:
                self._cb(pcm)


class BleOmiSource(OmiAudioSource):
    """Real Omi over BLE (import-safe). Subscribes to the audio characteristic,
    decodes Opus -> PCM16, and forwards chunks. Needs `bleak` + `opuslib`."""

    def __init__(
        self,
        address: str | None = None,
        rate: int = OMI_RATE,
        srvc: str = OMI_SERVICE_UUID,
        audio: str = OMI_AUDIO_UUID,
    ):
        super().__init__(rate)
        self.address = address
        self.srvc = srvc
        self.audio = audio

    def _run(self):
        try:
            import asyncio

            from bleak import BleakClient
        except Exception as e:
            raise RuntimeError("bleak not installed: `pip install bleak`") from e

        async def _loop():
            client = BleakClient(self.address)
            await client.connect()

            def _handle(_, data: bytearray):
                if not self.running:
                    return
                pcm = decode_opus(bytes(data), self.rate)
                if self._cb:
                    self._cb(pcm)

            await client.start_notify(self.audio, _handle)
            while self.running:
                await asyncio.sleep(0.05)
            await client.stop_notify(self.audio)

        asyncio.run(_loop())


class OmiIngest:
    """Drive an OmiAudioSource into a Transcriber, emitting phrases.

    The brain Transcriber already consumes PCM16 at 16 kHz, so this is a thin
    loop: collect chunks, transcribe when enough audio has accumulated, and
    call `on_phrase(text)` for each recognized utterance. Consent is the
    caller's responsibility (the tool gates it).
    """

    def __init__(
        self,
        source: OmiAudioSource,
        transcriber,
        on_phrase=lambda t: None,
        max_chunks: int = 30,
    ):
        self.source = source
        self.transcriber = transcriber
        self.on_phrase = on_phrase
        self.max_chunks = max_chunks
        self._buf = bytearray()
        self._count = 0
        self.last_phrase = ""

    def _feed(self, pcm16: bytes):
        self._buf += pcm16
        self._count += 1
        if self._count >= self.max_chunks:
            text = self.transcriber.transcribe(bytes(self._buf), self.source.rate)
            if text:
                self.last_phrase = text
                self.on_phrase(text)
            self._buf = bytearray()
            self._count = 0

    def run(self):
        self.source.start(self._feed)

    def stop(self):
        self.source.stop()
