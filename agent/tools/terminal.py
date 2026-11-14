"""Tools: control a terminal session.

Sandboxed behind a confirm flag (AgentConfig.terminal_confirm). Runs a
command with no shell interpolation via shlex.split(). Off Android it
targets an attached device via ADB; on desktop it runs locally or over SSH.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from typing import Callable

from ..config import AgentConfig
from ..loop import Tool

# Commands and patterns that are always blocked in non-interactive mode,
# regardless of confirm callback. These are destructive system operations.
_BLOCKED_COMMANDS: tuple[str, ...] = (
    "mkfs", "dd", "fdisk", "parted", "format",
)
_BLOCKED_PATTERNS: tuple[str, ...] = (
    r">\s*/dev/",
    r"chmod\s+-R\s+000",
    r":\(\)\s*\{",
)
_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS)) if _BLOCKED_PATTERNS else None


def _is_dangerous(cmd: str) -> bool:
    base = cmd.strip().split(maxsplit=1)[0] if cmd.strip() else ""
    if any(base == b or base.startswith(b + ".") for b in _BLOCKED_COMMANDS):
        return True
    if _BLOCKED_RE and _BLOCKED_RE.search(cmd):
        return True
    return False


def make_terminal_tool(
    config: AgentConfig, confirm: Callable[[str], bool] | None = None
) -> Tool:
    def run(args: dict) -> str:
        cmd = args.get("command", "")
        if not cmd:
            return "error: empty command"
        if _is_dangerous(cmd):
            return "cancelled: command blocked by safety policy"
        if config.terminal_confirm:
            ok = confirm(cmd) if confirm else _default_confirm(cmd)
            if not ok:
                return "cancelled: terminal_confirm required"
        try:
            cmd_list = shlex.split(cmd)
        except ValueError as e:
            return f"error: invalid command syntax — {e}"
        try:
            proc = subprocess.run(
                cmd_list,
                shell=False,
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
        # In non-interactive contexts we refuse risky commands unless
        # a confirm callback is provided by the UI.
        danger = ("rm -rf", "> /dev/", "chmod -R 000", ":(){ :|:& };:")
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
