"""Tools: talk to the Cyclops brain server (notes / extract / chat)."""

from __future__ import annotations

import json

from ..config import AgentConfig
from ..loop import Tool


def make_brain_tool(config: AgentConfig, session=None) -> Tool:
    def base():
        return f"http://{config.device_host}:{config.device_port}"

    def get(path: str) -> object:
        if session is not None:
            return session.post(base() + path, data=b"", headers={}, timeout=10).json()
        import urllib.request

        with urllib.request.urlopen(base() + path, timeout=10) as r:
            return json.loads(r.read())

    def run(args: dict) -> str:
        action = args.get("action", "notes")
        if session is None:
            return f"offline: brain {action} -> (no transport)"
        if action == "notes":
            return json.dumps(get("/api/notes")[:20])
        if action == "extract":
            txt = args.get("text", "")
            import urllib.parse

            return json.dumps(get("/api/extract?text=" + urllib.parse.quote(txt))[:20])
        if action == "chat":
            txt = args.get("text", "")
            import urllib.parse

            return json.dumps(get("/api/chat?text=" + urllib.parse.quote(txt)))
        return "unknown brain action"

    return Tool(
        name="brain",
        description="Query the Cyclops brain server: list notes, extract notes from text, chat.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["notes", "extract", "chat"]},
                "text": {"type": "string"},
            },
        },
        run=run,
    )
