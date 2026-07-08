"""Memory, persona and health access.

Reads the on-disk memory the user asked for: Hermes MEMORY.md/USER.md and the
digiGio brain's persona + health when present. All paths are configurable
(see AgentConfig) so this works whether the digigio drive is mounted or not.
Write-back is supported for notes/reminders (memory persists to a JSONL).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class MemoryView:
    persona: str = ""
    health: str = ""
    user_profile: str = ""
    agent_memory: str = ""
    sources: list[str] = field(default_factory=list)

    def system_block(self) -> str:
        parts = []
        if self.persona:
            parts.append("PERSONA:\n" + self.persona)
        if self.user_profile:
            parts.append("USER PROFILE:\n" + self.user_profile)
        if self.health:
            parts.append("HEALTH CONTEXT:\n" + self.health)
        if self.agent_memory:
            parts.append("AGENT MEMORY:\n" + self.agent_memory)
        return "\n\n".join(parts)


class MemoryStore:
    def __init__(self, config):
        self.cfg = config

    def read(self) -> MemoryView:
        view = MemoryView()
        hermes = Path(self.cfg.hermes_home).expanduser()
        view.user_profile = self._read(hermes / self.cfg.user_file)
        view.agent_memory = self._read(hermes / self.cfg.memory_file)
        if view.user_profile: view.sources.append(str(hermes / self.cfg.user_file))
        if view.agent_memory: view.sources.append(str(hermes / self.cfg.memory_file))

        digi = Path(self.cfg.digigio_home).expanduser()
        view.persona = self._read(digi / "persona" / "character_sheet.md")
        view.health = self._read(digi / "health" / "health.md")
        if view.persona: view.sources.append(str(digi / "persona" / "character_sheet.md"))
        if view.health: view.sources.append(str(digi / "health" / "health.md"))
        return view

    def _read(self, p: Path) -> str:
        try:
            if p.exists():
                return p.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            pass
        return ""

    def append_note(self, text: str, kind: str = "note") -> str:
        """Persist a small note/reminder to the agent memory JSONL."""
        hermes = Path(self.cfg.hermes_home).expanduser()
        hermes.mkdir(parents=True, exist_ok=True)
        path = hermes / "cyclops_notes.jsonl"
        rec = {"kind": kind, "text": text}
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return str(path)
