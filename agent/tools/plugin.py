"""Tool: plugin — list / sync the local-first plugin marketplace (P2-A).

Offline-safe: sync falls back to a graceful 'offline' status when no network.
No remote code execution — install only drops validated manifests.
"""

from __future__ import annotations

import os

from ..config import AgentConfig
from ..loop import Tool
from ..plugins import PluginRegistry, sync_index


def make_plugin_tool(
    config: AgentConfig, plugin_dir: str = None, index_url: str = None
) -> Tool:
    plugin_dir = plugin_dir or os.path.join(
        os.path.expanduser(config.config_dir), "plugins"
    )
    index_url = index_url or getattr(config, "plugin_index_url", None)

    def run(args: dict) -> str:
        reg = PluginRegistry(plugin_dir)
        action = (args.get("action") or "list").lower()
        if action == "list":
            items = reg.list()
            if not items:
                return "no plugins installed (run: plugin sync)"
            return "\n".join(
                f"- {m.name} v{m.version} [{m.kind}] {m.description}" for m in items
            )
        if action == "show":
            name = args.get("name")
            m = reg.get(name) if name else None
            return m.to_json() if m else f"plugin not found: {name}"
        if action == "sync":
            if not index_url:
                return "plugin sync: no index url configured (offline)"
            installed = sync_index(index_url, plugin_dir)
            if not installed:
                return "plugin sync: offline or empty index (nothing installed)"
            return "plugin sync installed: " + ", ".join(m.name for m in installed)
        return f"unknown plugin action: {action}"

    return Tool(
        name="plugin",
        description="List/sync the local-first plugin marketplace (offline-safe).",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "show", "sync"]},
                "name": {"type": "string"},
            },
            "required": [],
        },
        run=run,
    )


# `os` is imported at module top; placeholder removed.
