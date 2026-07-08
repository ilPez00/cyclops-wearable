"""Persistent note store: JSONL + markdown export. No external deps."""
from __future__ import annotations
import json, os, time
from dataclasses import asdict
from .extractor import Note, NOTE_TYPES

class NoteStore:
    def __init__(self, path: str = "~/.cyclops/notes.jsonl"):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.notes: list[Note] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path): return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: self.notes.append(Note(**json.loads(line)))
                except Exception: pass

    def add(self, note: Note) -> Note:
        self.notes.append(note)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(note)) + "\n")
        return note

    def add_many(self, notes: list[Note]) -> list[Note]:
        for n in notes: self.add(n)
        return notes

    def all(self) -> list[Note]: return list(self.notes)

    def by_type(self, t: str) -> list[Note]:
        return [n for n in self.notes if n.type == t]

    def dump_markdown(self, out_path: str | None = None) -> str:
        out = out_path or (os.path.splitext(self.path)[0] + ".md")
        sections = {t: [] for t in NOTE_TYPES}
        for n in self.notes:
            sections.setdefault(n.type, []).append(n)
        lines = ["# Cyclops Notes", ""]
        for t in NOTE_TYPES:
            lines.append("## Summaries" if t=="summary" else f"## {t.capitalize()}s")
            if not sections[t]: lines.append("_none_")
            for n in sections[t]:
                due = f" (due {n.due})" if n.due else ""
                lines.append(f"- {n.text}{due}  _{n.created}_")
            lines.append("")
        txt = "\n".join(lines)
        with open(out, "w", encoding="utf-8") as f: f.write(txt)
        return txt

    def clear(self):
        self.notes = []
        if os.path.exists(self.path): os.remove(self.path)
