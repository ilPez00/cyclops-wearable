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

    def search(self, query: str, k: int = 5, embedder=None) -> list[Note]:
        """Offline-first search. If `embedder` (callable: str->list[float]) is
        given, rank by cosine similarity (semantic); else rank by token overlap
        (keyword). Both paths work with zero deps / zero network."""
        q = (query or "").strip().lower()
        if not q:
            return self.notes[-k:]
        toks = set(q.split())
        scored = []
        for n in self.notes:
            text = n.text.lower()
            if embedder is not None:
                import math
                a = embedder(q); b = embedder(text)
                if not a or not b:
                    score = float(len(toks & set(text.split())))
                else:
                    dot = sum(x*y for x, y in zip(a, b))
                    na = math.sqrt(sum(x*x for x in a)); nb = math.sqrt(sum(y*y for y in b))
                    score = dot/(na*nb + 1e-9)
            else:
                score = float(len(toks & set(text.split())))
            if score > 0:
                scored.append((score, n))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [n for _, n in scored[:k]]

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
