"""Tool: memory — read / append / edit / delete the agent's long-term memory.

Ports Hermes's memory tool semantics into Cyclops: two persistent stores
(USER.md = who the user is, MEMORY.md = agent/world facts), addressed by a
`target` arg. The agent can both remember ("remember I prefer X" -> append to
USER.md) and manage what it knows (edit/delete a learned card).

All writes go to the Cyclops memory root (~/.cyclops/memory) so the user's
real ~/.hermes files are never touched.
"""

from __future__ import annotations

from ..config import AgentConfig
from ..loop import Tool


def make_memory_tool(config: AgentConfig) -> Tool:
    def run(args: dict) -> str:
        action = (args.get("action") or "read").lower()
        target = (args.get("target") or "agent").lower()
        if target not in ("agent", "user"):
            return "error: target must be 'agent' or 'user'"
        try:
            from ..memory import MemoryStore

            store = MemoryStore(config)
        except Exception as e:
            return f"error: memory store unavailable: {e}"

        if action == "read":
            cards = store.list(target)
            if not cards:
                return f"(no {target} memory yet)"
            return "\n".join(f"[{i}] {c.text}" for i, c in enumerate(cards))

        if action == "append":
            note = (args.get("note") or "").strip()
            if not note:
                return "error: note required"
            idx = store.append(note, target=target)
            return f"remembered ({target} card #{idx}): {note}"

        if action == "edit":
            try:
                idx = int(args.get("index", -1))
            except Exception:
                return "error: index must be an integer"
            text = (args.get("note") or "").strip()
            if store.edit(idx, text, target=target):
                return f"updated {target} card #{idx}"
            return f"error: no {target} card #{idx}"

        if action == "delete":
            try:
                idx = int(args.get("index", -1))
            except Exception:
                return "error: index must be an integer"
            if store.delete(idx, target=target):
                return f"deleted {target} card #{idx}"
            return f"error: no {target} card #{idx}"

        return "error: unknown action (read|append|edit|delete)"

    return Tool(
        name="memory",
        description=(
            "Read or manage long-term memory. target='user' stores facts about "
            "the user; target='agent' stores environment/world facts. "
            "actions: read, append (note=), edit (index=,note=), delete (index=)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "append", "edit", "delete"],
                },
                "target": {"type": "string", "enum": ["agent", "user"]},
                "note": {"type": "string"},
                "index": {"type": "integer"},
            },
            "required": ["action"],
        },
        run=run,
    )
