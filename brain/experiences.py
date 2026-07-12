"""Experience log — explicit graded self-review (AURA/Praxis PDCA port).

Cyclops's agent/learning.py learns *implicitly* from turns; this adds an
*explicit* signal: the user records an action in a domain with a 0..1 grade
and a note. Per-domain stats (count, avg grade) drive a Plan/Do/Check/Act
state — the substrate for value-learning (ties to Rachmaninov: learn what
the user values from what they grade well).

JSONL-persisted under ~/.cyclops/ following brain/store.py's NoteStore.
Zero-dep, offline.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

GRADE_LABELS = ["fail", "poor", "fair", "good", "great"]


def grade_label(g: float) -> str:
    i = min(len(GRADE_LABELS) - 1, max(0, int(g * len(GRADE_LABELS))))
    return GRADE_LABELS[i]


def pdca_state(avg: float, count: int) -> str:
    """Derive a PDCA phase from average grade (AURA main.rs heuristic)."""
    if count == 0:
        return "Plan"
    if avg < 0.35:
        return "Check"  # underperforming: re-examine
    if avg < 0.6:
        return "Do"  # in progress
    if avg < 0.8:
        return "Act"  # working, tune
    return "Act"  # strong


class ExperienceStore:
    def __init__(self, path: str = "~/.cyclops/experiences.jsonl"):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()

    def record(self, domain: str, action: str, grade: float, note: str = "") -> dict:
        row = {
            "id": uuid.uuid4().hex[:12],
            "domain": (domain or "general").strip(),
            "action": (action or "").strip(),
            "grade": max(0.0, min(1.0, float(grade))),
            "note": (note or "").strip(),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row

    def all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with self._lock, open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
        return out

    def for_domain(self, domain: str) -> list[dict]:
        return [e for e in self.all() if e.get("domain") == domain]

    def domains(self) -> list[dict]:
        """Per-domain rollup: count, avg grade, PDCA state (newest first)."""
        by: dict[str, list[float]] = {}
        last: dict[str, str] = {}
        for e in self.all():
            d = e.get("domain", "general")
            by.setdefault(d, []).append(float(e.get("grade", 0.0)))
            last[d] = e.get("ts", "")
        out = []
        for d, grades in by.items():
            avg = sum(grades) / len(grades) if grades else 0.0
            out.append(
                {
                    "domain": d,
                    "count": len(grades),
                    "avg": round(avg, 3),
                    "grade_label": grade_label(avg),
                    "pdca": pdca_state(avg, len(grades)),
                    "last": last.get(d, ""),
                }
            )
        out.sort(key=lambda x: x["last"], reverse=True)
        return out


__all__ = ["ExperienceStore", "grade_label", "pdca_state", "GRADE_LABELS"]
