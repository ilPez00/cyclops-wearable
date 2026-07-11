"""Display sinks (brain side) for every target (protocol v2).

- LocalScreenSink  : XIAO 128x128 (DISPLAY_CMD JSON frames)
- ArduinoSink      : 128x32 OLED (DISPLAY_CMD, compact text)
- G2GlassesSink    : EvenRealities G2 HUD (HUD_FRAME compact, max 4x18)
- ConsoleSink      : debug
All push via a transport.write(bytes) — USB-serial for Arduino/XIAO, BLE for G2.
"""
from __future__ import annotations

import json

from .protocol import MSG, encode
from .protocol_v2 import HUD_KINDS, MSG_HUD_FRAME, build_hud


class DisplaySink:
    def render(self, note): raise NotImplementedError
    def render_text(self, text): raise NotImplementedError

class ConsoleSink(DisplaySink):
    def render(self, note):
        print(f"[{note.type}] {note.text}" + (f" (due {note.due})" if note.due else ""))
    def render_text(self, text): print(f"> {text}")

class LocalScreenSink(DisplaySink):
    def __init__(self, transport): self.t = transport
    def render(self, note):
        self.t.write(encode(MSG["DISPLAY_CMD"], json.dumps({"kind":"text","data":f"{note.type}: {note.text}"}).encode()))
    def render_text(self, text):
        self.t.write(encode(MSG["DISPLAY_CMD"], json.dumps({"kind":"text","data":text}).encode()))

class ArduinoSink(DisplaySink):
    """128x32 OLED: 4 rows x 21 chars. Same DISPLAY_CMD channel as XIAO."""
    def __init__(self, transport): self.t = transport
    def _send(self, text):
        self.t.write(encode(MSG["DISPLAY_CMD"], json.dumps({"kind":"text","data":text[:21]}).encode()))
    def render(self, note): self._send(f"{note.type[0].upper()}:{note.text[:19]}")
    def render_text(self, text): self._send(text[:21])

class G2GlassesSink(DisplaySink):
    """G2 640x200: strict 4 lines x 18 chars (premortem #4)."""
    MAX = 18
    def __init__(self, transport): self.t = transport
    def _trim(self, s): return s if len(s) <= self.MAX else s[:self.MAX-1] + "\u2026"
    def render(self, note):
        line = self._trim(f"{note.type[0].upper()}:{note.text}")
        self.t.write(build_hud(HUD_KINDS.index("note"), [line], more=False))
    def render_text(self, text):
        self.t.write(build_hud(HUD_KINDS.index("note"), [self._trim(text)], more=False))
    def teleprompter(self, lines):
        # stream one line at a time; phone handles paging
        for i in range(0, len(lines), 4):
            chunk = [self._trim(l) for l in lines[i:i+4]]
            more = (i+4) < len(lines)
            self.t.write(build_hud(HUD_KINDS.index("teleprompter"), chunk, more))
