"""Tests for the cloud transcriber (F2) — offline via an injected fake session."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.aikeys import AiKeys
from brain.transcriber import CloudTranscriber


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakeSession:
    """Records the last request and returns a scripted response."""

    def __init__(self, response):
        # accept either a dict (auto-wrapped) or a FakeResp
        self.response = (
            response if isinstance(response, FakeResp) else FakeResp(response)
        )
        self.last = None

    def post(self, url, data=None, headers=None, timeout=30, files=None):
        self.last = {"url": url, "headers": headers, "files": files, "data": data}
        return self.response


def _keys(tmp_dir):
    p = os.path.join(tmp_dir, "ai_api.txt")
    with open(p, "w") as f:
        f.write(
            "deepgram:dummy_dg_key\ndeepgram_endpoint:https://api.deepgram.com/v1\n"
        )
    return AiKeys(ai_api_txt=p, env_paths=[])


def test_deepgram_path_builds_wav_and_parses():
    with tempfile.TemporaryDirectory() as d:
        sess = FakeSession(
            {
                "results": {
                    "channels": [{"alternatives": [{"transcript": "hello world"}]}]
                }
            }
        )
        t = CloudTranscriber(keys=_keys(d), audio_provider="deepgram", session=sess)
        out = t.transcribe(b"\x00\x00" * 100, rate=16000)
        assert out == "hello world"
        # wav header prefix present on body? (data path, deepgram uses raw+header appended)
        assert sess.last["url"].startswith("https://api.deepgram.com/v1/listen")
        assert "Authorization" in sess.last["headers"]
        assert sess.last["headers"]["Authorization"].endswith("dummy_dg_key")


def test_openai_fallback_parses_text():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "ai_api.txt")
        with open(p, "w") as f:
            f.write("groq:gsk_x\ngroq_endpoint:https://api.groq.com/openai/v1\n")
        keys = AiKeys(ai_api_txt=p, env_paths=[])
        sess = FakeSession({"text": "transcribed via groq"})
        # force non-deepgram provider
        t = CloudTranscriber(keys=keys, audio_provider="groq", session=sess)
        out = t.transcribe(b"\x01\x02" * 50)
        assert out == "transcribed via groq"
        assert "audio/transcriptions" in sess.last["url"]
        assert sess.last["files"] is not None  # multipart form sent


def test_no_key_raises():
    with tempfile.TemporaryDirectory():
        keys = AiKeys(ai_api_txt="/nope/ai_api.txt", env_paths=[])
        sess = FakeSession({})
        t = CloudTranscriber(keys=keys, audio_provider="groq", session=sess)
        try:
            t.transcribe(b"x")
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass
