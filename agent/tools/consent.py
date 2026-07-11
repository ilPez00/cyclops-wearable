"""Tool: consent — Omi-style Consent Mode (P0-D).

Privacy control for always-on capture. When consent is OFF, the wearable /
companion must refuse to start recording or capture a photo. The tool toggles
the flag (persisted via config) and reports status; capture/camera tools read
the same flag and decline when off.
"""
from __future__ import annotations

from ..config import AgentConfig
from ..loop import Tool


def make_consent_tool(config: AgentConfig) -> Tool:
    def run(args: dict) -> str:
        action = (args.get("action") or "status").lower()
        if action == "on":
            config.consent_mode = True
            return "consent: ON — capture/recording allowed"
        if action == "off":
            config.consent_mode = False
            return "consent: OFF — capture/recording refused"
        if action in ("status", "get"):
            return f"consent: {'ON' if config.consent_mode else 'OFF'}"
        return "usage: consent action=on|off|status"
    return Tool(
        name="consent",
        description="Toggle or check Consent Mode (privacy gate for capture/recording).",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "on|off|status"},
            },
            "required": [],
        },
        run=run,
    )


def consent_required(config: AgentConfig) -> bool:
    """True when capture is currently blocked (consent off)."""
    return not config.consent_mode
