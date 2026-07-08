"""Tool: clipboard — get/set (OS-aware, safe offline stub).

On Linux uses xclip/wl-paste; elsewhere returns a stored value so the agent
still works headless. Never crashes if no clipboard backend exists.
"""
from __future__ import annotations
import os, shutil, subprocess
from ..loop import Tool
from ..config import AgentConfig

_STORE = os.path.join(os.path.expanduser("~/cyclops_data"), "clipboard.txt")


def make_clipboard_tool(config: AgentConfig) -> Tool:
    def _get() -> str:
        if shutil.which("xclip"):
            try:
                return subprocess.run(["xclip", "-o", "-selection", "clipboard"],
                                      capture_output=True, text=True, timeout=5).stdout.strip()
            except Exception:
                pass
        if os.path.exists(_STORE):
            return open(_STORE, encoding="utf-8").read().strip()
        return "(clipboard empty)"

    def _set(text: str) -> str:
        os.makedirs(os.path.dirname(_STORE), exist_ok=True)
        open(_STORE, "w", encoding="utf-8").write(text)
        if shutil.which("xclip"):
            try:
                subprocess.run(["xclip", "-selection", "clipboard"], input=text,
                               capture_output=True, text=True, timeout=5)
            except Exception:
                pass
        return f"clipboard set ({len(text)} chars)"

    def run(args: dict) -> str:
        a = args.get("action", "get")
        if a == "get":
            return _get()
        if a == "set":
            return _set(args.get("text", ""))
        return "unknown clipboard action"

    return Tool(
        name="clipboard",
        description="Read or write the system clipboard.",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["get", "set"]},
                "text": {"type": "string"},
            },
            "required": ["action"],
        },
        run=run,
    )
