"""MCP JSON-RPC server over stdio for Cyclops note store.

Exposes note-oriented tools as an MCP server. Transport is stdio with
line-delimited JSON-RPC 2.0. Zero external dependencies.

Gate (CY-001):
  python3 tests/run_tests.py tests/test_brain.py tests/test_mcp_server.py
"""

from __future__ import annotations

import json
import sys
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional


# --- Note model (mirrors brain/extractor.Note) ---

NOTE_TYPES = ("task", "reminder", "decision", "idea", "summary")


@dataclass
class Note:
    id: str
    type: str
    text: str
    created: str = ""
    due: Optional[str] = None
    source: str = "audio"
    confidence: float = 1.0
    candidate: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.candidate:
            d.pop("candidate", None)
            d.pop("confidence", None)
        return d


# --- Persistent note store (mirrors brain.store.NoteStore) ---

class NoteStore:
    def __init__(self, path: str = "", max_notes: int = 0):
        # Allow env var to override store path (for test integration)
        env_path = os.environ.get("CYCLOPS_NOTES_PATH")
        if env_path:
            path = env_path
        if path:
            self.path = os.path.expanduser(path)
        else:
            self.path = os.path.expanduser("~/.cyclops/notes.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.notes: list[Note] = []
        self.max_notes = max_notes
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
                    self.notes.append(Note(**json.loads(line)))
                except Exception:
                    pass
        self._trim()

    def _trim(self):
        if self.max_notes > 0 and len(self.notes) > self.max_notes:
            self.notes = self.notes[-self.max_notes:]

    def add(self, note: Note) -> Note:
        self.notes.append(note)
        self._trim()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(note.to_dict()) + "\n")
        return note

    def add_many(self, notes: list[Note]) -> list[Note]:
        for n in notes:
            self.add(n)
        return notes


# --- MCP JSON-RPC handler ---

class MCPHandler:
    """Handle MCP JSON-RPC requests over stdio."""

    def __init__(self, store: NoteStore | None = None) -> None:
        self.store = store or NoteStore()
        self.request_id: int = 0

    # ------------------------------------------------------------------
    # Response sending
    # ------------------------------------------------------------------

    def _resp(self, id: Any, result: Any = None, error: Any = None) -> None:
        """Send a single JSON-RPC 2.0 response line."""
        obj: dict[str, Any] = {"jsonrpc": "2.0", "id": id}
        if error is not None:
            obj["error"] = error
        else:
            obj["result"] = result
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    def _err(self, id: Any, code: int, message: str) -> None:
        self._resp(id, error={"code": code, "message": message})

    # ------------------------------------------------------------------
    # MCP tool: search_notes
    # ------------------------------------------------------------------

    def _handle_search_notes(self, params: dict[str, Any], id: Any) -> None:
        """Search notes by kind, confidence, max_age_days, or text substring."""
        kind: str | None = params.get("kind")
        min_confidence: float | None = params.get("min_confidence")
        max_age_days: int | None = params.get("max_age_days")
        substring: str | None = params.get("substring")

        notes = self.store.notes

        if kind is not None and kind not in NOTE_TYPES:
            self._err(id, -32602, f"Invalid kind: {kind}; must be one of {NOTE_TYPES}")
            return

        filtered = list(notes)
        if kind is not None:
            filtered = [n for n in filtered if n.type == kind]

        if min_confidence is not None:
            filtered = [n for n in filtered if n.confidence >= min_confidence]

        if max_age_days is not None:
            cutoff = date.today() - timedelta(days=max_age_days)
            filtered = [
                n for n in filtered
                if n.created
                and try_parse_date(n.created) >= cutoff
            ]

        if substring is not None:
            filtered = [n for n in filtered if substring.lower() in n.text.lower()]

        self._resp(id, [n.to_dict() for n in filtered])

    # ------------------------------------------------------------------
    # MCP tool: today
    # ------------------------------------------------------------------

    def _handle_today(self, params: dict[str, Any], id: Any) -> None:
        """Return notes created or due today."""
        kind: str | None = params.get("kind")

        today_str = date.today().isoformat()

        if kind is not None and kind not in NOTE_TYPES:
            self._err(id, -32602, f"Invalid kind: {kind}; must be one of {NOTE_TYPES}")
            return

        filtered = [
            n for n in self.store.notes
            if n.created == today_str or n.due == today_str
        ]

        if kind is not None:
            filtered = [n for n in filtered if n.type == kind]

        self._resp(id, [n.to_dict() for n in filtered])

    # ------------------------------------------------------------------
    # MCP tool: reminders_due
    # ------------------------------------------------------------------

    def _handle_reminders_due(self, params: dict[str, Any], id: Any) -> None:
        """Return notes with due dates within the next N days."""
        n_days: int = params.get("n_days", 7)

        end = date.today() + timedelta(days=n_days)

        filtered = [n for n in self.store.notes if n.due is not None]
        filtered = [
            n for n in filtered
            if try_parse_date(n.due) <= end
        ]

        self._resp(id, [n.to_dict() for n in filtered])

    # ------------------------------------------------------------------
    # MCP tool: by_kind
    # ------------------------------------------------------------------

    def _handle_by_kind(self, params: dict[str, Any], id: Any) -> None:
        """Group notes by type, returning counts and items."""
        groups: dict[str, list[dict[str, Any]]] = {t: [] for t in NOTE_TYPES}

        for n in self.store.notes:
            groups[n.type].append(n.to_dict())

        counts = {t: len(groups[t]) for t in NOTE_TYPES}

        self._resp(id, {"counts": counts, "groups": groups})

    # ------------------------------------------------------------------
    # Main: read JSON-RPC from stdin, dispatch, write responses
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Read JSON-RPC requests from stdin, dispatch, write responses."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError:
                continue

            method = req.get("method")
            id_val = req.get("id")
            params = req.get("params", {})

            handler_map = {
                "search_notes": self._handle_search_notes,
                "today": self._handle_today,
                "reminders_due": self._handle_reminders_due,
                "by_kind": self._handle_by_kind,
            }

            handler = handler_map.get(method)
            if handler is None:
                self._err(id_val, -32601, f"Method not found: {method}")
                continue

            try:
                handler(params, id_val)
            except Exception as e:
                self._err(id_val, -32000, str(e))


# --- Helper: parse date string safely ---

def try_parse_date(s: str) -> date:
    """Parse YYYY-MM-DD date string; return a very early date on failure."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return date.min


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    """Entry point: create handler and start the MCP event loop."""
    handler = MCPHandler()
    handler.run()


if __name__ == "__main__":
    main()