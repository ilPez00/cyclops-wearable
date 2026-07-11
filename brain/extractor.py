"""Smart note extraction from raw transcript text.

Local-first, deterministic, dependency-free. Mirrors the kind of memory
extraction Omi/limitless do: pull out actionable items, reminders with
relative dates, decisions, ideas, and a running summary. A cloud LLM adapter
can replace extract() later behind the same interface.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

NOTE_TYPES = ("task", "reminder", "decision", "idea", "summary")


@dataclass
class Note:
    id: str
    type: str
    text: str
    created: str = ""
    due: str | None = None
    source: str = "audio"
    confidence: float = 1.0
    candidate: bool = False

    def to_dict(self):
        d = asdict(self)
        if not self.candidate:
            d.pop("candidate", None)
            d.pop("confidence", None)
        return d


# crude date parsing for "by friday", "tomorrow", "next week"
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
PAT_REMINDER = re.compile(
    r"\b(remind me to|reminder to|don't forget to|remember to)\b", re.I
)
PAT_TASK = re.compile(
    r"\b(todo|to-do|i need to|i have to|i must|let's|lets|we should|i will|need to)\b",
    re.I,
)
PAT_IDEA = re.compile(r"\b(idea|what if|maybe we|suggest|could we)\b", re.I)
PAT_IDEA_LEAD = re.compile(r"^\s*(idea)\s*:\s*", re.I)
PAT_DECISION = re.compile(
    r"\b(we decided|decided to|we will|agreed to|the plan is|conclusion:)\b", re.I
)
# explicit "idea:" / "idea :" lead-in
PAT_IDEA_LEAD = re.compile(r"^\s*(idea)\s*:\s*", re.I)


def _resolve_due(text: str) -> str | None:
    t = text.lower()
    today = datetime.now()
    if "tomorrow" in t:
        return (today + timedelta(days=1)).date().isoformat()
    if "today" in t:
        return today.date().isoformat()
    if "next week" in t:
        return (today + timedelta(weeks=1)).date().isoformat()
    m = re.search(r"by\s+(\w+day)", t)
    if m:
        wd = WEEKDAYS.get(m.group(1))
        if wd is not None:
            days = (wd - today.weekday()) % 7 or 7
            return (today + timedelta(days=days)).date().isoformat()
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})", t)
    if m:
        return f"{today.year}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


def _clean_action(text: str) -> str:
    # strip leading trigger words
    for pat in (PAT_IDEA_LEAD, PAT_REMINDER, PAT_TASK, PAT_IDEA, PAT_DECISION):
        text = pat.sub("", text, count=1)
    text = re.sub(r"^\s*to\s+", "", text, flags=re.I)
    return text.strip(" .,").capitalize()


def extract(text: str) -> list[Note]:
    notes: list[Note] = []
    # split into sentences
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    for s in sents:
        s = s.strip()
        if not s:
            continue
        ts = datetime.now().isoformat(timespec="seconds")
        due = _resolve_due(s)
        nid = ts.replace(":", "").replace("-", "").replace(".", "") + str(len(notes))
        if PAT_DECISION.search(s):
            notes.append(Note(nid, "decision", _clean_action(s), ts))
        elif PAT_REMINDER.search(s):
            notes.append(Note(nid, "reminder", _clean_action(s), ts, due))
        elif PAT_IDEA.search(s):
            notes.append(Note(nid, "idea", _clean_action(s), ts))
        elif PAT_TASK.search(s):
            notes.append(Note(nid, "task", _clean_action(s), ts, due))
        else:
            notes.append(Note(nid, "summary", s, ts))
    return notes


# ---- unified interface (mirrors the transcriber design) -------------------
class Extractor:
    """Base class for note extractors."""

    name = "base"

    def extract(self, text: str) -> list[Note]:
        raise NotImplementedError


class RuleExtractor(Extractor):
    name = "rule"

    def extract(self, text: str) -> list[Note]:
        return extract(text)


def get_extractor(
    prefer: str = "auto",
    keys=None,
    provider: str = "groq",
    client=None,
    model: str = "llama-3.3-70b-versatile",
) -> Extractor:
    """Pick an extractor.

    prefer:
      rule -> deterministic regex extraction (offline, no keys)
      llm  -> LLM-backed (candidates + confidence), falls back to rule on error
      auto -> llm if a key/endpoint is configured, else rule
    """
    if prefer == "rule":
        return RuleExtractor()
    if prefer == "llm":
        from .llm_extractor import LLMClient, LLMExtractor

        k = keys or _aikeys()
        c = client or LLMClient(keys=k, provider=provider)
        return LLMExtractor(keys=k, provider=provider, client=c, model=model)
    # auto: only use LLM when a key/endpoint is present
    from .llm_extractor import LLMClient, LLMExtractor

    k = keys or _aikeys()
    if k.get_key(provider) or k.get_endpoint(provider):
        c = client or LLMClient(keys=k, provider=provider)
        return LLMExtractor(keys=k, provider=provider, client=c, model=model)
    return RuleExtractor()


def _aikeys():
    from .aikeys import AiKeys

    return AiKeys()
