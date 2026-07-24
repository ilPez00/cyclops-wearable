"""OAuth device-flow (RFC 8628) client — fully offline, scripted fake HTTP."""

import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.oauth_device import (
    OAuthError,
    ProviderConfig,
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
