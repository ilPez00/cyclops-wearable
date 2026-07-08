"""Tools: export WhatsApp chats to feed the AI.

Parses the standard WhatsApp export format (txt with date/time sender: body)
and returns a condensed, AI-friendly summary plus per-contact threads. This is
the "export WhatsApp chats to feed the AI" feature.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from ..loop import Tool


# Matches: 12/04/2026, 14:33 - Sender: message
_LINE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),?\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*"
    r"([^:]+?):\s?(.*)$")


def parse_export(text: str) -> dict:
    threads = defaultdict(list)
    cur = None
    for raw in text.splitlines():
        m = _LINE.match(raw)
        if m:
            sender = m.group(3).strip()
            body = m.group(4).strip()
            threads[sender].append(body)
            cur = (sender, body)
        elif cur and raw.strip():
            # continuation / media line attached to previous message
            threads[cur[0]].append(raw.strip())
    summary = {k: v for k, v in threads.items()}
    return {
        "participants": list(threads.keys()),
        "counts": {k: len(v) for k, v in threads.items()},
        "threads": summary,
    }


def make_whatsapp_tool(root: str = "~") -> Tool:
    def run(args: dict) -> str:
        path = args.get("path") or args.get("text")
        if not path:
            return "error: provide 'path' to a WhatsApp export .txt"
        import os
        p = os.path.expanduser(path)
        if not os.path.exists(p):
            return f"error: file not found: {p}"
        with open(p, encoding="utf-8", errors="ignore") as f:
            data = parse_export(f.read())
        # condense: keep counts + a short sample per participant for the model
        out = [f"participants: {', '.join(data['participants'])}"]
        for who, msgs in data["threads"].items():
            sample = " | ".join(msgs[:5])
            out.append(f"[{who}] ({data['counts'][who]} msgs) {sample}")
        return "\n".join(out)[:4000]

    return Tool(
        name="whatsapp_export",
        description="Parse a WhatsApp chat export (.txt) into per-contact threads to feed the AI.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "path to WhatsApp export txt"},
            },
            "required": ["path"],
        },
        run=run,
    )
