"""End-to-end brain pipeline: audio/text -> transcript -> notes -> store + display.
Optionally joins ring health context (premortem #3)."""

from __future__ import annotations

import os
import re
import sys

from .extractor import Note, extract, get_extractor
from .transcriber import get_transcriber

# Keyword stoplist for the local entity tagger (docs/43 §9.4). Deliberately
# tiny and deterministic — this replaced a remote classifier, and a big list
# would just hide which words become entities.
_ENTITY_STOP = {
    "the", "and", "for", "with", "that", "this", "have", "will", "from",
    "your", "about", "into", "them", "they", "then", "than", "when", "what",
    "which", "been", "were", "says", "make", "made", "just", "also", "more",
    "next", "over", "some", "such", "most", "many", "each", "does", "done",
}


def _keywords(text: str, min_len: int = 4, limit: int = 12) -> list[str]:
    """Deterministic entity candidates: words >= min_len, deduped, capped."""
    out: list[str] = []
    seen: set[str] = set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9_'-]+", text or ""):
        k = w.lower()
        if len(k) < min_len or k in _ENTITY_STOP or k in seen:
            continue
        seen.add(k)
        out.append(k)
        if len(out) >= limit:
            break
    return out


class Pipeline:
    def __init__(
        self,
        store,
        transcriber=None,
        on_note=None,
        on_transcript=None,
        health=None,
        extractor=None,
    ):
        self.store = store
        self.trans = transcriber or get_transcriber()
        # unified extractor: rule by default, llm (with rule fallback) if keys present
        self.extractor = extractor or get_extractor()
        self.on_note = on_note
        self.on_transcript = on_transcript
        self.health = health
        self.last_transcript = ""

    def _do_extract(self, text):
        if self.extractor is not None:
            if hasattr(self.extractor, "extract"):
                return self.extractor.extract(text)
            return self.extractor(text)
        return extract(text)

    def _enrich(self, note: Note):
        if self.health:
            avg = self.health.avg_hr_around(int(__import__("time").time() * 1000))
            if avg:
                note.text = f"{note.text}  (~{avg}bpm)"
        self._tag_entities(note)
        return note

    def _tag_entities(self, note: Note):
        """Local entity tagging on ingest (docs/43 §9.4).

        Replaces the dead physis-pro `/api/v1/classify` call: deterministic,
        offline, no model, no network. Long-enough keywords from the note text
        become EntityStore rows, so the app's Entities tab and the concept
        index have something real to join on. Off by default —
        CYCLOPS_ENRICH_ENTITIES=1 enables it; CYCLOPS_PHYSIS_ENRICH stays a
        legacy alias so existing deployments keep working.
        """
        on = (os.environ.get("CYCLOPS_ENRICH_ENTITIES")
              or os.environ.get("CYCLOPS_PHYSIS_ENRICH"))
        if on != "1":
            return
        try:
            from .entities import EntityStore

            store = EntityStore()
            for word in _keywords(note.text):
                store.touch(word, etype="thing", note=note.id)
        except Exception as e:
            # Best-effort enrichment must never lose the note itself, but it
            # also must not fail silently (docs/34 §3c silence audit).
            print(f"[enrich] entity tagging skipped: {e}", file=sys.stderr)


    def process_audio(self, pcm16, rate=16000):
        text = self.trans.transcribe(pcm16, rate)
        self.last_transcript = text
        if self.on_transcript:
            self.on_transcript(text)
        return self._emit(self._do_extract(text))

    def process_text(self, text):
        self.last_transcript = text
        if self.on_transcript:
            self.on_transcript(text)
        return self._emit(self._do_extract(text))

    def _emit(self, notes):
        for n in notes:
            self._enrich(n)
            self.store.add(n)
            if self.on_note:
                self.on_note(n)
        return notes


# ---- P1-B: local-first inference policy ---------------------------------
# Resolved here (not in agent.config) so brain stays importable without agent.
def resolve_stt(cfg, keys=None):
    """Return a Transcriber for the resolved mode (enforces local-first).

    Cloud is only selected when the user explicitly opts in; otherwise we stay
    offline (deterministic stub) or use a local whisper endpoint. We never
    phone home implicitly.
    """
    from .transcriber import StubTranscriber, get_transcriber

    mode = cfg.resolve_mode()
    if mode == "cloud":
        return get_transcriber("cloud", keys=keys)
    if mode == "local":
        try:
            return get_transcriber("whisper")
        except Exception:
            return StubTranscriber()
    return StubTranscriber()  # offline-first default


def resolve_mode_name(cfg) -> str:
    return cfg.resolve_mode()
