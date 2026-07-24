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


class _FakeOAuthStore:
    """Minimal double matching brain.oauth_store.OAuthStore's public shape,
    for testing AiKeys' fallback to OAuth tokens without touching disk."""

    def __init__(self, tokens=None):
        self._tokens = tokens or {}

    def get_valid_key(self, provider, provider_cfg=None):
        return self._tokens.get(provider)

    def available_providers(self):
        return sorted(self._tokens)


def test_get_key_falls_back_to_oauth_when_no_static_key():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)  # has gemini/groq, nothing for "kimi"
        oauth = _FakeOAuthStore({"kimi": "oauth-tok-123"})
        k = AiKeys(ai_api_txt=p, env_paths=[], oauth_store=oauth)
        assert k.get_key("kimi") == "oauth-tok-123"


def test_get_key_prefers_static_over_oauth():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)  # groq:gsk_test
        oauth = _FakeOAuthStore({"groq": "should-not-be-used"})
        k = AiKeys(ai_api_txt=p, env_paths=[], oauth_store=oauth)
        assert k.get_key("groq") == "gsk_test"


def test_available_includes_oauth_only_providers():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)
        oauth = _FakeOAuthStore({"kimi": "tok"})
        k = AiKeys(ai_api_txt=p, env_paths=[], oauth_store=oauth)
        assert "kimi" in k.available()
        assert "gemini" in k.available()  # static providers still present too


def test_get_key_no_static_no_oauth_is_none():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d)
        k = AiKeys(ai_api_txt=p, env_paths=[], oauth_store=_FakeOAuthStore())
        assert k.get_key("nonexistent_provider") is None


def test_get_endpoint_falls_back_to_oauth_provider_api_base_url():
    import json

    with tempfile.TemporaryDirectory() as d:
        p = _make(d)
        providers_path = os.path.join(d, "oauth_providers.json")
        with open(providers_path, "w") as f:
            json.dump(
                {
                    "kimi": {
                        "device_auth_url": "https://a/d",
                        "token_url": "https://a/t",
                        "client_id": "c",
                        "api_base_url": "https://api.moonshot.ai/v1",
                    }
                },
                f,
            )
        old = os.environ.get("CYCLOPS_OAUTH_PROVIDERS")
        os.environ["CYCLOPS_OAUTH_PROVIDERS"] = providers_path
        try:
            k = AiKeys(ai_api_txt=p, env_paths=[], oauth_store=_FakeOAuthStore({"kimi": "tok"}))
            assert k.get_endpoint("kimi") == "https://api.moonshot.ai/v1"
            # a provider with no matching oauth config and no static endpoint is still None
            assert k.get_endpoint("nonexistent_provider") is None
        finally:
            if old is None:
                os.environ.pop("CYCLOPS_OAUTH_PROVIDERS", None)
            else:
                os.environ["CYCLOPS_OAUTH_PROVIDERS"] = old
