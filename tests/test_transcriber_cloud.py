"""Offline tests for the real cloud transcriber (Deepgram + OpenAI) via fake session."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.transcriber import CloudTranscriber, StubTranscriber, get_transcriber


class FakeKeys:
    """Minimal key store so CloudTranscriber runs without the real /home/gio/.env."""
    def __init__(self, prov, key, endpoint=None):
        self._prov = prov; self._key = key; self._ep = endpoint
    def get_key(self, p): return self._key if p == self._prov else None
    def get_endpoint(self, p): return self._ep if p == self._prov else None
    def has(self, p): return p == self._prov
    def provider(self, p):
        return {"key": self._key, "endpoint": self._ep} if p == self._prov else {"key": None, "endpoint": None}


class Resp:
    def __init__(self, d): self._d = d
    def json(self): return self._d


class Session:
    def __init__(self, expect_url_substr, payload):
        self.expect = expect_url_substr; self.payload = payload; self.calls = []
    def post(self, url, data=None, headers=None, timeout=30, files=None):
        self.calls.append(url)
        assert self.expect in url, f"unexpected url {url}"
        return Resp(self.payload)


def test_cloud_deepgram():
    keys = FakeKeys("deepgram", "tok", "https://api.deepgram.com/v1")
    sess = Session("deepgram.com", {
        "results": {"channels": [{"alternatives": [{"transcript": "hello from deepgram"}]}]}
    })
    t = CloudTranscriber(keys=keys, audio_provider="deepgram", session=sess, language="it")
    out = t.transcribe(b"\x00\x00" * 100, rate=16000)
    assert out == "hello from deepgram"
    assert "language=it" in sess.calls[0]


def test_cloud_openai():
    # no deepgram key -> falls to OpenAI-compatible provider
    keys = FakeKeys("groq", "sk", "https://api.groq.com/openai/v1")
    sess = Session("audio/transcriptions", {"text": "ciao da groq"})
    t = CloudTranscriber(keys=keys, audio_provider="groq", session=sess)
    out = t.transcribe(b"\x00\x00" * 100)
    assert out == "ciao da groq"


def test_stub_deterministic():
    s = StubTranscriber()
    a = s.transcribe(b"")
    assert a and a in StubTranscriber.SAMPLES  # canned line from the sample set


def test_get_transcriber_stub():
    assert isinstance(get_transcriber("stub"), StubTranscriber)


def test_get_transcriber_cloud_with_keys():
    keys = FakeKeys("deepgram", "tok")
    t = get_transcriber("cloud", keys=keys)
    assert isinstance(t, CloudTranscriber)
