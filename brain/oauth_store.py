"""Persists OAuth device-flow tokens and transparently refreshes expired ones.

Plaintext JSON at ~/.cyclops/oauth_tokens.json -- same trust model as the
already-plaintext api_key field in ~/.cyclops/profile.json (agent/config.py),
not a new regression. Provider OAuth *client* config (device_auth_url,
token_url, client_id, scope, api_base_url) lives separately in
~/.cyclops/oauth_providers.json -- see load_provider_configs() -- since that
file is what a user populates with their own registered OAuth app details and
is conceptually static, while oauth_tokens.json is generated/rotated at runtime.

get_valid_key() is the integration point brain/aikeys.py calls: synchronous,
refreshes inline if expired, matching how resolve_key() is already called
synchronously from ModelRouter.chat() elsewhere in this codebase -- no
background refresh thread needed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from .oauth_device import OAuthError, ProviderConfig, refresh

DEFAULT_TOKENS_PATH = "~/.cyclops/oauth_tokens.json"
DEFAULT_PROVIDERS_PATH = "~/.cyclops/oauth_providers.json"


def _atomic_write_json_0600(path: Path, data: dict) -> None:
    """Write `data` as JSON to `path`, owner-only (0600) rather than
    inheriting the process umask (typically 0644, group/world-readable).
    os.open + fdopen so the restrictive mode applies atomically at creation,
    not as a chmod race after the fact. Shared by token writes (refresh
    tokens) and provider-config writes (client_secret) -- both equally
    sensitive."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2))
    os.chmod(path, 0o600)  # belt-and-suspenders in case the file pre-existed with looser perms


def load_provider_configs(path: str | None = None) -> dict[str, ProviderConfig]:
    """Read the user-supplied OAuth client config file. Missing file (the
    common case -- most installs never use device-flow providers) or a
    malformed one both degrade to "no providers configured", not an error."""
    p = Path(path or os.environ.get("CYCLOPS_OAUTH_PROVIDERS", DEFAULT_PROVIDERS_PATH)).expanduser()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for name, cfg in (raw or {}).items():
        if not isinstance(cfg, dict):
            continue
        flow = cfg.get("flow", "device")
        # device flow needs device_auth_url; pkce needs authorize_url. Both
        # need token_url. client_id is required except for the openrouter
        # flow, which doesn't use one at all.
        required = ["token_url"]
        required.append("device_auth_url" if flow == "device" else "authorize_url")
        if flow != "openrouter":
            required.append("client_id")
        if any(cfg.get(k) is None for k in required):
            continue  # missing a required field -- skip this one provider, not the whole file
        out[name] = ProviderConfig(
            name=name,
            device_auth_url=cfg.get("device_auth_url", ""),
            token_url=cfg.get("token_url", ""),
            client_id=cfg.get("client_id", ""),
            scope=cfg.get("scope", ""),
            api_base_url=cfg.get("api_base_url", ""),
            flow=flow,
            authorize_url=cfg.get("authorize_url", ""),
            client_secret=cfg.get("client_secret", ""),
        )
    return out


def save_provider_config(name: str, path: str | None = None, **fields) -> None:
    """Merge `fields` (device_auth_url/token_url/client_id/scope/api_base_url/
    flow/authorize_url/client_secret) into provider `name`'s entry in
    oauth_providers.json, creating the file if needed. Used by the GUI
    provider picker so a user never has to hand-edit this file -- see
    app/server.py's /api/oauth/start catalog_id path."""
    p = Path(path or os.environ.get("CYCLOPS_OAUTH_PROVIDERS", DEFAULT_PROVIDERS_PATH)).expanduser()
    data = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
    entry = data.get(name, {})
    entry.update({k: v for k, v in fields.items() if v is not None})
    data[name] = entry
    _atomic_write_json_0600(p, data)


class OAuthStore:
    def __init__(self, path: str | None = None, session=None):
        self.path = Path(path or os.environ.get("CYCLOPS_OAUTH_TOKENS", DEFAULT_TOKENS_PATH)).expanduser()
        self._session = session  # injected for tests; real refresh needs a real one

    # ------------------------------------------------------------- storage
    def _read_all(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _write_all(self, data: dict) -> None:
        _atomic_write_json_0600(self.path, data)

    def save(
        self, provider: str, access_token: str, refresh_token: str = "", expires_in: int = 0
    ) -> None:
        data = self._read_all()
        data[provider] = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": (time.time() + expires_in) if expires_in else 0,
        }
        self._write_all(data)

    def get(self, provider: str) -> Optional[dict]:
        return self._read_all().get(provider)

    def clear(self, provider: str) -> None:
        data = self._read_all()
        if provider in data:
            del data[provider]
            self._write_all(data)

    # -------------------------------------------------------- resolution
    def get_valid_key(
        self, provider: str, provider_cfg: ProviderConfig | None = None, session=None
    ) -> Optional[str]:
        """Return a usable access token for `provider`, refreshing first if
        expired. Returns None (never raises) if there's no token, no refresh
        token, or the refresh itself fails -- callers (AiKeys) treat "no key"
        as "this provider just isn't available", not an error."""
        entry = self.get(provider)
        if not entry:
            return None
        expires_at = entry.get("expires_at") or 0
        # 0 = "no expiry info" (some providers don't return expires_in) -- treat as always valid
        if expires_at and time.time() >= expires_at:
            if not entry.get("refresh_token") or provider_cfg is None:
                return None  # expired with no way to refresh
            try:
                sess = session or self._session
                if sess is None:
                    from agent.models import _default_session  # lazy import

                    sess = _default_session()
                tok = refresh(provider_cfg, entry["refresh_token"], sess)
            except OAuthError:
                return None
            self.save(provider, tok.access_token, tok.refresh_token, tok.expires_in)
            return tok.access_token
        return entry.get("access_token")

    def available_providers(self) -> list[str]:
        """Providers with a token on file (expired-but-refreshable still
        counts -- AiKeys.available() callers care about "configured", not
        "currently valid"; get_valid_key() is where expiry actually matters)."""
        return sorted(self._read_all().keys())
