"""Ring health time-series + join to notes (premortem #3).

Ring samples arrive async with no RTC; phone pushes UTC time-sync. We store
samples in a fixed window and join notes by timestamp neighborhood so we can
answer "what was my heart rate during that meeting?".
"""
from __future__ import annotations

import bisect
import os
from dataclasses import asdict, dataclass


@dataclass
class HealthSample:
    t: int          # utc_ms
    hr: int = 0
    spo2: int = 0
    sleep_stage: int = 0   # 0 awake,1 light,2 deep,3 rem
    batt_mv: int = 0
    def to_dict(self): return asdict(self)

class HealthStore:
    def __init__(self, path: str = "~/.cyclops/health.jsonl"):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.samples: list[HealthSample] = []
        self._load()
    def _load(self):
        if not os.path.exists(self.path): return
        for line in open(self.path, encoding="utf-8"):
            line=line.strip()
            if not line: continue
            try:
                d=eval(line); self.samples.append(HealthSample(**d))
            except Exception: pass
        self.samples.sort(key=lambda s: s.t)
    def add(self, s: HealthSample):
        bisect.insort(self.samples, s, key=lambda x: x.t)
        with open(self.path,"a",encoding="utf-8") as f: f.write(repr(asdict(s))+"\n")
    def window(self, t_center: int, before_ms: int = 300_000, after_ms: int = 60_000):
        lo = t_center - before_ms; hi = t_center + after_ms
        return [s for s in self.samples if lo <= s.t <= hi]
    def avg_hr_around(self, t_center: int, before_ms=300_000, after_ms=60_000):
        w = self.window(t_center, before_ms, after_ms)
        hrs = [s.hr for s in w if s.hr > 0]
        return sum(hrs)//len(hrs) if hrs else None
    def latest(self) -> HealthSample | None:
        return self.samples[-1] if self.samples else None
