"""Pipeline factory that upgrades the brain when AI-stack keys are present.

Local-first by default: if no cloud transcription / LLM keys are found, the
pipeline silently uses the deterministic stub transcriber + rule-based
extractor. When keys exist, it transparently upgrades to:

  * CloudTranscriber  (Deepgram if available, else OpenAI-compatible STT)
  * LLMExtractor      (candidate notes via groq/openai/..., rule fallback)

The HTTP layer is injectable so the companion app and tests can substitute a
fake transport without touching the network.
"""

from __future__ import annotations

from .aikeys import AiKeys
from .pipeline import Pipeline
from .store import NoteStore


def build_transcriber(keys: AiKeys | None = None, session=None):
    from .transcriber import CloudTranscriber, StubTranscriber, WhisperTranscriber

    keys = keys or AiKeys()
    try:
        return WhisperTranscriber()
    except Exception:
        pass
    if keys.get_key("deepgram") or keys.get_endpoint("deepgram"):
        return CloudTranscriber(keys=keys, audio_provider="deepgram", session=session)
    if keys.get_key("groq") or keys.get_endpoint("groq"):
        return CloudTranscriber(keys=keys, audio_provider="groq", session=session)
    for name in ("openai", "assemblyai", "deepinfra", "together"):
        if keys.get_key(name) or keys.get_endpoint(name):
            return CloudTranscriber(keys=keys, audio_provider=name, session=session)
    return StubTranscriber()


def build_extractor(keys: AiKeys | None = None, session=None, provider: str = "groq"):
    from .extractor import extract
    from .llm_extractor import LLMClient, LLMExtractor

    keys = keys or AiKeys()
    if keys.get_key(provider) or keys.get_endpoint(provider):
        client = (
            LLMClient(keys=keys, provider=provider, session=session)
            if session
            else None
        )
        return LLMExtractor(keys=keys, provider=provider, client=client)
    return extract  # rule-based function


def build_pipeline(
    store_path: str | None = None,
    keys: AiKeys | None = None,
    session=None,
    llm_provider: str = "groq",
):
    """Return a Pipeline wired with the best available transcriber + extractor."""
    keys = keys or AiKeys()
    store = NoteStore(store_path or "~/.cyclops/notes.jsonl")
    trans = build_transcriber(keys, session)
    extr = build_extractor(keys, session, llm_provider)
    return Pipeline(store, transcriber=trans, extractor=extr)
