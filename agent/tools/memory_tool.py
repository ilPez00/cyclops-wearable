"""Tool: memory — read and append to the user's long-term memory.

Reads MEMORY.md/USER.md from the hermes home and lets the agent append notes
(the "remember that I prefer X" capability). Writes append to a per-session
memory file so the core memory files are never clobbered.
"""
from __future__ import annotations
import os
from ..loop import Tool
from ..config import AgentConfig


def make_memory_tool(config: AgentConfig) -> Tool:
    home = os.path.expanduser(config.hermes_home)
    mem_path = os.path.join(home, config.memory_file)
    append_path = os.path.join(os.path.expanduser("~/cyclops_data"), "memory_append.md")

    def run(args: dict) -> str:
        action = args.get("action", "read")
        if action == "read":
            if os.path.exists(mem_path):
                return open(mem_path, encoding="utf-8").read()[:2000]
            return "(no memory file)"
        if action == "append":
            note = args.get("note", "")
            if not note:
                return "error: note required"
            os.makedirs(os.path.dirname(append_path), exist_ok=True)
            with open(append_path, "a", encoding="utf-8") as f:
                f.write(f"- {note}\n")
            return f"remembered: {note}"
        return "unknown memory action"

    return Tool(
        name="memory",
        description="Read or append to the user's long-term memory.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["read", "append"]},
                "note": {"type": "string"},
            },
            "required": ["action"],
        },
        run=run,
    )
