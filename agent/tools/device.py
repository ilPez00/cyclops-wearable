"""Tools: connect to the wearable device over WiFi / Bluetooth / cable.

Unifies "connect to device no matter how" behind one Transport (see
device/transport.py): WifiTransport (HTTP), BluetoothTransport (RFCOMM/serial),
CableTransport (ADB/serial). Exposes Omi/G2-style features: push glanceable
HUD text, trigger audio capture, send notifications, read captured notes.

The transport is injectable so the agent loop can be tested offline with a
FakeTransport. In production the server passes a real WifiTransport (or the
phone passes a BluetoothTransport), and `device_transport` picks the default.
"""
from __future__ import annotations

import json
import sys
from typing import Optional

from ..loop import Tool
from ..config import AgentConfig

# make device/ importable both as a package and from repo root
sys.path.insert(0, os_path := __import__("os").path.dirname(
    __import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from device.transport import build_transport, Transport, FakeTransport  # noqa: E402


def make_device_tool(config: AgentConfig, session=None, transport: Optional[Transport] = None) -> Tool:
    # resolve the active transport once
    active: Transport = transport or build_transport(
        config.device_transport, config=config, session=session)

    def run(args: dict) -> str:
        action = args.get("action", "status")
        requested = args.get("transport") or config.device_transport
        # allow per-call transport switch only if we can build it
        t = active
        if requested != config.device_transport and transport is None:
            try:
                t = build_transport(requested, config=config, session=session)
            except Exception:
                pass
        if action == "status":
            return f"device via {t.name} ready"
        if action == "notes":
            try:
                notes = t.request("/api/notes")
                return json.dumps(notes[:10])
            except Exception as e:
                return f"notes failed: {e}"
        if action == "hud":
            return t.push_hud(args.get("text", ""))
        if action == "notify":
            # notify == push a short HUD banner + a haptic cue (ACT_AGENT=14)
            return t.push_hud(args.get("text", "(notification)"))
        if action == "capture":
            # ACT_CAMERA=7 / audio capture; device handles the rest
            return t.send_cmd(7, args.get("media", "audio"))
        return f"device[{t.name}] {action} queued"

    return Tool(
        name="device",
        description="Connect to the wearable (WiFi/BT/cable) and push HUD text, capture audio, read notes, notify.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "notes", "hud", "capture", "notify"]},
                "transport": {"type": "string", "enum": ["wifi", "bt", "cable"]},
                "text": {"type": "string"},
                "media": {"type": "string"},
            },
        },
        run=run,
    )
