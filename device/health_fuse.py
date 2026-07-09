"""Unified health frame (P1-D) — fuse COLMI R02 + Omi + G2/R1 into one sample.

Cyclops has several body sensors (COLMI R02 ring: HR/SpO2/battery, G2 R1 ring,
Omi pendant). This module fuses their readings into ONE canonical
HEALTH_SAMPLE (see brain.protocol_v2.build_health) so the HUD, agent and logs
have a single source of truth instead of per-device forks (premortem D4 drift).

Fusion policy: last-writer-wins per field, but a reading only overwrites an
existing field if it is newer (higher ts). Battery is tracked per-source (each
device has its own battery) and the ring's battery drives the HEALTH_SAMPLE
`batt` field by convention.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Reading:
    """A single reading from one source. Unset fields stay None."""
    source: str
    ts: int = 0
    hr: int | None = None
    spo2: int | None = None
    sleep_stage: int | None = None
    batt: int | None = None  # this source's own battery %


@dataclass
class HealthAggregator:
    """Merge readings from multiple wearables into one fused sample."""
    hr: int | None = None
    spo2: int | None = None
    sleep_stage: int | None = None
    _ts: dict = field(default_factory=dict)          # field -> newest ts seen
    batteries: dict = field(default_factory=dict)    # source -> batt %
    battery_source: str = "ring"                     # drives fused `batt`

    def update(self, r: Reading) -> None:
        # 0 means "not reported this frame" (mirrors the wearable decoder),
        # so a partial sample never clobbers an existing reading with a zero.
        for f in ("hr", "spo2", "sleep_stage"):
            v = getattr(r, f)
            if v is None or v == 0:
                continue
            if r.ts >= self._ts.get(f, -1):
                setattr(self, f, v)
                self._ts[f] = r.ts
        if r.batt is not None and r.batt > 0:
            self.batteries[r.source] = r.batt

    # -- convenience adapters for the sources we already have ---------------
    def from_colmi(self, hr=None, spo2=None, battery=None, ts=0) -> "HealthAggregator":
        self.update(Reading("ring", ts, hr=hr, spo2=spo2, batt=battery))
        return self

    def from_omi(self, hr=None, ts=0) -> "HealthAggregator":
        self.update(Reading("omi", ts, hr=hr))
        return self

    def from_g2(self, hr=None, spo2=None, battery=None, ts=0) -> "HealthAggregator":
        self.update(Reading("g2", ts, hr=hr, spo2=spo2, batt=battery))
        return self

    @property
    def batt(self) -> int:
        """Battery for the HEALTH_SAMPLE (ring by convention; 0 if unknown)."""
        return self.batteries.get(self.battery_source,
                                  next(iter(self.batteries.values()), 0))

    def to_frame(self, ts: int = 0) -> bytes:
        """Emit the canonical HEALTH_SAMPLE payload (protocol_v2.build_health)."""
        from brain.protocol_v2 import build_health
        return build_health(ts, self.hr or 0, self.spo2 or 0,
                            self.sleep_stage or 0, self.batt)

    def snapshot(self) -> dict:
        return {"hr": self.hr, "spo2": self.spo2,
                "sleep_stage": self.sleep_stage, "batt": self.batt,
                "batteries": dict(self.batteries)}
