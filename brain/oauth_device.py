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

import base64
import hashlib
import json as _json
import secrets
import urllib.parse
from dataclasses import dataclass


class OAuthError(Exception):
    def __init__(self, message: str, code: str = ""):
        super().__init__(message)
        self.code = code


@dataclass
class ProviderConfig:
    name: str
    device_auth_url: str = ""
    token_url: str = ""
    client_id: str = ""
    scope: str = ""
    api_base_url: str = ""  # the resulting OpenAI-compatible inference endpoint
    flow: str = "device"  # "device" | "pkce" | "openrouter"
    authorize_url: str = ""  # used by "pkce" flow instead of device_auth_url
    client_secret: str = ""  # optional -- some PKCE providers (Google) still issue one


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


# --- authorization_code + PKCE (RFC 6749 + RFC 7636) ----------------------
# The counterpart to the device flow above for providers that require a
# browser redirect rather than a polled user_code (GitHub device flow above
# covers the no-redirect case; this covers Google/Gemini and any future
# standard PKCE provider). No redirect URI is baked into ProviderConfig --
# it's derived per-request from the brain server's own reachable host (see
# app/server.py's /api/oauth/start), so the same provider config works
# whether the brain is reached via LAN IP, hostname, or an adb-reverse
# tunnel, without editing oauth_providers.json per install.


def generate_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge) using S256, per RFC 7636 §4.2."""
    verifier = secrets.token_urlsafe(64)  # 86 chars, well within the 43-128 range
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(24)


def build_pkce_authorize_url(
    cfg: ProviderConfig, redirect_uri: str, state: str, code_challenge: str
) -> str:
    params = {
        "response_type": "code",
        "client_id": cfg.client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    if cfg.scope:
        params["scope"] = cfg.scope
    return f"{cfg.authorize_url}?{urllib.parse.urlencode(params)}"


def exchange_pkce_code(
    cfg: ProviderConfig, code: str, redirect_uri: str, code_verifier: str, session
) -> TokenResult:
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg.client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if cfg.client_secret:
        data["client_secret"] = cfg.client_secret
    body = _post_form(session, cfg.token_url, data)
    if "access_token" not in body:
        raise OAuthError(
            f"pkce token exchange failed: {body}", code=body.get("error", "bad_response")
        )
    return TokenResult(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token", ""),
        expires_in=int(body.get("expires_in", 0)),
        token_type=body.get("token_type", "Bearer"),
    )


# --- OpenRouter's PKCE variant ---------------------------------------------
# Not a standard OAuth2 token endpoint: no client_id/client_secret at all (any
# app can use it -- that's the point, zero registration), JSON request body
# instead of form-urlencoded, and the response is a persistent API key under
# "key" rather than an access/refresh token pair. Documented at
# https://openrouter.ai/docs/use-cases/oauth-pkce -- kept as its own pair of
# functions rather than bending build_pkce_authorize_url/exchange_pkce_code
# with flags, since the wire shape genuinely isn't the same protocol.
OPENROUTER_AUTHORIZE_URL = "https://openrouter.ai/auth"
OPENROUTER_TOKEN_URL = "https://openrouter.ai/api/v1/auth/keys"


def build_openrouter_authorize_url(redirect_uri: str, code_challenge: str) -> str:
    params = {
        "callback_url": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{OPENROUTER_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def exchange_openrouter_code(code: str, code_verifier: str, session) -> TokenResult:
    payload = _json.dumps(
        {"code": code, "code_verifier": code_verifier, "code_challenge_method": "S256"}
    ).encode()
    try:
        resp = session.post(
            OPENROUTER_TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15,
        )
    except Exception as e:
        raise OAuthError(f"transport error: {e}", code="transport_error") from e
    try:
        body = resp.json()
    except Exception as e:
        raise OAuthError(f"bad response: {e}", code="bad_response") from e
    if "key" not in body:
        # OpenRouter's error field can be a nested object (observed live:
        # {"error": {"message": "Invalid code", "code": 400}}), not always a
        # bare string like the RFC 8628 providers -- OAuthError.code is
        # typed str, so coerce rather than silently stash a dict in it.
        raise OAuthError(
            f"openrouter key exchange failed: {body}",
            code=str(body.get("error", "bad_response")),
        )
    return TokenResult(access_token=body["key"], refresh_token="", expires_in=0)
