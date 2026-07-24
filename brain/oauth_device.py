"""OAuth 2.0 Device Authorization Grant (RFC 8628) client — generic, works with
any RFC-8628-compliant provider via config (device_auth_url/token_url/client_id/
scope), not hardcoded per-provider. Same testable shape as agent/cascade.py: the
HTTP session is injectable, so this is fully unit-testable with no real network.

No redirect URI, no callback server needed -- the user visits verification_uri
on ANY device and enters user_code (or opens verification_uri_complete
directly). Drivable identically from the Python brain, a CLI, or the Android
app -- exactly the gap OmniRoute already covers for itself but Cyclops didn't.

Usage (see app/server.py's /api/oauth/* handlers for the actual wiring):
    cfg = ProviderConfig(name="kimi", device_auth_url=..., token_url=...,
                          client_id=..., scope=..., api_base_url=...)
    dc = start_device_flow(cfg, session)
    # show dc.user_code / dc.verification_uri_complete to the user
    while True:
        r = poll_once(cfg, dc.device_code, session)
        if r.status == "complete": ... r.token.access_token ...
        elif r.status in ("expired", "denied"): break
        time.sleep(r.retry_after)
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass


class OAuthError(Exception):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


@dataclass
class ProviderConfig:
    name: str
    device_auth_url: str
    token_url: str
    client_id: str
    scope: str = ""
    api_base_url: str = ""  # the resulting OpenAI-compatible inference endpoint


@dataclass
class DeviceCode:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


@dataclass
class TokenResult:
    access_token: str
    refresh_token: str = ""
    expires_in: int = 0
    token_type: str = "Bearer"


@dataclass
class PollResult:
    status: str  # "pending" | "complete" | "expired" | "denied"
    token: TokenResult | None = None
    retry_after: int = 0  # seconds to wait before the next poll


def _post_form(session, url: str, data: dict) -> dict:
    """POST application/x-www-form-urlencoded (standard OAuth wire format),
    parse the JSON response. Raises OAuthError on transport failure."""
    body = urllib.parse.urlencode(data).encode()
    try:
        resp = session.post(
            url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=15,
        )
    except Exception as e:
        raise OAuthError(f"transport error: {e}", code="transport_error") from e
    try:
        return resp.json()
    except Exception as e:
        raise OAuthError(f"bad response: {e}", code="bad_response") from e


def start_device_flow(cfg: ProviderConfig, session) -> DeviceCode:
    data = {"client_id": cfg.client_id}
    if cfg.scope:
        data["scope"] = cfg.scope
    body = _post_form(session, cfg.device_auth_url, data)
    if "device_code" not in body:
        raise OAuthError(
            f"device_auth response missing device_code: {body}", code="bad_response"
        )
    return DeviceCode(
        device_code=body["device_code"],
        user_code=body.get("user_code", ""),
        verification_uri=body.get("verification_uri", body.get("verification_url", "")),
        verification_uri_complete=body.get("verification_uri_complete", ""),
        expires_in=int(body.get("expires_in", 900)),
        interval=int(body.get("interval", 5)),
    )


def poll_once(
    cfg: ProviderConfig, device_code: str, session, default_interval: int = 5
) -> PollResult:
    """One poll attempt (not a blocking loop — the caller controls pacing, so a
    long-lived HTTP server thread never blocks for the full ~15 min RFC 8628
    device-code lifetime; see app/server.py's /api/oauth/poll for why)."""
    data = {
        "client_id": cfg.client_id,
        "device_code": device_code,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
    }
    body = _post_form(session, cfg.token_url, data)
    if "access_token" in body:
        return PollResult(
            status="complete",
            token=TokenResult(
                access_token=body["access_token"],
                refresh_token=body.get("refresh_token", ""),
                expires_in=int(body.get("expires_in", 0)),
                token_type=body.get("token_type", "Bearer"),
            ),
        )
    err = body.get("error", "")
    if err == "authorization_pending":
        return PollResult(status="pending", retry_after=default_interval)
    if err == "slow_down":
        # RFC 8628 §3.5: increase the interval by 5s and use it going forward
        return PollResult(status="pending", retry_after=default_interval + 5)
    if err == "expired_token":
        return PollResult(status="expired")
    if err == "access_denied":
        return PollResult(status="denied")
    raise OAuthError(f"device token poll error: {body}", code=err or "unknown")


def refresh(cfg: ProviderConfig, refresh_token: str, session) -> TokenResult:
    data = {
        "client_id": cfg.client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    body = _post_form(session, cfg.token_url, data)
    if "access_token" not in body:
        raise OAuthError(
            f"refresh response missing access_token: {body}",
            code=body.get("error", "bad_response"),
        )
    return TokenResult(
        access_token=body["access_token"],
        # some providers rotate the refresh token, some don't -- keep the old
        # one if a new one wasn't issued
        refresh_token=body.get("refresh_token", refresh_token),
        expires_in=int(body.get("expires_in", 0)),
        token_type=body.get("token_type", "Bearer"),
    )
