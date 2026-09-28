"""World registry: named answers about the physical scene in front of the wearer.

Cyclops is the bridge from the computer (the phone) to the real world. The
wearable fires ACT_WORLD_* with a short tag as arg ("menu", "sign", ...);
this module resolves the tag in three tiers:

  1. registry hit — a named place/thing the user taught the system
     ("menu" at Luigi's -> today's specials, pinned by the user).
  2. live vision — capture-and-tag the current frame, zero-photo
     (bytes discarded, only tags persist — same privacy design as
     brain/sightings.py).
  3. miss — honest "don't know", logged as an event so a later registry
     entry can answer it retroactively (Phase-2 claims material).

Tags are matched case-insensitively, exact first, then substring.
Registry persists as JSON: {tag: {"answer": str, "source": str}}.
Zero-dep, offline. vision_fn injected like sightings.capture_and_tag.
"""

from __future__ import annotations

import json
import os
from typing import Callable, Optional

DEFAULT_REGISTRY = os.path.expanduser("~/.cyclops/world.json")

# ACT_WORLD_* -> (label, vision prompt) — mirrors firmware hud.h Action.
WORLD_ACTS = {
    24: ("look", "What is this? Identify it and describe it in one short sentence."),
    25: ("read", "Transcribe exactly what this text says, in reading order. No commentary."),
    26: ("price", "What does this cost? Quote the visible price and say in one line whether it is a fair deal."),
    27: ("howto", "How do I use, fix, or cook this? Answer in at most three short steps."),
}

ACT_WORLD_LOOK = 24
ACT_WORLD_READ = 25
ACT_WORLD_PRICE = 26
ACT_WORLD_HOWTO = 27


class WorldRegistry:
    def __init__(self, path: str = DEFAULT_REGISTRY):
        self.path = os.path.expanduser(path)
        self._entries: dict[str, dict] = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                self._entries = json.load(f) or {}
        except (OSError, ValueError):
            self._entries = {}

    def teach(self, tag: str, answer: str, source: str = "user") -> dict:
        row = {"answer": answer, "source": source}
        self._entries[tag.strip().lower()] = row
        self._save()
        return row

    def lookup(self, tag: str) -> Optional[dict]:
        t = (tag or "").strip().lower()
        if not t:
            return None
        if t in self._entries:
            return self._entries[t]
        for k, v in self._entries.items():
            if t in k or k in t:
                return v
        return None

    def forget(self, tag: str) -> bool:
        t = (tag or "").strip().lower()
        if t in self._entries:
            del self._entries[t]
            self._save()
            return True
        return False

    def all(self) -> dict:
        return dict(self._entries)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._entries, f)
        os.replace(tmp, self.path)


def split_steps(answer: str, max_steps: int = 6) -> list[str]:
    """Split a taught HOWTO answer into OLED-sized procedure steps (W4).

    Numbered/bulleted/dashed lines win; else split on sentence ends; else
    hard-wrap at 23 chars (firmware NCOLS). Always returns >= 1 step so the
    overlay never opens empty — a single blob becomes one step.
    """
    import re

    lines = []
    for raw in (answer or "").splitlines():
        t = raw.strip()
        if not t:
            continue
        t = re.sub(r"^(\d+[.)]|[-*•])\s+", "", t)
        lines.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip())
    if not lines:
        lines = [(answer or "").strip()] if (answer or "").strip() else ["(empty)"]
    out: list[str] = []
    for ln in lines:
        while len(ln) > 23:
            cut = ln.rfind(" ", 0, 23)
            cut = cut if cut > 0 else 23
            out.append(ln[:cut])
            ln = ln[cut:].strip()
        if ln:
            out.append(ln)
    return out[:max_steps] or ["(empty)"]


def answer_world(
    act: int,
    tag: str,
    registry: Optional[WorldRegistry] = None,
    vision_fn: Optional[Callable[[str, str], str]] = None,
    frame_b64: str = "",
    translate_fn: Optional[Callable[[str], str]] = None,
) -> tuple[str, str]:
    """Resolve one ACT_WORLD_* request. Returns (tier, text) where tier is
    one of registry/vision/miss. Registry always wins when it hits — a taught
    answer beats a fresh guess. Vision runs only with a frame and a backend;
    otherwise the miss is honest, never a stub dressed as knowledge.
    translate_fn, when given with ACT_WORLD_READ, appends a translation line
    (W6 read-then-translate: one gesture, both lines, offline-safe)."""
    reg = registry or WorldRegistry()
    hit = reg.lookup(tag or "")
    if hit:
        return ("registry", hit["answer"])
    label, prompt = WORLD_ACTS.get(act, ("look", WORLD_ACTS[24][1]))
    if vision_fn is not None and frame_b64:
        try:
            out = (vision_fn(frame_b64, prompt) or "").strip()
        except Exception:
            out = ""
        if out and not out.startswith("error:") and not out.startswith("offline:"):
            text = f"{label.upper()}: {out}"
            if act == ACT_WORLD_READ and translate_fn is not None:
                try:
                    tr = (translate_fn(out) or "").strip()
                except Exception:
                    tr = ""
                if tr and tr.lower() != out.lower():
                    text += f"\nTR: {tr}"
            return ("vision", text)
    return ("miss", f"{label}: don't know yet — teach me with /api/world/teach")
