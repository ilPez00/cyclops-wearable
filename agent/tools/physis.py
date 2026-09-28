"""Tools: physis gateway — the single access point to computer/internet/AI.

The wearable (one button + voice/photo, docs/43) issues one MSG_CMD; the
phone/app fulfils it HERE: terminal (computer), web (internet), brain/vision/
model (AI). Memory goes through `brain.physis_next` (physis-next MCP over
HTTP — the retired physis-pro CLI this tool used to shell out to is gone);
the local tools stay the fallback so the gateway works offline too.
Offline-safe: no physis-next server / no session => honest stub strings.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from ..loop import Tool

# physis-next ships one binary: `physis` (apps/physis-cli). Release build is
# what the MCP config points at; debug is the fallback for a dev box.
_PHYSIS_BIN = os.environ.get(
    "PHYSIS_BIN", "/home/gio/dev/physis-next/target/release/physis"
)


def _physis_cli(args: list[str], timeout: int = 20) -> str | None:
    """Run the physis-next CLI, return stdout or None when unavailable.

    Used for the read-only legs (search/context) that need no running server:
    `physis search <q> --path <root>` works straight off the observation log.
    """
    binary = _PHYSIS_BIN
    if not os.path.exists(binary):
        binary = shutil.which("physis") or ""
        if not binary:
            return None
    try:
        proc = subprocess.run(
            [binary, *args], capture_output=True, text=True, timeout=timeout
        )
        out = (proc.stdout or "").strip()
        return out if out else None
    except Exception:
        return None


def recall(text: str) -> str | None:
    """Memory recall via physis-next: MCP search first, CLI search second.

    Returns None when neither path is available (caller prints the honest
    offline stub). Never raises — the gateway must not break a turn.
    """
    from brain import physis_next as px

    try:
        hits = px.search(text or "cyclops", limit=8)
    except px.PhysisNextUnavailable:
        hits = []
    if hits:
        lines = []
        for h in hits[:8]:
            if isinstance(h, dict):
                lines.append(f"{h.get('score', 0):.2f} {h.get('entity_id', '')} "
                             f"{h.get('snippet', '')}".strip())
            else:
                lines.append(str(h))
        return "\n".join(lines)
    root = px.root() or os.getcwd()
    return _physis_cli(["search", text or "cyclops", "--path", root])


def make_physis_tool(config=None, session=None) -> Tool:
    def run(args: dict) -> str:
        action = args.get("action", "ask")
        text = args.get("text", "")
        if action == "remember":
            verdict = str(args.get("outcome", args.get("verdict", "unverified")))
            from brain import physis_next as px

            try:
                px.remember(text, outcome=verdict, actor="cyclops-agent")
            except px.PhysisNextUnavailable as e:
                return (f"offline: physis-next unavailable ({e}) — "
                        f"nothing remembered")
            return f"physis-next: remembered ({verdict})"
        if action == "recall":
            out = recall(text)
            return "offline: physis-next unavailable (no recall)" if out is None else out
        if action == "computer":
            # computer access = terminal tool path (confirm-gated there)
            from .terminal import make_terminal_tool

            cmd = text or args.get("command", "")
            return make_terminal_tool(config, confirm=None).run(
                {"command": cmd} if cmd else {}
            )
        if action == "internet":
            from .web import make_web_tool

            t = make_web_tool(config, session=session)
            if args.get("url"):
                return t.run({"action": "fetch", "url": args["url"]})
            return t.run({"action": "search", "query": text})
        # default: ask — recall physis memory, caller (agent) reasons over it
        mem = recall(text) if text else None
        if mem:
            return f"physis memory:\n{mem[:2000]}"
        return f"offline: physis gateway ask('{text}') — no local memory hit"

    return Tool(
        name="physis",
        description=(
            "Single access point to computer/internet/AI via physis-next. "
            "actions: ask|remember|recall|computer|internet."
        ),
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["ask", "remember", "recall", "computer", "internet"],
                },
                "text": {"type": "string"},
                "outcome": {"type": "string"},
                "verdict": {"type": "string"},
                "command": {"type": "string"},
                "url": {"type": "string"},
            },
        },
        run=run,
    )

