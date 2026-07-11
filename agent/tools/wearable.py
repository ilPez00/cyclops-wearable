"""Tools: wearable control — HUD text, notification buzz, capture.

Mirrors Omi / EvenRealities G2: push short text to the glasses HUD, trigger a
haptic buzz/notification, or ask the device to capture a photo / start a voice
recording. All go through the device transport (wifi/bt/cable) via the brain
server's /api/device endpoint. Offline stub returns what would happen.
"""

from __future__ import annotations

import json

from ..config import AgentConfig
from ..loop import Tool


def _make(
    action: str, name: str, desc: str, extra_props: dict, config: AgentConfig, session
) -> Tool:
    sess = session  # None => offline stub (safe default)
    host = config.device_host
    port = config.device_port

    def run(args: dict) -> str:
        if action == "capture" and not config.consent_mode:
            return "error: consent OFF — capture refused (enable via consent tool)"
        if sess is None:
            payload = {"action": action}
            payload.update({k: args.get(k) for k in extra_props})
            return f"offline: device[{config.device_transport}] {action} -> {payload}"
        payload = {"action": action}
        payload.update({k: args.get(k) for k in extra_props})
        if sess is None:
            return f"offline: device[{config.device_transport}] {action} -> {payload}"
        try:
            url = f"http://{host}:{port}/api/device"
            resp = sess.post(
                url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
                timeout=15,
            )
            return json.loads(resp.text if hasattr(resp, "text") else "{}").get(
                "result", "ok"
            )
        except Exception as e:
            return f"error: {e}"

    params = {
        "type": "object",
        "properties": {k: {"type": "string"} for k in extra_props},
        "required": list(extra_props),
    }
    return Tool(name=name, description=desc, parameters=params, run=run)


def make_hud_tool(config: AgentConfig, session=None) -> Tool:
    return _make(
        "hud",
        "hud",
        "Show short text on the wearable glasses HUD.",
        {"text": "string"},
        config,
        session,
    )


def make_notify_tool(config: AgentConfig, session=None) -> Tool:
    return _make(
        "notify",
        "notify",
        "Trigger a haptic buzz / system notification on the device.",
        {"message": "string"},
        config,
        session,
    )


def make_capture_tool(config: AgentConfig, session=None) -> Tool:
    return _make(
        "capture",
        "capture",
        "Ask the wearable to capture a photo or start/stop a voice recording.",
        {"media": "string", "command": "string"},
        config,
        session,
    )
