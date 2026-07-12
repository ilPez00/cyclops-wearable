"""Dream / proposal loop — the proactive layer Cyclops lacks.

Merges AURA's DreamEngine (replay accumulated experience -> corrective
insights) with merlin's ProposalEngine (context -> next-action suggestion).
A periodic review reads recent notes + graded experiences and, when a model
is available, asks for a short list of {kind, message} insights ("dreams").
Offline-safe: no model / no key -> a deterministic rule-based fallback (never
empty-crashes), matching learning.py's degrade pattern.

Dreams are JSONL-persisted and surfaced in the activity feed as kind="dream",
so no new UI is required.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid

_REVIEW_PROMPT = (
    "You are a background reviewer for a personal AI (Cyclops). Given recent "
    "notes and graded experiences, propose UP TO 3 short, actionable insights "
    "or next actions. Each must be one declarative sentence under 120 chars. "
    "Return STRICT JSON only: "
    '{"dreams":[{"kind":"insight|proposal|risk","message":"..."}]}. '
    "If nothing useful, return an empty list."
)


def _extract(text: str) -> list[dict]:
    if not text:
        return []
    t = text.strip()
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e <= s:
        return []
    try:
        obj = json.loads(t[s : e + 1])
    except Exception:
        return []
    out = []
    for d in obj.get("dreams", []) if isinstance(obj, dict) else []:
        if isinstance(d, dict) and d.get("message"):
            out.append(
                {
                    "kind": str(d.get("kind", "insight")),
                    "message": str(d["message"])[:160],
                }
            )
    return out[:3]


def _fallback(notes: list[str], domains: list[dict]) -> list[dict]:
    """No-model rule-based proposals so the loop is never a no-op offline."""
    out = []
    weak = [d for d in domains if d.get("avg", 1.0) < 0.4 and d.get("count", 0) >= 2]
    if weak:
        d = weak[0]
        out.append(
            {
                "kind": "proposal",
                "message": f"'{d['domain']}' is underperforming (avg {d['avg']}) — review what's blocking it.",
            }
        )
    if len(notes) >= 5:
        out.append(
            {
                "kind": "insight",
                "message": f"{len(notes)} notes captured — a summary pass may be due.",
            }
        )
    return out[:3]


class DreamStore:
    def __init__(self, path: str = "~/.cyclops/dreams.jsonl"):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()

    def add(self, kind: str, message: str) -> dict:
        row = {
            "id": uuid.uuid4().hex[:12],
            "kind": kind,
            "message": message,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "dismissed": False,
        }
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return row

    def _all(self) -> list[dict]:
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

    def active(self) -> list[dict]:
        return [d for d in self._all() if not d.get("dismissed")]

    def dismiss(self, dream_id: str) -> bool:
        rows = self._all()
        hit = False
        for r in rows:
            if r.get("id") == dream_id:
                r["dismissed"] = True
                hit = True
        if hit:
            with self._lock, open(self.path, "w", encoding="utf-8") as f:
                for r in rows:
                    f.write(json.dumps(r) + "\n")
        return hit


def review(
    notes: list[str], domains: list[dict], router=None, store=None
) -> list[dict]:
    """One review pass -> persisted dreams. router=None or failure -> fallback."""
    store = store or DreamStore()
    dreams: list[dict] = []
    if router is not None and (notes or domains):
        try:
            ctx = "NOTES:\n" + "\n".join(f"- {n}" for n in notes[-15:])
            ctx += "\nDOMAINS:\n" + "\n".join(
                f"- {d['domain']}: avg {d.get('avg')}, {d.get('pdca')}" for d in domains
            )
            res = router.chat(
                [
                    {"role": "system", "content": _REVIEW_PROMPT},
                    {"role": "user", "content": ctx},
                ]
            )
            dreams = _extract(getattr(res, "text", "") or "")
        except Exception:
            dreams = []
    if not dreams:
        dreams = _fallback(notes, domains)
    return [store.add(d["kind"], d["message"]) for d in dreams]


__all__ = ["DreamStore", "review"]
