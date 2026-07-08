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
    def __init__(self, model_size: str = "base"):
        try:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
        except Exception as e:  # pragma: no cover
            raise RuntimeError(f"faster-whisper unavailable: {e}")
    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        import numpy as np, io
        arr = np.frombuffer(pcm16, dtype="<i2").astype("float32") / 32768.0
        segs, _ = self.model.transcribe(arr, language="en")
        return " ".join(s.text for s in segs).strip()

class APITranscriber(Transcriber):
    """Cloud fallback (OpenAI/Deepgram/DeepSeek). Add key via /home/gio/.env."""
    name = "api"
    def __init__(self, provider: str = "openai", api_key: str | None = None):
        self.provider = provider
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("no API key for cloud transcriber")
    def transcribe(self, pcm16: bytes, rate: int = 16000) -> str:
        # placeholder: wire real HTTP call here
        raise NotImplementedError("cloud adapter not wired yet")


class CloudTranscriber(Transcriber):
    """Real cloud transcription, wired to the local AI-stack key store.

    - audio  -> Deepgram (preffered) or an OpenAI-compatible STT endpoint
    - text   -> not applicable; use LLMExtractor for text understanding

    The HTTP layer is injectable (``session``) so it is unit-testable without
    network access. Default session is stdlib ``urllib.request`` (no deps).
    """
    name = "cloud"

    def __init__(self, keys=None, audio_provider: str = "deepgram",
                 session=None):
        from .aikeys import AiKeys
        self.keys = keys or AiKeys()
        self.audio_provider = audio_provider
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
        url = url.rstrip("/") + "/listen?smart_format=true&punctuate=true&language=en"
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
    """Minimal requests-like wrapper over stdlib urllib (no third-party dep)."""
    import json as _json
    import urllib.request as _req
    import urllib.error as _err

    class _Resp:
        def __init__(self, status, body):
            self.status = status
            self._body = body
        def json(self):
            return _json.loads(self._body)

    class _Session:
        def post(self, url, data=None, headers=None, timeout=30, files=None):
            if files is not None:
                # multipart/form-data encoding
                boundary = "----cyclopsboundary"
                parts = []
                for k, v in files.items():
                    if isinstance(v, tuple):
                        fname, fdata, ctype = v
                        parts.append(f"--{boundary}\r\n".encode()
                                     + f'Content-Disposition: form-data; name="{k}"; filename="{fname}"\r\n'.encode()
                                     + f"Content-Type: {ctype}\r\n\r\n".encode()
                                     + fdata + b"\r\n")
                    else:
                        parts.append(f"--{boundary}\r\n".encode()
                                     + f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
                                     + v.encode() + b"\r\n")
                body = b"".join(parts) + f"--{boundary}--\r\n".encode()
                h = dict(headers or {})
                h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
                req = _req.Request(url, data=body, headers=h, method="POST")
            else:
                req = _req.Request(url, data=data, headers=headers or {}, method="POST")
            try:
                with _req.urlopen(req, timeout=timeout) as r:
                    return _Resp(r.status, r.read().decode("utf-8", "ignore"))
            except _err.HTTPError as e:
                return _Resp(e.code, e.read().decode("utf-8", "ignore"))
    return _Session()


def from_aikeys(keys=None, audio_provider: str = "deepgram") -> CloudTranscriber:
    """Build a cloud transcriber backed by the local AI-stack key store."""
    return CloudTranscriber(keys=keys, audio_provider=audio_provider)


def get_transcriber(prefer: str = "auto") -> Transcriber:
    if prefer == "stub":
        return StubTranscriber()
    if prefer == "whisper":
        return WhisperTranscriber()
    if prefer == "api":
        return APITranscriber()
    if prefer == "cloud":
        return CloudTranscriber()
    # auto: whisper if present, else cloud if keys available, else stub
    try:
        return WhisperTranscriber()
    except Exception:
        pass
    try:
        from .aikeys import AiKeys
        if AiKeys().has("deepgram") or AiKeys().has("groq"):
            return CloudTranscriber()
    except Exception:
        pass
    return StubTranscriber()
