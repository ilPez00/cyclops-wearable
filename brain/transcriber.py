"""Audio transcription backend — pluggable.

Default: local-first. If faster-whisper is installed it is used; otherwise a
deterministic stub returns canned transcripts so the full pipeline is testable
offline with no API keys. A cloud adapter can be added later (see APITranscriber).
"""
from __future__ import annotations

import os
import time


class Transcriber:
    name = "base"

    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        raise NotImplementedError

class StubTranscriber(Transcriber):
    name = "stub"
    # Deterministic canned conversation so tests are reproducible.
    SAMPLES = [
        "Remind me to send the invoice to Marco by friday",
        "We decided to ship the MVP next week",
        "Idea: add a vibration alert when a task is captured",
        "Call the dentist to book an appointment tomorrow",
        "Note: the battery lasts about six hours with the screen on",
    ]
    def __init__(self):
        self._i = 0
    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        # produce something even for empty input so the pipeline keeps moving
        text = self.SAMPLES[self._i % len(self.SAMPLES)]
        self._i += 1
        time.sleep(0.0)
        return text

class WhisperTranscriber(Transcriber):
    name = "whisper"
    def __init__(self, model_size: str = "base", language: str = "en"):
        self.language = language
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"faster-whisper unavailable: {e}")
    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        import io

        import numpy as np
        arr = np.frombuffer(pcm16, dtype="<i2").astype("float32") / 32768.0
        segs, _ = self.model.transcribe(arr, language=self.language)
        return " ".join(s.text for s in segs).strip()

class CloudTranscriber(Transcriber):
    """Real cloud transcription, wired to the local AI-stack key store.

    - audio  -> Deepgram (preffered) or an OpenAI-compatible STT endpoint
    - text   -> not applicable; use LLMExtractor for text understanding

    The HTTP layer is injectable (``session``) so it is unit-testable without
    network access. Default session is stdlib ``urllib.request`` (no deps).
    """
    name = "cloud"

    def __init__(self, keys=None, audio_provider: str = "deepgram",
                 session=None, language: str = "en"):
        from .aikeys import AiKeys
        self.keys = keys or AiKeys()
        self.audio_provider = audio_provider
        self.language = language
        self.session = session or _urllib_session()

    # -- public -------------------------------------------------------------
    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        if self.audio_provider == "deepgram" and self.keys.get_key("deepgram"):
            return self._transcribe_deepgram(pcm16, rate)
        # generic OpenAI-compatible transcription (e.g. whisper-style)
        return self._transcribe_openai(pcm16, rate)

    # -- providers ----------------------------------------------------------
    def _transcribe_deepgram(self, pcm16: bytes, rate: int) -> str:
        key = self.keys.get_key("deepgram")
        url = (self.keys.get_endpoint("deepgram")
               or "https://api.deepgram.com/v1")
        url = url.rstrip("/") + f"/listen?smart_format=true&punctuate=true&language={self.language}"
        headers = {"Authorization": f"Token {key}",
                   "Content-Type": "audio/raw",
                   "Accept": "application/json"}
        body = self._encode_wav_header(pcm16, rate) + pcm16
        resp = self.session.post(url, data=body, headers=headers, timeout=20)
        data = resp.json()
        try:
            return data["results"]["channels"][0]["alternatives"][0]["transcript"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"deepgram parse error: {e} ({data})")

    def _transcribe_openai(self, pcm16: bytes, rate: int) -> str:
        prov = self.keys.provider(self.audio_provider)
        if not prov["key"] and not prov["endpoint"]:
            raise RuntimeError(f"no key/endpoint for audio provider {self.audio_provider}")
        endpoint = prov["endpoint"] or "https://api.openai.com/v1"
        url = endpoint.rstrip("/") + "/audio/transcriptions"
        headers = {"Authorization": f"Bearer {prov['key']}"}
        files = {"file": ("audio.wav", self._encode_wav_header(pcm16, rate) + pcm16,
                          "audio/wav"), "model": (None, "whisper-1")}
        resp = self.session.post(url, files=files, headers=headers, timeout=30)
        data = resp.json()
        return data.get("text", "")

    @staticmethod
    def _encode_wav_header(pcm16: bytes, rate: int) -> bytes:
        import struct
        n = len(pcm16)
        return b"RIFF" + struct.pack("<I", 36 + n) + b"WAVE" + b"fmt " + \
            struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + \
            b"data" + struct.pack("<I", n)


def _urllib_session():
    from .http_session import stdlib_session
    return stdlib_session()


def from_aikeys(keys=None, audio_provider: str = "deepgram") -> CloudTranscriber:
    """Build a cloud transcriber backed by the local AI-stack key store."""
    return CloudTranscriber(keys=keys, audio_provider=audio_provider)


def get_transcriber(prefer: str = "auto", language: str = "en", keys=None) -> Transcriber:
    if prefer == "stub":
        return StubTranscriber()
    if prefer == "whisper":
        return WhisperTranscriber(language=language)
    if prefer == "cloud":
        return CloudTranscriber(keys=keys, language=language)
    # auto: edge whisper if present -> cloud if keys -> stub
    try:
        return WhisperTranscriber(language=language)
    except Exception:
        pass
    try:
        from .aikeys import AiKeys
        k = keys or AiKeys()
        if k.has("deepgram") or k.has("groq"):
            return CloudTranscriber(keys=k, language=language)
    except Exception:
        pass
    return StubTranscriber()
