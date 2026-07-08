"""Bridge between the digiGio desk-companion brain and the Cyclops wearable brain.

digiGio (the desk face / philosophy companion) holds long-term persona memory,
an M3 RAG store and a running conversation. Cyclops (the wearable) captures
short, glanceable notes on the go. This bridge lets the two share context
without coupling their internals:

  * digiGio -> Cyclops : push persona + retrieved M3 RAG chunks so that
    on-device note extraction can be disambiguated ("the Marco from the
    lecture", "the MVP we decided on"). Pure context, never auto-committed.
  * Cyclops -> digiGio : surface new candidate notes back so digiGio can
    remember them in its wiki / mention them in conversation.

The bridge is fully offline and side-effect free: context is held in memory
(and optionally a JSONL file) and merged into note metadata. No import of the
digiGio ``duck`` package is required — an adapter object with the methods
``get_persona() -> str`` and ``retrieve(query) -> list[str]`` is the only
contract, so it works against the real brain or a test double.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class BridgeContext:
    persona: str = ""
    rag_chunks: list[str] = field(default_factory=list)
    recent_turns: list[str] = field(default_factory=list)
    source: str = "digigio"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"persona": self.persona, "rag_chunks": self.rag_chunks,
                "recent_turns": self.recent_turns, "source": self.source,
                "ts": self.ts}


class DigigioBridge:
    def __init__(self, adapter=None, context_path: str | None = None,
                 on_push: Callable[[dict], None] | None = None):
        """
        adapter: object exposing get_persona() -> str and retrieve(q) -> list[str]
                 (the digiGio Brain satisfies this). May be None for offline use.
        context_path: optional JSONL file to persist pushed context.
        on_push: callback invoked with a dict whenever context is pushed to
                 digiGio (e.g. to feed its wiki store).
        """
        self.adapter = adapter
        self.context_path = os.path.expanduser(context_path) if context_path else None
        self.on_push = on_push
        self._last: BridgeContext | None = None

    # -- digiGio -> Cyclops ------------------------------------------------
    def pull_context(self, query: str = "") -> BridgeContext:
        """Collect current digiGio context (persona + RAG + recent turns)."""
        persona = ""
        rag: list[str] = []
        if self.adapter is not None:
            try:
                persona = self.adapter.get_persona() or ""
            except Exception:
                persona = ""
            try:
                rag = list(self.adapter.retrieve(query) or [])
            except Exception:
                rag = []
        ctx = BridgeContext(persona=persona, rag_chunks=rag, recent_turns=[])
        self._last = ctx
        return ctx

    def enrich_note(self, note, ctx: BridgeContext | None = None) -> dict:
        """Return note.to_dict() augmented with bridge provenance context."""
        ctx = ctx or self._last or BridgeContext()
        d = note.to_dict()
        meta = {"bridge_source": ctx.source}
        if ctx.persona:
            meta["persona_hint"] = ctx.persona[:120]
        if ctx.rag_chunks:
            # only attach the most relevant chunk as a disambiguation hint
            meta["rag_hint"] = ctx.rag_chunks[0][:160]
        d["bridge"] = meta
        return d

    # -- Cyclops -> digiGio ------------------------------------------------
    def push_notes(self, notes: list) -> dict:
        """Surface new Cyclops notes back to digiGio. Returns a summary dict."""
        payload = {
            "event": "cyclops_notes",
            "count": len(notes),
            "notes": [self.enrich_note(n) for n in notes],
            "ts": time.time(),
        }
        if self.context_path:
            os.makedirs(os.path.dirname(self.context_path) or ".", exist_ok=True)
            with open(self.context_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        if self.on_push:
            self.on_push(payload)
        return payload


# -- adapter shim for the real digiGio Brain (lives on the digigio drive) --
class DigigioAdapter:
    """Thin wrapper around digigio.brain.Brain implementing the bridge contract.

    Imported lazily so this module stays importable even when the digigio
    package is not on the path (it lives on a separate drive).
    """
    def __init__(self, brain):
        self.brain = brain

    def get_persona(self) -> str:
        try:
            return getattr(self.brain, "persona_text", "") or ""
        except Exception:
            return ""

    def retrieve(self, query: str) -> list[str]:
        try:
            wiki = getattr(self.brain, "wiki", None)
            if wiki is not None and hasattr(wiki, "retrieve"):
                return list(wiki.retrieve(query) or [])
        except Exception:
            pass
        return []
