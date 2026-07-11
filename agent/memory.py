"""Hermes-style dual memory store — agent facts + user profile.

Ports the core of Hermes's memory model into the Cyclops brain:

- Two durable, human-readable markdown files:
    * MEMORY.md  -> facts about the agent/world/environment (target="agent")
    * USER.md    -> who the user is: preferences, identity, how they work
                    (target="user")
- Entries are short, declarative §-delimited "cards" (one fact per card),
  each kept under a tight char budget so they stay cheap to inject every
  session (the same reason Hermes caps MEMORY.md entries at ~220 chars).
- Stable indexing: cards are addressed by position (0-based) so the app and
  the /api/memory endpoints can edit/delete a single learned fact without
  rewriting the whole file.

Cyclops keeps its OWN memory root (~/.cyclops/memory) so it never clobbers
the user's real ~/.hermes/MEMORY.md. The store is offline-safe: every
method swallows IO errors and returns sane empties rather than raising.
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# § delimiter between cards. Reading tolerates either "\n§\n" or a leading "§ ".
_CARD_SEP = "\n§\n"
_CARD_RE = re.compile(r"(?m)^§\s*$")

# Per-card character budget. Hermes keeps MEMORY.md cards compact for the
# same reason — they are re-injected into the system prompt on every turn.
MAX_CARD_CHARS = 240


@dataclass
class MemoryCard:
    text: str
    target: str = "agent"  # "agent" | "user"

    def to_dict(self) -> dict:
        return {"text": self.text, "target": self.target}


class MemoryStore:
    def __init__(self, config):
        self.cfg = config
        root = getattr(config, "memory_root", "~/.cyclops/memory")
        self.root = Path(root).expanduser()
        self.root.mkdir(parents=True, exist_ok=True)
        self.agent_file = self.root / (
            getattr(config, "memory_file", None) or "MEMORY.md"
        )
        self.user_file = self.root / (getattr(config, "user_file", None) or "USER.md")
        self.max_chars = int(getattr(config, "memory_max_chars", MAX_CARD_CHARS))
        self._lock = threading.Lock()  # serialize reads/writes per process

    # -- file <-> cards -----------------------------------------------------
    def _path(self, target: str) -> Path:
        return self.user_file if target == "user" else self.agent_file

    def _read_cards(self, path: Path) -> list[str]:
        try:
            if not path.exists():
                return []
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            return []
        if not text:
            return []
        parts = [p.strip() for p in _CARD_RE.split(text)]
        return [p for p in parts if p]

    def _write_cards(self, path: Path, cards: list[str]) -> None:
        # Atomic: write to temp then rename so a concurrent reader never sees
        # a half-written file (mirrors Hermes MemoryStore._write_file).
        cards = [c.strip() for c in cards if c and c.strip()]
        body = _CARD_SEP.join(cards) + ("\n" if cards else "")
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(body, encoding="utf-8")
            tmp.replace(path)
        except Exception:
            pass

    # -- public API ---------------------------------------------------------
    def list(self, target: str = "agent") -> list[MemoryCard]:
        with self._lock:
            return [
                MemoryCard(text=t, target=target)
                for t in self._read_cards(self._path(target))
            ]

    def read(self, target: str = "agent") -> str:
        """Full markdown for a target (injected into the system prompt)."""
        with self._lock:
            cards = self._read_cards(self._path(target))
        if not cards:
            return ""
        return "\n§\n".join(cards)

    def append(self, text: str, target: str = "agent") -> int:
        """Append one card. Returns the new card index (or -1 on empty)."""
        text = (text or "").strip()
        if not text:
            return -1
        # Enforce the char budget so memory stays cache-cheap.
        if len(text) > self.max_chars:
            text = text[: self.max_chars - 1].rstrip() + "…"
        with self._lock:
            cards = self._read_cards(self._path(target))
            cards.append(text)
            self._write_cards(self._path(target), cards)
            return len(cards) - 1

    def edit(self, index: int, text: str, target: str = "agent") -> bool:
        text = (text or "").strip()
        if not text:
            return False
        if len(text) > self.max_chars:
            text = text[: self.max_chars - 1].rstrip() + "…"
        with self._lock:
            cards = self._read_cards(self._path(target))
            if not 0 <= index < len(cards):
                return False
            cards[index] = text
            self._write_cards(self._path(target), cards)
            return True

    def delete(self, index: int, target: str = "agent") -> bool:
        with self._lock:
            cards = self._read_cards(self._path(target))
            if not 0 <= index < len(cards):
                return False
            del cards[index]
            self._write_cards(self._path(target), cards)
            return True

    def recall(self, target: str = "agent", limit: int = 8) -> str:
        """Last `limit` cards as a compact context blob (offline-safe)."""
        with self._lock:
            cards = self._read_cards(self._path(target))[-limit:]
        if not cards:
            return ""
        return "\n".join(f"- {c}" for c in cards)

    def counts(self) -> dict:
        with self._lock:
            return {
                "agent": len(self._read_cards(self.agent_file)),
                "user": len(self._read_cards(self.user_file)),
            }


def _as_json_payload(store: MemoryStore) -> str:
    """Combined view for the app / api: both targets with indices."""
    out = {
        "agent": [c.to_dict() for c in store.list("agent")],
        "user": [c.to_dict() for c in store.list("user")],
    }
    return json.dumps(out)
