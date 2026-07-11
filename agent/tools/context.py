"""Tool: context — surface / refresh the agent's live fused context (P2-B).

Reads the brain ContextAssembler (notes + fused health + calendar) so the
agent can answer "what's my day look like" or "how's my HR" without dipping
into raw sources. The assembler is injected by the server (shared with the
agent loop); offline-safe if none is wired.
"""
from __future__ import annotations

from ..config import AgentConfig
from ..loop import Tool


def make_context_tool(config: AgentConfig, assembler=None) -> Tool:
    def run(args: dict) -> str:
        if assembler is None:
            return "no live context assembler wired (notes/health/calendar silent)"
        action = (args.get("action") or "show").lower()
        if action == "reload":
            # re-read the last loaded calendar file if one was recorded
            if getattr(assembler, "_calendar_path", None):
                assembler.load_calendar(assembler._calendar_path)
            return assembler.render()
        return assembler.render()
    return Tool(
        name="context",
        description="Show the fused live context (notes + health + calendar).",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["show", "reload"]},
            },
            "required": [],
        },
        run=run,
    )
