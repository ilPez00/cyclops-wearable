"""Event ledger (docs/34 Phase 1a) — one append-only stream for "what happened".

Why: notes, sightings, experiences, claims and health samples each keep their own
shape, so "what was going on while X" is a join nobody performs. The shared
primitive is:

    Event{ts, duration, source, kind, body, locator}

`duration_s` is mandatory -- it is the field every re-implementation drops, and
it turns "while X" from a join into a query. `locator` keeps provenance IN the
primitive (which store/file the row came from), so a merged timeline never
loses where a row was born.

Discipline (docs/34 §1b): the ledger sits BESIDE the existing stores. A writer
appends an Event *in addition to* what it already wrote; old readers keep
working; nothing is put in the write path. Stdlib only, offline by default.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

def default_path() -> str:
    """Ledger location, resolved at CALL time (not import time).

    Same reason as everywhere else in brain/: a test or a profile switch that
    changes HOME must isolate the ledger instead of appending to the real one.
    """
    return os.path.join(os.path.expanduser("~/.cyclops"), "events.jsonl")


DEFAULT_PATH = os.path.expanduser("~/.cyclops/events.jsonl")  # reference only


def utc_now() -> str:
    """ISO-8601 UTC, seconds resolution ('2026-09-28T10:12:03Z').

    Second resolution is deliberate: the ledger is compared and sorted as
    strings, so every writer must produce the same shape.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seconds_since(ts: str, now: str | None = None) -> float:
    """Whole seconds from an ISO-8601 UTC stamp to `now` (0.0 if unparseable).

    Used for durations between two edges (e.g. presence on -> off): the ledger
    stores how long a state lasted, not just when it flipped.
    """
    try:
        a = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return 0.0
    if now:
        try:
            b = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except ValueError:
            b = datetime.now(timezone.utc)
    else:
        b = datetime.now(timezone.utc)
    return max(0.0, (b - a).total_seconds())


@dataclass
class Event:
    """One observation. `body` is text only -- raw media never enters the ledger."""

    kind: str                  # note | voice | photo | presence | posture | act | hud
    body: str = ""
    duration_s: float = 0.0    # seconds this state/action lasted (mandatory field)
    source: str = "brain"      # who observed it: brain | wearable | app | ring
    locator: str = ""          # provenance: "notes.jsonl#<id>", "ble:status", ...
    ts: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(
            kind=str(d.get("kind", "")),
            body=str(d.get("body", "")),
            duration_s=float(d.get("duration_s", 0.0) or 0.0),
            source=str(d.get("source", "brain")),
            locator=str(d.get("locator", "")),
            ts=str(d.get("ts") or utc_now()),
        )


class EventLog:
    """Append-only JSONL of Events, newest last on disk (same convention as
    brain.store.NoteStore: load tolerantly, append one line per write)."""

    def __init__(self, path: str | None = None):
        self.path = os.path.expanduser(path or default_path())
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.events: list[Event] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    self.events.append(Event.from_dict(json.loads(line)))
                except Exception:
                    pass  # one corrupt row must not hide the whole ledger

    def append(self, kind: str, body: str = "", duration_s: float = 0.0,
               source: str = "brain", locator: str = "", ts: str | None = None,
               persist: bool = True) -> Event:
        ev = Event(kind=kind, body=body, duration_s=float(duration_s or 0.0),
                   source=source, locator=locator, ts=ts or utc_now())
        self.events.append(ev)
        if persist:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev.to_dict()) + "\n")
        return ev

    def all(self) -> list[Event]:
        return list(self.events)

    def recent(self, limit: int = 50) -> list[Event]:
        """Newest first. Ties keep insertion order (stable sort)."""
        n = max(0, int(limit))
        return sorted(self.events, key=lambda e: e.ts, reverse=True)[:n]

    def by_kind(self, kind: str, limit: int = 50) -> list[Event]:
        return [e for e in self.recent(limit) if e.kind == kind]

    def search(self, query: str, limit: int = 20) -> list[Event]:
        """Case-insensitive substring over body/kind/source (no model, no index:
        the ledger is small and honesty beats ranking here)."""
        q = (query or "").strip().lower()
        if not q:
            return self.recent(limit)
        out = []
        for e in self.recent(0) or self.all():
            hay = " ".join((e.body, e.kind, e.source)).lower()
            if q in hay:
                out.append(e)
        return out[:limit]

    def count(self) -> int:
        return len(self.events)
