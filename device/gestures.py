"""Gyroscope gesture detection from raw accel streams (host-simulated).

Detects nod (pitch oscillation) and shake (lateral oscillation) from a simple
peak/zero-crossing heuristic. On real HW feed MPU6886/BMX055 samples here.
"""
from __future__ import annotations

class GestureDetector:
    def __init__(self, threshold=0.6, min_crossings=2, window=20):
        self.threshold = threshold
        self.min_crossings = min_crossings
        self.window = window
        self.buf = []
        self.last_dir = 0
    def push(self, x: float, y: float, z: float) -> str | None:
        # use magnitude of pitch-ish axis (y) and lateral (x)
        mag = abs(y) + abs(x) * 0.5
        self.buf.append(mag)
        if len(self.buf) > self.window: self.buf.pop(0)
        if len(self.buf) < 4: return None
        # count direction changes above threshold around the mean
        mean = sum(self.buf) / len(self.buf)
        crossings = 0
        prev = 0
        for v in self.buf:
            d = 1 if (v - mean) > self.threshold else (-1 if (v - mean) < -self.threshold else 0)
            if d != 0 and prev != 0 and d != prev: crossings += 1
            if d != 0: prev = d
        if crossings >= self.min_crossings:
            self.buf.clear()
            # shake if lateral dominates, else nod
            return "shake" if abs(x) > abs(y) else "nod"
        return None
