"""Entity store — a deduplicated registry of things Cyclops has seen.

AURA EntityStore port. Cyclops has freeform memory cards and vision, but no
structured, queryable registry of people/places/things with recurrence counts
and associations. touch() is the key op: upsert-and-increment, so seeing the
same entity again bumps its seen_count and last_seen instead of duplicating.

JSONL-persisted under ~/.cyclops/ (NoteStore pattern). Zero-dep, offline.
"""

from __future__ import annotations

import json
import os
import threading
import time


def _norm(name: str) -> str:
    return " ".join((name or "").strip().split()).lower()


class EntityStore:
    def __init__(self, path: str = "~/.cyclops/entities.jsonl"):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()

    def _load(self) -> dict[str, dict]:
        by: dict[str, dict] = {}
        if not os.path.exists(self.path):
            return by
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                by[r.get("key", "")] = r  # last write wins on the same key
        return by

    def _dump(self, by: dict[str, dict]) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in by.values():
                f.write(json.dumps(r) + "\n")
        os.replace(tmp, self.path)

    def touch(self, name: str, etype: str = "thing", note: str = "") -> dict:
        """Upsert: create the entity or bump its seen_count + last_seen.
        Returns the current record."""
        key = _norm(name)
        if not key:
            return {}
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        with self._lock:
            by = self._load()
            r = by.get(key)
            if r is None:
                r = {
                    "key": key,
                    "name": name.strip(),
                    "type": etype,
                    "seen_count": 1,
                    "first_seen": now,
                    "last_seen": now,
                    "notes": [note] if note else [],
                }
            else:
                r["seen_count"] = int(r.get("seen_count", 0)) + 1
                r["last_seen"] = now
                if etype and etype != "thing":
                    r["type"] = etype
                if note and note not in r.get("notes", []):
                    r.setdefault("notes", []).append(note)
                    r["notes"] = r["notes"][-10:]
            by[key] = r
            self._dump(by)
            return dict(r)

    def all(self, etype: str = "") -> list[dict]:
        rows = list(self._load().values())
        if etype:
            rows = [r for r in rows if r.get("type") == etype]
        rows.sort(key=lambda r: (r.get("seen_count", 0), r.get("last_seen", "")), reverse=True)
        return rows

    def search(self, query: str) -> list[dict]:
        q = _norm(query)
        if not q:
            return self.all()
        return [
            r for r in self.all()
            if q in r.get("key", "") or any(q in _norm(n) for n in r.get("notes", []))
        ]

    def types(self) -> dict:
        counts: dict[str, int] = {}
        for r in self._load().values():
            counts[r.get("type", "thing")] = counts.get(r.get("type", "thing"), 0) + 1
        return counts


__all__ = ["EntityStore"]
