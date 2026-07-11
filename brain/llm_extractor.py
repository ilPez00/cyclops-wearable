"""LLM-enhanced smart-note extraction, behind the same interface as extract().

Design (premortem #5): the LLM may *hallucinate* actions (e.g. invent a wrong
due date). So the LLM extractor only ever emits **candidates** with a
confidence score and an ``actionable`` flag. The companion app (phone) is the
place where the user confirms a candidate before it is committed to a calendar
/ contacts / tasks. The local-first rule-based :func:`brain.extractor.extract`
remains the deterministic fallback when no LLM key is configured or the LLM
call fails, so the pipeline never breaks.

Both :func:`extract` (rule) and :class:`LLMExtractor.extract` return
``list[Note]``; the ``Note`` gains two optional fields (``confidence``,
``candidate``) that the store and display layers ignore gracefully.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Callable

from .extractor import NOTE_TYPES, Note, _resolve_due


class LLMClientError(RuntimeError):
    """Raised when no LLM provider is configured or the endpoint is missing."""


SYSTEM_PROMPT = """You are a meeting-memory extractor for a wearable AI note-taker.
Given a transcript segment, extract structured items. For each item return JSON:
[{"type": "task|reminder|decision|idea|summary",
  "text": "clean actionable text",
  "due": "ISO date or null",
  "confidence": 0.0-1.0}]
Rules:
- type "summary" only for plain statements with no clear action.
- "reminder"/"task" may carry a due date resolved from relative words.
- Do NOT invent dates you cannot infer. If unsure, omit due.
- Output ONLY the JSON array, no prose.
"""


class LLMClient:
    """OpenAI-compatible chat-completions client (stdlib-only by default).

    Mirrors the request shape used by every provider in the user's Hermes
    config (mistral, groq, deepinfra, together, openrouter, ...). The transport
    is injectable for offline testing.
    """

    def __init__(self, keys=None, provider: str = "groq", session=None):
        from .aikeys import AiKeys

        self.keys = keys or AiKeys()
        self.provider = provider
        self.session = session or _urllib_session()

    def complete(
        self,
        messages: list[dict],
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.0,
    ) -> str:
        prov = self.keys.provider(self.provider)
        if not prov["key"] and not prov["endpoint"]:
            raise LLMClientError(f"no LLM configured for provider {self.provider}")
        endpoint = prov["endpoint"] or "https://api.openai.com/v1"
        url = endpoint.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {prov['key']}",
            "Content-Type": "application/json",
        }
        payload = {"model": model, "messages": messages, "temperature": temperature}
        resp = self.session.post(
            url, data=json.dumps(payload).encode(), headers=headers, timeout=30
        )
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"llm parse error: {e} ({data})")


class LLMExtractor:
    """Drop-in replacement for :func:`brain.extractor.extract`.

    Emits candidate notes. If the LLM is unavailable, transparently falls back
    to the rule-based extractor so the pipeline keeps producing notes.
    """

    def __init__(
        self,
        keys=None,
        provider: str = "groq",
        client: "LLMClient | None" = None,
        fallback: Callable[[str], list[Note]] | None = None,
        model: str = "llama-3.3-70b-versatile",
    ):
        from .aikeys import AiKeys
        from .extractor import extract as _rule_extract

        self.keys = keys or AiKeys()
        self.provider = provider
        self.client = client or LLMClient(keys=self.keys, provider=provider)
        self._fallback = fallback or _rule_extract
        self.model = model

    # -- public -------------------------------------------------------------
    def extract(self, text: str) -> list[Note]:
        if not text or not text.strip():
            return []
        try:
            if not (
                self.keys.get_key(self.provider)
                or self.keys.get_endpoint(self.provider)
            ):
                return self._fallback(text)
            raw = self.client.complete(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                model=self.model,
            )
            return self._parse(raw, text)
        except Exception:
            # never let extraction break the pipeline (premortem #5 + #10)
            return self._fallback(text)

    # -- internals ----------------------------------------------------------
    def _parse(self, raw: str, text: str) -> list[Note]:
        raw = raw.strip()
        # tolerate fenced code blocks
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw).strip()
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            return self._fallback(text)
        notes: list[Note] = []
        ts = datetime.now().isoformat(timespec="seconds")
        for i, it in enumerate(items):
            t = (it.get("type") or "summary").lower()
            if t not in NOTE_TYPES:
                t = "summary"
            due = it.get("due") or _resolve_due(it.get("text", ""))
            conf = float(it.get("confidence", 0.5))
            nid = ts.replace(":", "").replace("-", "").replace(".", "") + f"L{i}"
            notes.append(
                Note(
                    id=nid,
                    type=t,
                    text=str(it.get("text", "")).strip() or text[:80],
                    created=ts,
                    due=due,
                    source="llm",
                    confidence=round(conf, 2),
                    candidate=True,
                )
            )
        return notes


# ---- stdlib HTTP session (shared) ----------------------------------------
def _urllib_session():
    from .http_session import stdlib_session

    return stdlib_session()
