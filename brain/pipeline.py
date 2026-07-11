"""End-to-end brain pipeline: audio/text -> transcript -> notes -> store + display.
Optionally joins ring health context (premortem #3)."""
from __future__ import annotations

from .extractor import Note, extract, get_extractor
from .store import NoteStore
from .transcriber import get_transcriber


class Pipeline:
    def __init__(self, store, transcriber=None, on_note=None, on_transcript=None,
                 health=None, extractor=None):
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
            avg = self.health.avg_hr_around(int(__import__("time").time()*1000))
            if avg: note.text = f"{note.text}  (~{avg}bpm)"
        return note

    def process_audio(self, pcm16, rate=16000):
        text = self.trans.transcribe(pcm16, rate)
        self.last_transcript = text
        if self.on_transcript: self.on_transcript(text)
        return self._emit(self._do_extract(text))

    def process_text(self, text):
        self.last_transcript = text
        if self.on_transcript: self.on_transcript(text)
        return self._emit(self._do_extract(text))

    def _emit(self, notes):
        for n in notes:
            self._enrich(n)
            self.store.add(n)
            if self.on_note: self.on_note(n)
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
