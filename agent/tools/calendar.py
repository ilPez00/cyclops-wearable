"""Tool: calendar / reminders / events — file-backed, offline-first.

Stores JSONL under ~/cyclops_data/calendar.jsonl. Supports add/list/delete
and natural-ish date parsing (today/tomorrow/+N days). The agent uses this to
create reminders captured from speech ("remind me to call mom tomorrow").
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta

from ..config import AgentConfig
from ..loop import Tool


def _parse_when(when: str) -> str:
    when = (when or "").lower().strip()
    today = datetime.now()
    if not when or when == "today":
        return today.strftime("%Y-%m-%d")
    if when == "tomorrow":
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.match(r"\+?(\d+)\s*d", when)
    if m:
        return (today + timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    # already a date-like string
    return when


def make_calendar_tool(config: AgentConfig) -> Tool:
    path = os.path.join(os.path.expanduser("~/cyclops_data"), "calendar.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def run(args: dict) -> str:
        action = args.get("action", "list")
        if action == "add":
            entry = {
                "when": _parse_when(args.get("when")),
                "title": args.get("title", ""),
                "kind": args.get("kind", "reminder"),
                "created": datetime.now().isoformat(timespec="seconds"),
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            return f"added {entry['kind']} on {entry['when']}: {entry['title']}"
        if action == "list":
            if not os.path.exists(path):
                return "no events"
            out = []
            for line in open(path, encoding="utf-8"):
                e = json.loads(line)
                out.append(f"{e['when']} [{e['kind']}] {e['title']}")
            return "\n".join(out[-20:]) or "no events"
        if action == "delete":
            if not os.path.exists(path):
                return "nothing to delete"
            keep, removed = [], 0
            for line in open(path, encoding="utf-8"):
                if args.get("title", "") in line:
                    removed += 1
                    continue
                keep.append(line)
            open(path, "w", encoding="utf-8").writelines(keep)
            return f"deleted {removed} matching entry"
        return "unknown calendar action"

    return Tool(
        name="calendar",
        description="Add or list reminders/events (when: today|tomorrow|+Nd).",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "delete"]},
                "title": {"type": "string"},
                "when": {"type": "string"},
                "kind": {"type": "string", "enum": ["reminder", "event", "task"]},
            },
            "required": ["action"],
        },
        run=run,
    )
