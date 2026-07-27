"""Tool: screen — capture and (optionally) describe the current screen.

Runs a platform screenshot command, then optionally describes it with the
vision tool. On headless/offline it returns a stub. This is the "see what's on
my screen" capability for desktop control.

Consent: capturing the screen is as invasive as the camera, so it obeys the
same consent_mode switch the camera/capture tools do.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from ..config import AgentConfig
from ..loop import Tool

# (executable, argv template). First one present on PATH wins.
BACKENDS = (
    ("scrot", ["scrot", "-o", "{path}"]),
    ("import", ["import", "-window", "root", "{path}"]),   # imagemagick
    ("grim", ["grim", "{path}"]),                          # wayland
)


def make_screen_tool(config: AgentConfig, vision=None, which=shutil.which) -> Tool:
    """`which` is injectable so tests can exercise the headless path on a box
    that happens to have scrot installed -- the old test asserted "offline"
    and therefore silently screenshotted the developer's desktop instead.
    """

    def _shot() -> str:
        for exe, argv in BACKENDS:
            if not which(exe):
                continue
            # mkstemp, not mktemp: mktemp is deprecated for the race between
            # picking the name and something else creating it.
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            try:
                # list argv, no shell -- the path is ours, but a shell here is
                # a standing invitation the moment anything else feeds it
                subprocess.run([a.format(path=path) for a in argv],
                               capture_output=True, timeout=20, check=False)
            except (OSError, subprocess.SubprocessError):
                _unlink(path)
                continue
            if os.path.exists(path) and os.path.getsize(path) > 0:
                return path
            _unlink(path)  # backend present but produced nothing (headless)
        return ""

    def _unlink(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    def run(args: dict) -> str:
        if not getattr(config, "consent_mode", True):
            return "refused: consent mode is off"
        path = _shot()
        if not path:
            return ("offline: no screenshot backend produced an image "
                    f"(tried {', '.join(e for e, _ in BACKENDS)})")
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
