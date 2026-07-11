"""Tool: screen — capture and (optionally) describe the current screen.

Uses the terminal tool to run a platform screenshot command, then optionally
describes it with the vision tool. On headless/offline it returns a stub. This
is the "see what's on my screen" capability for desktop control.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from ..config import AgentConfig
from ..loop import Tool


def make_screen_tool(config: AgentConfig, vision=None) -> Tool:
    def _shot() -> str:
        # pick a screenshot backend
        if shutil.which("scrot"):
            p = tempfile.mktemp(suffix=".png")
            os.system(f"scrot -o {p}")
            return p if os.path.exists(p) else ""
        if shutil.which("import"):  # imagemagick
            p = tempfile.mktemp(suffix=".png")
            os.system(f"import -window root {p}")
            return p if os.path.exists(p) else ""
        return ""

    def run(args: dict) -> str:
        path = _shot()
        if not path:
            return "offline: no screenshot backend (scrot/import) available"
        if args.get("describe") and vision:
            return vision.run(
                {"image": path, "prompt": "Describe this screen briefly."}
            )
        return f"screenshot saved: {path}"

    return Tool(
        name="screen",
        description="Capture the current screen (and optionally describe it).",
        parameters={
            "type": "object",
            "properties": {"describe": {"type": "boolean"}},
        },
        run=run,
    )
