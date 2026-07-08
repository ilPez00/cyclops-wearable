"""Tool: read the in-session conversation history of the agent.

Lets the agent (or the user via a tool call) recall what was said earlier in
the current session — the "memory" pillar. Returns the last N turns as text.
"""
from __future__ import annotations

from ..loop import Tool


def make_history_tool(agent, limit: int = 20) -> Tool:
    def run(args: dict) -> str:
        n = int(args.get("limit", limit))
        hist = agent.history[-n:] if n > 0 else agent.history
        if not hist:
            return "(no history yet this session)"
        lines = []
        for m in hist:
            role = m.get("role")
            c = m.get("content")
            if isinstance(c, list):
                c = " ".join(b.get("text", "") for b in c if isinstance(b, dict))
            lines.append(f"{role}: {c}")
        return "\n".join(lines)

    return Tool(
        name="history",
        description="Recall the recent conversation in this session (last N turns).",
        parameters={
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "max turns to return"}},
        },
        run=run,
    )
