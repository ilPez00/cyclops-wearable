"""Tool: health — read the user's health signals from the digiGio brain.

Looks under digigio_home for health.jsonl / vitals / steps / sleep exports.
Returns a condensed summary so the agent can answer "how did I sleep" or log
a workout. Privacy-first: only reads, never uploads raw data outside the loop.
"""
from __future__ import annotations
import os, json, glob
from ..loop import Tool
from ..config import AgentConfig


def make_health_tool(config: AgentConfig) -> Tool:
    root = os.path.expanduser(config.digigio_home)

    def run(args: dict) -> str:
        action = args.get("action", "summary")
        if action == "summary":
            lines = []
            for f in glob.glob(os.path.join(root, "**", "health*.jsonl"), recursive=True)[:3]:
                try:
                    for ln in open(f, encoding="utf-8"):
                        d = json.loads(ln)
                        lines.append(str(d))
                except Exception:
                    pass
            # also scan a flat vitals file
            vf = os.path.join(root, "health", "vitals.json")
            if os.path.exists(vf):
                try: lines.append(open(vf, encoding="utf-8").read()[:800])
                except Exception: pass
            return "\n".join(lines[-15:]) or "no health data available"
        if action == "log":
            path = os.path.join(root, "health", "log.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"note": args.get("note", ""),
                                    "ts": __import__("datetime").datetime.now().isoformat(timespec="seconds")}) + "\n")
            return f"logged health note: {args.get('note', '')}"
        return "unknown health action"

    return Tool(
        name="health",
        description="Read or log the user's health data from the digiGio brain.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["summary", "log"]},
                "note": {"type": "string"},
            },
            "required": ["action"],
        },
        run=run,
    )
