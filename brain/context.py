"""Multi-source context fusion (P2-B).

Assembles one context block for the agent from the body signals Cyclops owns:
  * notes      (extracted tasks/reminders/decisions from audio/transcript)
  * health     (fused ring + omi + g2 vitals via health_fuse.HealthAggregator)
  * calendar   (upcoming events from an offline JSONL file, no deps)

Offline-first and dependency-free; the calendar source is a JSONL path
(one event per line: {"title","start","loc"}) or an in-memory list.
"""

from __future__ import annotations

import json
import os


class ContextAssembler:
    def __init__(self):
        self._notes = []
        self._health = None  # HealthAggregator
        self._calendar = []  # list of event dicts

    # -- inputs ------------------------------------------------------------
    def add_notes(self, notes) -> "ContextAssembler":
        self._notes = list(notes)
        return self

    def set_health(self, aggregator) -> "ContextAssembler":
        self._health = aggregator
        return self

    def load_calendar(self, path: str) -> "ContextAssembler":
        """Read upcoming events from a JSONL file (one JSON object per line)."""
        self._calendar_path = path
        self._calendar = []
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        self._calendar.append(json.loads(ln))
                    except Exception:
                        pass
        return self

    def set_calendar(self, events: list) -> "ContextAssembler":
        self._calendar = list(events)
        return self

    # -- assembly ----------------------------------------------------------
    def build(self) -> dict:
        health = self._health.snapshot() if self._health else {}
        upcoming = sorted(self._calendar, key=lambda e: e.get("start", ""))[:5]
        return {
            "notes": [n.to_dict() if hasattr(n, "to_dict") else n for n in self._notes],
            "health": health,
            "calendar": upcoming,
        }

    def render(self) -> str:
        """Human/agent-readable fused context (compact, one section per source)."""
        d = self.build()
        lines = []
        if d["health"]:
            h = d["health"]
            vit = ", ".join(
                f"{k}={v}"
                for k, v in (
                    ("hr", h.get("hr")),
                    ("spo2", h.get("spo2")),
                    ("batt", h.get("batt")),
                )
                if v
            )
            if vit:
                lines.append(f"[health] {vit}")
        if d["calendar"]:
            cal = "; ".join(
                f"{e.get('title', '?')}@{e.get('start', '?')}" for e in d["calendar"]
            )
            lines.append(f"[calendar] {cal}")
        if d["notes"]:
            nt = "; ".join(
                f"{n.get('type', 'note')}: {n.get('text', '')}" for n in d["notes"][-5:]
            )
            lines.append(f"[notes] {nt}")
        return "\n".join(lines) if lines else "[context] empty"
