"""Physis note sink — mirror Cyclops notes into a physis semantic store.

Sends notes via HTTP POST to a physis server. Opt-in via env var
CYCLOPS_PHYSIS_URL. Fails soft: if the server is unreachable, notes are
stored locally in a retry queue and sent later.

Gate (CY-002):
  python3 tests/run_tests.py tests/test_brain.py tests/test_physis_sink.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from brain.store import NoteStore
from brain.extractor import Note, NOTE_TYPES


# --- Configuration ---

PHYSIS_URL = os.environ.get("CYCLOPS_PHYSIS_URL")

# Local retry store: notes that failed to send are queued here
RETRY_STORE_PATH = os.path.expanduser("~/.cyclops/physis_retry.jsonl")
MAX_RETRIES = 3  # give up after N failed attempts
RETRY_INTERVAL_SECONDS = 60  # how often to attempt retry


# --- Physis API types ---

@dataclass
class PhiseNotePayload:
    """Payload sent to the physis HTTP API."""
    id: str
    type: str
    text: str
    created: str
    due: Optional[str] = None
    source: str = "audio"
    kind: Optional[str] = None  # task, reminder, decision, idea
    device: Optional[str] = None  # identifier of the sending device

    def to_json(self) -> str:
        d = {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "created": self.created,
        }
        if self.due is not None:
            d["due"] = self.due
        if self.source is not None:
            d["source"] = self.source
        if self.kind is not None:
            d["kind"] = self.kind
        if self.device is not None:
            d["device"] = self.device
        return json.dumps(d)


# --- Physis sink ---

class PhysisSink:
    """Sink that posts notes to a physis server over HTTP."""

    def __init__(self, url: str | None = None, retry: bool = True) -> None:
        self.url = url or PHYSIS_URL
        self.retry = retry
        self.local_store: NoteStore | None = None

        # If URL is configured, set up a local retry store
        if self.url:
            os.makedirs(os.path.dirname(RETRY_STORE_PATH), exist_ok=True)
            self.local_store = NoteStore(RETRY_STORE_PATH)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send(self, note: Note) -> bool:
        """Send a single note to physis.

        Returns True if sent (or accepted as sent), False if failed and
        retried/queued locally.
        """
        if not self.url:
            # No physis URL configured — local-only mode, mark as "sent"
            # so the capture pipeline doesn't block. In a real deployment
            # the user would set CYCLOPS_PHYSIS_URL.
            return True

        payload = PhiseNotePayload(
            id=note.id,
            type=note.type,
            text=note.text,
            created=note.created or "",
            due=note.due,
            source=note.source,
            kind=note.type,  # note.type is one of NOTE_TYPES
            device=os.environ.get("CYCLOPS_DEVICE_ID"),
        )

        data = payload.to_json().encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                # Accept any 2xx response as success
                return resp.status >= 200 and resp.status < 300
        except urllib.error.HTTPError as e:
            # Even 4xx/5xx from physis are treated as failures for retry
            body = e.read().decode() if e.fp else "no body"
            print(f"Physis HTTP error {e.code}: {body[:200]}")
            return self._queue_for_retry(note, e)
        except (urllib.error.URLError, OSError, TimeoutError) as e:
            print(f"Physis connection error: {e}")
            return self._queue_for_retry(note, e)

    def _queue_for_retry(self, note: Note, error: Exception) -> bool:
        """Queue a note for local retry later."""
        if self.local_store is None:
            # No local store available; drop the note but don't crash
            print("Physis sink: no local retry store; note dropped")
            return False

        note.acknowledged = False  # type: ignore[attr-defined]
        note.attempt_count = getattr(note, "attempt_count", 0) + 1  # type: ignore[attr-defined]

        try:
            self.local_store.add(note)  # type: ignore[arg-type]
            print(f"Physis sink: queued note {note.id} for retry (attempt {note.attempt_count})")
            return False
        except Exception as qe:
            print(f"Physis sink: failed to queue note: {qe}")
            return False

    def process_retry_queue(self) -> int:
        """Attempt to resend any notes in the local retry queue.

        Returns the number of notes successfully sent on this run.
        """
        if self.local_store is None:
            return 0

        sent = 0
        notes = list(self.local_store.notes)

        for note in notes:
            # Skip notes that have exceeded max retries
            attempt_count = getattr(note, "attempt_count", 1)
            if attempt_count >= MAX_RETRIES:
                print(f"Physis sink: note {note.id} exceeded max retries; discarding")
                try:
                    self.local_store.notes.remove(note)  # type: ignore[attr-type]
                except ValueError:
                    pass
                continue

            success = self.send(note)
            if success:
                # Remove from retry store on success
                try:
                    self.local_store.notes.remove(note)  # type: ignore[attr-type]
                    sent += 1
                except ValueError:
                    pass

        if sent > 0:
            print(f"Physis sink: sent {sent} notes from retry queue")
        return sent


# ------------------------------------------------------------------
# Convenience: capture-side helper
# ------------------------------------------------------------------

def capture_note(note: Note, sink: PhysisSink | None = None) -> bool:
    """Send a note through the sink; returns True if accept (even if local)."""
    sink = sink or (_detect_sink())
    return sink.send(note)


def _detect_sink() -> PhysisSink:
    """Create a PhysisSink if CYCLOPS_PHYSIS_URL is set."""
    url = os.environ.get("CYCLOPS_PHYSIS_URL")
    if url:
        return PhysisSink(url=url)
    # Return a no-op sink that always "succeeds" so capture isn't blocked
    return PhysisSink(url=None, retry=False)


# ------------------------------------------------------------------
# Module entry point (optional: useful as script)
# ------------------------------------------------------------------

def main() -> None:
    """Process the retry queue (e.g., from a cron job or systemd timer)."""
    url = os.environ.get("CYCLOPS_PHYSIS_URL")
    if not url:
        print("CYCLOPS_PHYSIS_URL not set; nothing to do")
        return

    sink = PhysisSink(url=url)
    sent = sink.process_retry_queue()
    if sent == 0:
        print("No notes sent from retry queue")


if __name__ == "__main__":
    main()