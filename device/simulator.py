"""Host simulator for the XIAO device: drives the C++ UI via ctypes-free
Python reimplementation to validate input -> display flow without a compiler.

For the real firmware, see src/device.cpp (compiled by PlatformIO). This module
is a behavioral twin used by the demo and to test input mapping headlessly.
"""

from __future__ import annotations


class DeviceSim:
    MAX_NOTES = 8
    COLS = 22
    ROWS = 4

    def __init__(self):
        self.notes = []
        self.sel = 0
        self.view_top = 0
        self.recording = False
        self.screen_on = True

    def add_note(self, text):
        if len(self.notes) >= self.MAX_NOTES:
            self.notes.pop(0)
        self.notes.append(text[: self.COLS])

    def wheel(self, delta):
        if delta > 0 and self.sel < len(self.notes) - 1:
            self.sel += 1
        elif delta < 0 and self.sel > 0:
            self.sel -= 1
        if self.sel < self.view_top:
            self.view_top = self.sel
        if self.sel > self.view_top + 2:
            self.view_top = self.sel - 2

    def btn_a(self):
        self.recording = not self.recording

    def btn_b(self):
        self.screen_on = not self.screen_on

    def gesture(self, name):
        if name == "nod":
            self.recording = not self.recording
        elif name == "shake":
            self.screen_on = False

    def screen(self) -> list[str]:
        if not self.screen_on:
            return ["<off>"]
        out = [(("[REC] " if self.recording else "") + f"notes:{len(self.notes)}")]
        for i in range(3):
            idx = self.view_top + i
            if idx < len(self.notes):
                mark = ">" if idx == self.sel else " "
                out.append(f"{mark}{idx + 1} {self.notes[idx]}")
        return out
