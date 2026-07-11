"""Desktop HUD simulator (P0-A) — exercise the Cyclops wearable UX with no
hardware. Decodes the EXACT wire frames the firmware emits:

  * DISPLAY_CMD  (MSG 6)  -> JSON {"kind":"text"/"progress"/"step", ...}
  * HUD_FRAME    (MSG 14) -> tagged text "K<kind>\\nL<line>\\nM<0|1>"
                          (see brain/protocol_v2.parse_hud)

and renders a glanceable terminal grid. Run standalone for a live demo, or
import `HudSim` to drive it from tests / a UDP frame source.

This is the anti-D1/D5 control: the HUD state machine lives in C firmware and
can't run here, but its *wire contract* can — so the UX is verifiable on any
laptop. See docs/31-repremortem-competition.md.
"""

from __future__ import annotations

import json
import sys

try:
    from brain.protocol_v2 import HUD_KINDS, parse_hud
except Exception:  # allow running from repo root or shells/ without package
    import os

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from brain.protocol_v2 import HUD_KINDS, parse_hud


# HUD_KINDS indices (must match firmware/protocol_v2.py)
_KIND_NAMES = {i: n for i, n in enumerate(HUD_KINDS)} if HUD_KINDS else {}


# Panel profiles. Mirrors the firmware Screen drivers (screens.h) so the
# laptop simulator renders the SAME grid geometry as the real panel.
#   legacy  = 21x4  (128x32/64 OLED style, the original glanceable grid)
#   128x128 = 21x16 (ST7735 RGB565 TFT — the default XIAO S3 Sense target)
#   g2      = 18x4  (EvenRealities G2 4x18 green microLED)
PROFILES = {
    "legacy": (21, 4),
    "128x128": (21, 16),
    "g2": (18, 4),
}


class HudSim:
    def __init__(self, cols: int = 21, rows: int = 4, profile: str = "legacy"):
        if profile in PROFILES:
            cols, rows = PROFILES[profile]
        self.profile = profile
        self.cols = cols
        self.rows = rows
        self.mode = "HOME"
        self.lines: list[str] = []
        self.progress: int | None = None
        self.steps: list[str] = []
        self.toast: str | None = None
        self.hr: int | None = None
        self.spo2: int | None = None
        self.batt: int | None = None
        self.rec: bool = False
        self.consent: bool = True

    # ---- ingest the two real wire formats ----
    def feed_display_cmd(self, payload: bytes):
        try:
            obj = json.loads(payload.decode(errors="replace"))
        except Exception:
            return
        kind = obj.get("kind")
        if kind == "progress":
            self.progress = int(obj.get("p", 0))
        elif kind == "step":
            tool = obj.get("tool", "?")
            if tool not in self.steps:
                self.steps.append(tool)
        elif kind == "text":
            text = obj.get("text") or obj.get("data") or ""
            self.lines = self._wrap(text, self.cols)

    def feed_hud_frame(self, payload: bytes):
        d = parse_hud(payload)
        kind = d.get("kind")
        self.mode = _KIND_NAMES.get(kind, str(kind))
        lines = d.get("lines", [])
        if lines:
            self.lines = [ln[: self.cols] for ln in lines][: self.rows - 1]

    # ---- helpers ----
    @staticmethod
    def _wrap(text: str, cols: int = 21) -> list[str]:
        out = []
        for para in text.split("\n"):
            while para:
                out.append(para[:cols])
                para = para[cols:]
        return out[:3]

    def set_health(self, hr=None, spo2=None, batt=None):
        if hr is not None:
            self.hr = hr
        if spo2 is not None:
            self.spo2 = spo2
        if batt is not None:
            self.batt = batt

    def set_rec(self, on: bool):
        self.rec = on

    def set_consent(self, on: bool):
        self.consent = on

    # ---- render ----
    def render(self) -> list[str]:
        grid = []
        # status bar (row 0)
        flags = []
        if self.hr is not None:
            flags.append(f"HR{self.hr}")
        if self.spo2 is not None:
            flags.append(f"S{self.spo2}%")
        if self.batt is not None:
            flags.append(f"B{self.batt}%")
        status = f"[{self.mode}] " + " ".join(flags)
        if self.rec:
            status += " REC"
        if not self.consent:
            status += " X"
        grid.append(status[: self.cols].ljust(self.cols))
        # body lines (rows 1..rows-2)
        for i in range(self.rows - 2):
            grid.append((self.lines[i] if i < len(self.lines) else "").ljust(self.cols))
        # progress / step footer (last row)
        foot = ""
        if self.progress is not None:
            foot = f"[{self.progress:3d}%]"
        if self.steps:
            foot += " " + ">".join(self.steps)
        if self.toast:
            foot = self.toast
        grid.append(foot[: self.cols].ljust(self.cols))
        return grid

    def to_g2(self) -> list[bytes]:
        """Render this HUD model as EvenRealities G2 BLE packets (P0-C)."""
        from device.g2_layout import render_to_g2

        return render_to_g2(
            self.mode, self.lines, self.progress, self.hr, self.spo2, self.batt
        )

    def __str__(self):
        return "\n".join(self.render())


def demo(profile: str = "legacy"):
    sim = HudSim(profile=profile)
    # 1) agent answer arrives as a HUD_FRAME (Omi/G2 style)
    from brain.protocol_v2 import build_hud

    sim.feed_hud_frame(
        build_hud(
            HUD_KINDS.index("agent"),
            ["Meet Bob at 3pm"[: sim.cols], "bring the cable"[: sim.cols]],
            more=False,
        )
    )
    sim.set_health(hr=72, spo2=97, batt=80)
    print(f"--- after agent frame ({sim.profile} {sim.cols}x{sim.rows}) ---")
    print(sim)
    # 2) agent streams progress + steps as DISPLAY_CMD
    sim.feed_display_cmd(b'{"kind":"progress","p":42}')
    sim.feed_display_cmd(b'{"kind":"step","tool":"device"}')
    sim.feed_display_cmd(b'{"kind":"step","tool":"web"}')
    print("--- after progress/step ---")
    print(sim)
    # 3) a note as DISPLAY_CMD text
    sim.feed_display_cmd(b'{"kind":"text","text":"idea: wire ring HR to HUD"}')
    print("--- after note ---")
    print(sim)


def demo_128x128():
    demo(profile="128x128")


if __name__ == "__main__":
    import sys

    demo(profile=sys.argv[1] if len(sys.argv) > 1 else "legacy")
