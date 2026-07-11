"""Tests for brain.aikeys — fully offline (no real secrets, no network)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo root

from brain.aikeys import AiKeys

SAMPLE = """
# comment line
gemini:KEY_G1,KEY_G2
groq:gsk_test
groq_endpoint:https://api.groq.com/openai/v1
deepgram_endpoint:https://api.deepgram.com/v1
"""


def _make(tmp, body=SAMPLE):
    p = os.path.join(tmp, "ai_api.txt")
    with open(p, "w") as f:
        f.write(body)
    return p


def test_parses_keys_and_endpoints():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)
        k = AiKeys(ai_api_txt=p, env_paths=[])
        assert k.get_key("gemini") == "KEY_G1"
        assert k.get_keys("gemini") == ["KEY_G1", "KEY_G2"]
        assert k.get_endpoint("groq") == "https://api.groq.com/openai/v1"
        assert k.get_endpoint("deepgram") == "https://api.deepgram.com/v1"


def test_missing_file_is_empty():
    k = AiKeys(ai_api_txt="/nonexistent/path/ai_api.txt", env_paths=[])
    assert k.get_key("gemini") is None
    assert k.available() == []


def test_provider_descriptor():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)
        k = AiKeys(ai_api_txt=p, env_paths=[])
        prov = k.provider("groq")
        assert prov["name"] == "groq"
        assert prov["endpoint"] == "https://api.groq.com/openai/v1"
        assert prov["key"] == "gsk_test"  # groq key present in sample
        # a name with only an endpoint (no key) still yields a descriptor
        dd = k.provider("deepgram")
        assert dd["endpoint"] == "https://api.deepgram.com/v1"
        assert dd["key"] is None


def test_env_key_loading():
    with tempfile.TemporaryDirectory() as d:
        ep = os.path.join(d, ".env")
        with open(ep, "w") as f:
            f.write('GROQ_API_KEY="gsk_test123"\n')
        k = AiKeys(ai_api_txt="/nope/ai_api.txt", env_paths=[ep])
        assert k.get_key("groq_api_key") == "gsk_test123"


def test_has_and_available():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)
        k = AiKeys(ai_api_txt=p, env_paths=[])
        assert k.has("gemini")
        assert k.has("groq")
        assert "gemini" in k.available() and "groq" in k.available()
