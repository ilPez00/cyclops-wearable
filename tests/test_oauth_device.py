"""OAuth device-flow (RFC 8628) client — fully offline, scripted fake HTTP."""

import base64
import hashlib
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.oauth_device import (
    OAuthError,
    ProviderConfig,
    build_openrouter_authorize_url,
    build_pkce_authorize_url,
    exchange_openrouter_code,
    exchange_pkce_code,
    generate_pkce_pair,
    generate_state,
    poll_once,
    refresh,
    start_device_flow,
)


class FakeResp:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class ScriptedSession:
    """Returns a queued JSON body per POST; records (url, parsed form data)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=15):
        parsed = dict(urllib.parse.parse_qsl(data.decode()))
        self.calls.append((url, parsed))
        return FakeResp(self.script.pop(0))


def _cfg(**overrides):
    base = dict(
        name="testprov",
        device_auth_url="https://auth.example/device/code",
        token_url="https://auth.example/oauth/token",
        client_id="client-123",
        scope="chat",
    )
    base.update(overrides)
    return ProviderConfig(**base)


def test_start_device_flow_happy_path():
    sess = ScriptedSession(
        [
            {
                "device_code": "dc1",
                "user_code": "ABCD-1234",
                "verification_uri": "https://auth.example/activate",
                "verification_uri_complete": "https://auth.example/activate?code=ABCD-1234",
                "expires_in": 900,
                "interval": 5,
            }
        ]
    )
    dc = start_device_flow(_cfg(), sess)
    assert dc.device_code == "dc1"
    assert dc.user_code == "ABCD-1234"
    assert dc.interval == 5
    url, form = sess.calls[0]
    assert url == "https://auth.example/device/code"
    assert form["client_id"] == "client-123"
    assert form["scope"] == "chat"
    print("OK start_device_flow happy path")


def test_start_device_flow_bad_response_raises():
    sess = ScriptedSession([{"error": "invalid_client"}])
    try:
        start_device_flow(_cfg(), sess)
        assert False, "should raise when device_code is missing"
    except OAuthError as e:
        assert e.code == "bad_response"
    print("OK start_device_flow rejects a response with no device_code")


def test_poll_pending_then_complete():
    sess = ScriptedSession(
        [
            {"error": "authorization_pending"},
            {"access_token": "tok_abc", "refresh_token": "ref_abc", "expires_in": 3600},
        ]
    )
    r1 = poll_once(_cfg(), "dc1", sess)
    assert r1.status == "pending" and r1.retry_after == 5
    r2 = poll_once(_cfg(), "dc1", sess)
    assert r2.status == "complete"
    assert r2.token.access_token == "tok_abc"
    assert r2.token.refresh_token == "ref_abc"
    assert r2.token.expires_in == 3600
    print("OK poll: pending then complete")


def test_poll_slow_down_bumps_interval():
    sess = ScriptedSession([{"error": "slow_down"}])
    r = poll_once(_cfg(), "dc1", sess, default_interval=5)
    assert r.status == "pending"
    assert r.retry_after == 10  # 5 + 5 per RFC 8628 3.5
    print("OK poll: slow_down bumps retry interval")


def test_poll_expired_and_denied():
    sess = ScriptedSession([{"error": "expired_token"}, {"error": "access_denied"}])
    r1 = poll_once(_cfg(), "dc1", sess)
    assert r1.status == "expired"
    r2 = poll_once(_cfg(), "dc1", sess)
    assert r2.status == "denied"
    print("OK poll: expired_token and access_denied map correctly")


def test_poll_unknown_error_raises():
    sess = ScriptedSession([{"error": "server_error"}])
    try:
        poll_once(_cfg(), "dc1", sess)
        assert False, "should raise on an unrecognized error code"
    except OAuthError as e:
        assert e.code == "server_error"
    print("OK poll: unrecognized error code raises")


def test_refresh_happy_path():
    sess = ScriptedSession([{"access_token": "tok_new", "expires_in": 3600}])
    tok = refresh(_cfg(), "ref_old", sess)
    assert tok.access_token == "tok_new"
    # provider didn't rotate the refresh token -> old one is kept
    assert tok.refresh_token == "ref_old"
    url, form = sess.calls[0]
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "ref_old"
    print("OK refresh happy path, keeps old refresh_token when not rotated")


def test_refresh_rotates_token_when_provided():
    sess = ScriptedSession(
        [{"access_token": "tok_new", "refresh_token": "ref_new", "expires_in": 3600}]
    )
    tok = refresh(_cfg(), "ref_old", sess)
    assert tok.refresh_token == "ref_new"
    print("OK refresh rotates the refresh_token when the provider issues a new one")


def test_refresh_failure_raises():
    sess = ScriptedSession([{"error": "invalid_grant"}])
    try:
        refresh(_cfg(), "ref_old", sess)
        assert False, "should raise when refresh fails"
    except OAuthError as e:
        assert e.code == "invalid_grant"
    print("OK refresh: invalid_grant raises")


def test_transport_error_wrapped():
    class BrokenSession:
        def post(self, *a, **kw):
            raise ConnectionError("no route to host")

    try:
        start_device_flow(_cfg(), BrokenSession())
        assert False, "should raise on transport failure"
    except OAuthError as e:
        assert e.code == "transport_error"
    print("OK transport failure wrapped as OAuthError")


# --- PKCE (RFC 7636) --------------------------------------------------------


class JsonScriptedSession:
    """Like ScriptedSession, but for JSON-body POSTs (OpenRouter's exchange)."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def post(self, url, data=None, headers=None, timeout=15):
        parsed = json.loads(data.decode())
        self.calls.append((url, parsed, headers))
        return FakeResp(self.script.pop(0))


def _pkce_cfg(**overrides):
    base = dict(
        name="google",
        authorize_url="https://accounts.example/o/auth",
        token_url="https://oauth.example/token",
        client_id="client-abc",
        client_secret="secret-xyz",
        scope="chat",
        flow="pkce",
    )
    base.update(overrides)
    return ProviderConfig(**base)


def test_generate_pkce_pair_challenge_matches_verifier():
    verifier, challenge = generate_pkce_pair()
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected
    assert 43 <= len(verifier) <= 128
    assert "=" not in challenge
    print("OK generate_pkce_pair: S256 challenge matches verifier, RFC 7636 length bounds")


def test_generate_state_is_random_and_nonempty():
    a, b = generate_state(), generate_state()
    assert a and b and a != b
    print("OK generate_state produces distinct non-empty tokens")


def test_build_pkce_authorize_url_includes_required_params():
    url = build_pkce_authorize_url(_pkce_cfg(), "http://host/api/oauth/callback", "state1", "chal1")
    assert url.startswith("https://accounts.example/o/auth?")
    qs = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))
    assert qs["response_type"] == "code"
    assert qs["client_id"] == "client-abc"
    assert qs["redirect_uri"] == "http://host/api/oauth/callback"
    assert qs["state"] == "state1"
    assert qs["code_challenge"] == "chal1"
    assert qs["code_challenge_method"] == "S256"
    assert qs["scope"] == "chat"
    print("OK build_pkce_authorize_url includes response_type/client_id/redirect_uri/state/PKCE params")


def test_exchange_pkce_code_includes_client_secret_when_set():
    sess = ScriptedSession([{"access_token": "tok1", "refresh_token": "ref1", "expires_in": 3600}])
    tok = exchange_pkce_code(_pkce_cfg(), "code1", "http://host/cb", "verifier1", sess)
    assert tok.access_token == "tok1"
    assert tok.refresh_token == "ref1"
    url, form = sess.calls[0]
    assert url == "https://oauth.example/token"
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "code1"
    assert form["redirect_uri"] == "http://host/cb"
    assert form["code_verifier"] == "verifier1"
    assert form["client_secret"] == "secret-xyz"
    print("OK exchange_pkce_code sends client_secret when the provider config has one")


def test_exchange_pkce_code_omits_client_secret_when_unset():
    sess = ScriptedSession([{"access_token": "tok1"}])
    exchange_pkce_code(_pkce_cfg(client_secret=""), "code1", "http://host/cb", "v1", sess)
    _, form = sess.calls[0]
    assert "client_secret" not in form
    print("OK exchange_pkce_code omits client_secret for public clients")


def test_exchange_pkce_code_bad_response_raises():
    sess = ScriptedSession([{"error": "invalid_grant"}])
    try:
        exchange_pkce_code(_pkce_cfg(), "code1", "http://host/cb", "v1", sess)
        assert False, "should raise when access_token is missing"
    except OAuthError as e:
        assert e.code == "invalid_grant"
    print("OK exchange_pkce_code raises OAuthError on failure")


# --- OpenRouter's PKCE variant ----------------------------------------------


def test_build_openrouter_authorize_url():
    url = build_openrouter_authorize_url("http://host/cb?state=s1", "chal1")
    assert url.startswith("https://openrouter.ai/auth?")
    qs = dict(urllib.parse.parse_qsl(url.split("?", 1)[1]))
    assert qs["callback_url"] == "http://host/cb?state=s1"
    assert qs["code_challenge"] == "chal1"
    assert qs["code_challenge_method"] == "S256"
    print("OK build_openrouter_authorize_url: callback_url + PKCE params, no client_id")


def test_exchange_openrouter_code_maps_key_to_access_token():
    sess = JsonScriptedSession([{"key": "sk-or-v1-abc"}])
    tok = exchange_openrouter_code("code1", "verifier1", sess)
    assert tok.access_token == "sk-or-v1-abc"
    assert tok.refresh_token == ""
    assert tok.expires_in == 0  # OpenRouter keys don't expire
    url, body, headers = sess.calls[0]
    assert url == "https://openrouter.ai/api/v1/auth/keys"
    assert body == {"code": "code1", "code_verifier": "verifier1", "code_challenge_method": "S256"}
    assert headers["Content-Type"] == "application/json"
    print("OK exchange_openrouter_code: JSON body, 'key' field maps to access_token, never expires")


def test_exchange_openrouter_code_bad_response_raises():
    sess = JsonScriptedSession([{"error": "invalid_code"}])
    try:
        exchange_openrouter_code("code1", "v1", sess)
        assert False, "should raise when key is missing"
    except OAuthError as e:
        assert e.code == "invalid_code"
    print("OK exchange_openrouter_code raises OAuthError on failure")
