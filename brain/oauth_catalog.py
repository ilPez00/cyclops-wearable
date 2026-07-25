"""Static catalog of OAuth providers shown in the Android picker.

Researched against each provider's own docs (not OmniRoute's session-import
routes -- see the plan this shipped from for why): GitHub's real RFC 8628
device flow, OpenRouter's real zero-registration PKCE flow, Google's real
PKCE flow. Claude/ChatGPT have no third-party-usable OAuth grant for API
access, so they're listed (matching what the user asked to see) but marked
unsupported with a pointer to the existing API-key field in Settings instead
of silently omitted or faked.

Pure data, no network calls -- importable by app/server.py and tests alike.
"""

from __future__ import annotations

CATALOG: list[dict] = [
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "flow": "openrouter",
        "needs_client_id": False,
        "needs_client_secret": False,
        "scope": "",
        "api_base_url": "https://openrouter.ai/api/v1",
        "setup_url": "",
        "note": "No app registration needed -- tap to connect.",
    },
    {
        "id": "github",
        "label": "GitHub",
        "flow": "device",
        "needs_client_id": True,
        "needs_client_secret": False,
        "device_auth_url": "https://github.com/login/device/code",
        "token_url": "https://github.com/login/oauth/access_token",
        "scope": "read:user",
        "api_base_url": "https://models.github.ai/inference",
        "setup_url": "https://github.com/settings/applications/new",
        "note": "Free GitHub OAuth App (client ID only, no secret needed for device flow). Works through GitHub Models' OpenAI-compatible endpoint.",
    },
    {
        "id": "google",
        "label": "Google (Gemini)",
        "flow": "pkce",
        "needs_client_id": True,
        "needs_client_secret": True,
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/generative-language.retriever",
        "api_base_url": "",
        "setup_url": "https://console.cloud.google.com/apis/credentials",
        "note": "Needs a Google Cloud Console OAuth client (client ID + secret). Token will save, but Gemini's native API isn't OpenAI-compatible yet, so chat calls may not route through the cascade until that adapter exists.",
    },
    {
        "id": "claude",
        "label": "Claude",
        "flow": "unsupported",
        "needs_client_id": False,
        "needs_client_secret": False,
        "note": "No third-party OAuth grant for API access. Use your Anthropic API key in Settings instead.",
    },
    {
        "id": "chatgpt",
        "label": "ChatGPT",
        "flow": "unsupported",
        "needs_client_id": False,
        "needs_client_secret": False,
        "note": "No third-party OAuth grant for API access. Use your OpenAI API key in Settings instead.",
    },
]


def get(catalog_id: str) -> dict | None:
    for entry in CATALOG:
        if entry["id"] == catalog_id:
            return entry
    return None
