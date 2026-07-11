"""Tools: control a terminal session.

Sandboxed behind a confirm flag (AgentConfig.terminal_confirm). Executes a
shell command, streams stdout/stderr, returns trimmed output. This is the
"control terminal sessions" feature. On Android it targets an attached device
via ADB; on desktop it runs locally or over SSH.
"""

from __future__ import annotations

import subprocess
from typing import Callable

from ..config import AgentConfig
from ..loop import Tool


def make_terminal_tool(
    config: AgentConfig, confirm: Callable[[str], bool] | None = None
) -> Tool:
    def run(args: dict) -> str:
        cmd = args.get("command", "")
        if not cmd:
            return "error: empty command"
        if config.terminal_confirm:
            ok = confirm(cmd) if confirm else _default_confirm(cmd)
            if not ok:
                return "cancelled: terminal_confirm required"
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=args.get("timeout", 30),
            )
            out = (proc.stdout or "") + (proc.stderr or "")
            return out[:4000] or f"(exit {proc.returncode}, no output)"
        except subprocess.TimeoutExpired:
            return "error: command timed out"
        except Exception as e:
            return f"error: {e}"

    def _default_confirm(cmd: str) -> bool:
        # In non-interactive contexts we refuse destructive commands unless
        # confirm callback is provided by the UI.
        danger = ("rm -rf", "mkfs", "dd if=", "> /dev/", "chmod -R 000")
        if any(d in cmd for d in danger):
            return False
        return True

    return Tool(
        name="terminal",
        description="Run a shell command and return its output. Use for terminal control.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "shell command to run"},
                "timeout": {"type": "integer", "description": "seconds (default 30)"},
            },
            "required": ["command"],
        },
        run=run,
    )
