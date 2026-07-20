"""Telegram sink bridge for Cyclops.

Reuses the same NoteStore + extractor pipeline already used by local HUD /
G2 / web sinks. Inbound messages go through brain.pipeline; outbound notes are
pushed as Telegram messages via Bot API polling or webhook.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from brain.store import NoteStore, Note  # noqa: E402


TGPMINI_DIR = Path(os.environ.get("TGPMINI_DIR", "/home/gio/TGPmini"))
SETTINGS_PATH = TGPMINI_DIR / "settings.json"
STATE_PATH = TGPMINI_DIR / "state.json"


def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return default
    return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


class TelegramSink:
    def __init__(self, store: NoteStore | None = None) -> None:
        self.store = store
        self.settings = _load_json(SETTINGS_PATH, {})
        self.state = _load_json(STATE_PATH, {"offset": 0, "chat_id": None})

    def render_text(self, text: str) -> None:
        # Best-effort: update last outbound payload; real delivery handled by bot.py polling
        self.settings["last_text"] = text
        _save_json(SETTINGS_PATH, self.settings)

    def outbox_push(self, chat_id: int | None, text: str) -> None:
        """Append one outbound message for bot.py to deliver."""
        outbox = _load_json(TGPMINI_DIR / "outbox.jsonl", [])  # IP-like manifest
        outbox.append({"ts": int(time.time()), "chat_id": chat_id, "text": text})
        _save_json(TGPMINI_DIR / "outbox.jsonl", outbox)

    def inbound_note(self, text: str, source: str = "telegram") -> dict:
        """Pass inbound text through NoteStore so it shows up across all sinks."""
        record = {"text": text, "source": source, "ts": int(time.time())}
        if self.store:
          try:
            self.store.add(Note(**record))
          except Exception:
            pass
        return record
