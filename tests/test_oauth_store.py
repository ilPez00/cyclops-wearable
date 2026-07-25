"""OAuth token persistence + lazy refresh — fully offline."""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.oauth_device import ProviderConfig
from brain.oauth_store import OAuthStore, load_provider_configs, save_provider_config


def _tmp_store():
    d = tempfile.mkdtemp()
    return OAuthStore(path=os.path.join(d, "oauth_tokens.json"))


def test_save_writes_owner_only_permissions():
    # Tokens (especially refresh_token) are longer-lived, broader-scoped
    # credentials than a static API key -- must not inherit the umask default
    # (typically 0644, group/world-readable).
    import stat

    s = _tmp_store()
    s.save("kimi", "tok_a", "ref_a", expires_in=3600)
    mode = stat.S_IMODE(os.stat(s.path).st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"


def test_save_and_get():
    s = _tmp_store()
    s.save("kimi", "tok_a", "ref_a", expires_in=3600)
    entry = s.get("kimi")
    assert entry["access_token"] == "tok_a"
    assert entry["refresh_token"] == "ref_a"
    assert entry["expires_at"] > time.time()


def test_get_missing_provider_is_none():
    s = _tmp_store()
    assert s.get("nope") is None
    assert s.get_valid_key("nope") is None


def test_get_valid_key_not_expired_no_network_needed():
    s = _tmp_store()
    s.save("kimi", "tok_a", "ref_a", expires_in=3600)
    # no session passed and none needed -- token isn't expired
    assert s.get_valid_key("kimi") == "tok_a"


def test_get_valid_key_no_expiry_info_always_valid():
    s = _tmp_store()
    s.save("kimi", "tok_a")  # expires_in=0 -> "unknown expiry"
    assert s.get_valid_key("kimi") == "tok_a"


def test_get_valid_key_expired_no_refresh_token_returns_none():
    s = _tmp_store()
    s.save("kimi", "tok_a", refresh_token="", expires_in=-1)  # already expired
    assert s.get_valid_key("kimi") is None


def test_get_valid_key_expired_refreshes_and_persists():
    s = _tmp_store()
    s.save("kimi", "tok_old", "ref_old", expires_in=-1)  # already expired

    class FakeSession:
        def post(self, url, data=None, headers=None, timeout=15):
            class R:
                def json(self):
                    return {"access_token": "tok_new", "refresh_token": "ref_new", "expires_in": 3600}
            return R()

    cfg = ProviderConfig(
        name="kimi", device_auth_url="https://x/d", token_url="https://x/t", client_id="c",
    )
    key = s.get_valid_key("kimi", provider_cfg=cfg, session=FakeSession())
    assert key == "tok_new"
    # refreshed token was persisted
    entry = s.get("kimi")
    assert entry["access_token"] == "tok_new"
    assert entry["refresh_token"] == "ref_new"
    assert entry["expires_at"] > time.time()


def test_get_valid_key_refresh_failure_returns_none():
    s = _tmp_store()
    s.save("kimi", "tok_old", "ref_old", expires_in=-1)

    class FailingSession:
        def post(self, *a, **kw):
            class R:
                def json(self):
                    return {"error": "invalid_grant"}
            return R()

    cfg = ProviderConfig(
        name="kimi", device_auth_url="https://x/d", token_url="https://x/t", client_id="c",
    )
    assert s.get_valid_key("kimi", provider_cfg=cfg, session=FailingSession()) is None
    # the stale token is left in place, not wiped, in case a later retry succeeds
    assert s.get("kimi")["access_token"] == "tok_old"


def test_clear_removes_provider():
    s = _tmp_store()
    s.save("kimi", "tok_a")
    s.clear("kimi")
    assert s.get("kimi") is None


def test_available_providers():
    s = _tmp_store()
    s.save("kimi", "tok_a")
    s.save("zeta", "tok_b")
    assert s.available_providers() == ["kimi", "zeta"]


def test_load_provider_configs_missing_file():
    assert load_provider_configs("/nonexistent/oauth_providers.json") == {}


def test_load_provider_configs_parses_valid_entries():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    with open(p, "w") as f:
        json.dump(
            {
                "kimi": {
                    "device_auth_url": "https://a/d",
                    "token_url": "https://a/t",
                    "client_id": "cid",
                    "scope": "chat",
                    "api_base_url": "https://api.moonshot.ai/v1",
                }
            },
            f,
        )
    cfgs = load_provider_configs(p)
    assert "kimi" in cfgs
    assert cfgs["kimi"].client_id == "cid"
    assert cfgs["kimi"].api_base_url == "https://api.moonshot.ai/v1"


def test_load_provider_configs_skips_entries_missing_required_fields():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    with open(p, "w") as f:
        json.dump(
            {
                "broken": {"device_auth_url": "https://a/d"},  # missing token_url/client_id
                "ok": {"device_auth_url": "https://a/d", "token_url": "https://a/t", "client_id": "c"},
            },
            f,
        )
    cfgs = load_provider_configs(p)
    assert "broken" not in cfgs
    assert "ok" in cfgs


def test_load_provider_configs_malformed_json_is_empty():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    with open(p, "w") as f:
        f.write("{not valid json")
    assert load_provider_configs(p) == {}


def test_load_provider_configs_pkce_flow_requires_authorize_url_not_device_auth_url():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    with open(p, "w") as f:
        json.dump(
            {
                "google": {
                    "flow": "pkce",
                    "authorize_url": "https://accounts.example/auth",
                    "token_url": "https://oauth.example/token",
                    "client_id": "cid",
                    "client_secret": "csecret",
                }
            },
            f,
        )
    cfgs = load_provider_configs(p)
    assert "google" in cfgs
    assert cfgs["google"].flow == "pkce"
    assert cfgs["google"].client_secret == "csecret"


def test_load_provider_configs_openrouter_flow_needs_no_client_id():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    with open(p, "w") as f:
        json.dump(
            {
                "openrouter": {
                    "flow": "openrouter",
                    "authorize_url": "https://openrouter.ai/auth",
                    "token_url": "https://openrouter.ai/api/v1/auth/keys",
                }
            },
            f,
        )
    cfgs = load_provider_configs(p)
    assert "openrouter" in cfgs
    assert cfgs["openrouter"].client_id == ""


def test_save_provider_config_creates_and_merges():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    save_provider_config("github", path=p, device_auth_url="https://github.com/login/device/code",
                          token_url="https://github.com/login/oauth/access_token",
                          client_id="cid1", flow="device")
    cfgs = load_provider_configs(p)
    assert cfgs["github"].client_id == "cid1"
    # a later save for a different provider doesn't clobber the first
    save_provider_config("openrouter", path=p, flow="openrouter",
                          authorize_url="https://openrouter.ai/auth",
                          token_url="https://openrouter.ai/api/v1/auth/keys")
    cfgs = load_provider_configs(p)
    assert "github" in cfgs and "openrouter" in cfgs


def test_save_provider_config_writes_owner_only_permissions():
    import stat

    d = tempfile.mkdtemp()
    p = os.path.join(d, "oauth_providers.json")
    save_provider_config("github", path=p, device_auth_url="https://x/d", token_url="https://x/t",
                          client_id="cid1", flow="device")
    mode = stat.S_IMODE(os.stat(p).st_mode)
    assert mode == 0o600, f"expected 0600, got {oct(mode)}"
