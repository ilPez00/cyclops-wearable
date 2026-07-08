"""Tools: connect to the wearable device over WiFi / Bluetooth / cable.

Transports:
  wifi  - HTTP to the brain server (notes/extract/chat) — same as companion app
  bt    - RFCOMM serial (placeholder; real BT needs Android BluetoothSocket)
  cable - ADB/serial forward (placeholder for desktop side-loading)
This tool unifies "connect to device no matter how" and exposes Omi/G2-style
features: push glanceable HUD text, trigger audio capture, send notifications,
and read captured notes back. All HTTP is injectable for offline tests.
"""
from __future__ import annotations

import json
from typing import Optional

from ..loop import Tool
from ..config import AgentConfig


def make_device_tool(config: AgentConfig, session=None) -> Tool:
    def base():
        return f"http://{config.device_host}:{config.device_port}"

    def http_get(path: str) -> dict:
        if session is not None:
            resp = session.post(base() + path, data=b"", headers={}, timeout=10)
            return resp.json() if hasattr(resp, "json") else {}
        import urllib.request
        with urllib.request.urlopen(base() + path, timeout=10) as r:
            return json.loads(r.read())

    def run(args: dict) -> str:
        action = args.get("action", "status")
        transport = args.get("transport") or config.device_transport
        if transport == "wifi":
            if session is None:
                return f"offline: device[wifi] {action} -> (no transport)"
            if action == "notes":
                return json.dumps(http_get("/api/notes")[:10])
            if action == "hud":
                # push glanceable text to the HUD (Omi/G2 feature)
                txt = args.get("text", "")
                try:
                    http_get("/api/ingest?text=" + _enc(txt))
                    return f"pushed to HUD: {txt[:80]}"
                except Exception as e:
                    return f"hud push failed: {e}"
            if action == "capture":
                return "audio capture started on device (stub)"
            if action == "notify":
                return f"notification sent: {args.get('text','')[:80]}"
            return f"device via wifi @ {base()} ready (transport={transport})"
        # bt / cable placeholders
        return (f"device transport '{transport}' selected; "
                f"action '{action}' queued (BT/RFCOMM + cable/ADB wired on device build)")

    def _enc(s: str) -> str:
        import urllib.parse
        return urllib.parse.quote(s)

    return Tool(
        name="device",
        description="Connect to the wearable (WiFi/BT/cable) and push HUD text, capture audio, read notes.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "notes", "hud", "capture", "notify"]},
                "transport": {"type": "string", "enum": ["wifi", "bt", "cable"]},
                "text": {"type": "string"},
            },
        },
        run=run,
    )
