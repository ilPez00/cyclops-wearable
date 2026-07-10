"""Automatic learning — the Cyclops port of Hermes's background-review loop.

Hermes, after every turn, forks a review agent that replays the conversation
and asks itself "should any memory/skill be saved?". This module is the
Cyclops adaptation:

    learn_from_turn(user_text, assistant_text, store, router, async_ok=True)

- Runs OFF the hot path: when async_ok it spawns a daemon thread so the agent's
  reply is never delayed by the review call (exactly Hermes's design — the
  main conversation and prompt cache are never touched by the fork).
- Uses the SAME model router the agent uses, so it reuses any warm cache and
  the same credentials.
- Offline-safe: if no LLM router / no key, it degrades to a no-op (Cyclops is
  local-first; learning simply doesn't fire without a model).
- Writes compact, char-budgeted cards to the store (agent + user targets),
  one fact per card — matching Hermes's declarative, cache-cheap memory style.

The review prompt deliberately asks for TWO buckets (like Hermes's
MEMORY.md/USER.md split):
    * "user" facts  -> USER.md  (who the user is, preferences, how they work)
    * "agent" facts -> MEMORY.md (environment, durable world/agent facts)
"""
from __future__ import annotations

import json
import threading
from typing import Optional

from .memory import MemoryStore

_REVIEW_PROMPT = (
    "You are a memory-review pass for a personal AI agent (Cyclops). You are "
    "given one exchange. Extract ONLY durable, reusable facts worth remembering "
    "across future sessions. Be terse — each fact must be a single declarative "
    "sentence, under 200 characters, no preamble, no quotes.\n\n"
    "Return STRICT JSON only, shape:\n"
    '{"user": ["fact about the user / their preferences / how they work"], '
    '"agent": ["durable fact about the world / environment / agent setup"]}\n\n'
    "Rules:\n"
    "- If nothing durable was learned, return empty arrays.\n"
    "- Do NOT store ephemeral task results, one-off answers, or secrets.\n"
    "- user = who the user is; agent = environment/world facts.\n"
    "- No markdown, no commentary — only the JSON object."
)


def _extract_json(text: str) -> Optional[dict]:
    """Best-effort JSON extraction from a model reply (handles ``` fences)."""
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        # drop an optional language tag on the first line
        t = t.split("\n", 1)[1] if "\n" in t else t
    # find the outermost {...}
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    blob = t[start : end + 1]
    try:
        obj = json.loads(blob)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _review(user_text: str, assistant_text: str, store: MemoryStore,
            router) -> dict:
    """Synchronous review. Returns a summary of what was written."""
    written = {"user": 0, "agent": 0}
    try:
        reply = router.complete(
            [{"role": "system", "content": _REVIEW_PROMPT},
             {"role": "user", "content":
                 f"USER: {user_text}\n\nASSISTANT: {assistant_text}"}],
            # learning is a small, cheap call — no tools, short output
            max_tokens=400,
        )
        if not reply:
            return written
        data = _extract_json(reply)
        if not data:
            return written
        for target in ("user", "agent"):
            for fact in (data.get(target) or []):
                if isinstance(fact, str) and fact.strip():
                    if store.append(fact.strip(), target=target) >= 0:
                        written[target] += 1
    except Exception:
        # never let learning break the agent
        pass
    return written


def learn_from_turn(user_text: str, assistant_text: str, store: MemoryStore,
                    router=None, async_ok: bool = True) -> dict:
    """Review a completed turn and persist any learned facts.

    Args:
        router: the agent's ModelRouter (or anything with .complete(messages)).
                If None, learning is skipped (offline-safe).
        async_ok: when True, run the review in a daemon thread so it never
                blocks the agent's reply. Returns {} immediately in that case;
                the actual write happens in the background.

    Returns:
        When async_ok=False: the summary dict {"user": n, "agent": n}.
        When async_ok=True: {} (work happens off-thread).
    """
    if router is None or not user_text or not assistant_text:
        return {}
    if not async_ok:
        return _review(user_text, assistant_text, store, router)

    def _run():
        _review(user_text, assistant_text, store, router)

    t = threading.Thread(target=_run, name="cyclops-learn", daemon=True)
    t.start()
    return {}


def learn_recent(history: list[dict], store: MemoryStore, router=None,
                 limit: int = 6) -> dict:
    """Re-review the last `limit` turns (used by the app's "Learn" button)."""
    written = {"user": 0, "agent": 0}
    if router is None or not history:
        return written
    turns = [m for m in history if m.get("role") in ("user", "assistant")]
    turns = turns[-limit * 2:]
    # pair up user/assistant
    for i in range(0, len(turns) - 1, 2):
        u = turns[i]
        a = turns[i + 1]
        if u.get("role") != "user" or a.get("role") != "assistant":
            continue
        w = _review(_text(u), _text(a), store, router)
        written["user"] += w["user"]
        written["agent"] += w["agent"]
    return written


def _text(msg: dict) -> str:
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict))
    return ""
