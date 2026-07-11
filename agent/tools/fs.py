"""Tools: safe file read/write (file_safety-style guard)."""

from __future__ import annotations

import os
from pathlib import Path

from ..config import AgentConfig
from ..loop import Tool


def make_fs_tool(config: AgentConfig) -> Tool:
    allowed_roots = [
        os.path.expanduser("~/cyclops_data"),
        os.path.expanduser("~/Documents"),
    ]

    def run(args: dict) -> str:
        action = args.get("action", "read")
        path = os.path.expanduser(args.get("path", ""))
        if not path:
            return "error: path required"
        if not _safe(path, allowed_roots) and not config.allow_fs_write:
            return "error: path outside allowed roots"
        if action == "read":
            try:
                return Path(path).read_text(errors="ignore")[:4000]
            except Exception as e:
                return f"error: {e}"
        if action == "write":
            if not config.allow_fs_write:
                return "error: fs write disabled"
            try:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(args.get("text", ""), encoding="utf-8")
                return f"wrote {path}"
            except Exception as e:
                return f"error: {e}"
        return "unknown fs action"

    def _safe(path: str, roots: list) -> bool:
        p = os.path.abspath(path)
        return any(p.startswith(os.path.abspath(r)) for r in roots)

    return Tool(
        name="fs",
        description="Safely read or write files under allowed roots.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "write"]},
                "path": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["action", "path"],
        },
        run=run,
    )
