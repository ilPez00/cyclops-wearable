"""End-to-end brain pipeline glue test (T2.5): text -> extract -> store + callbacks."""
import sys, os, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.pipeline import Pipeline
from brain.store import NoteStore
from brain.extractor import Note
from brain.transcriber import StubTranscriber
from brain.llm_extractor import LLMExtractor, LLMClient, LLMClientError


class FakeKeys:
    def __init__(self, ok=True): self.ok = ok
    def get_key(self, p): return "k" if self.ok else None
    def get_endpoint(self, p): return None
    def provider(self, p): return {"key": ("k" if self.ok else None), "endpoint": None}


class FakeClient:
    def __init__(self, payload): self.payload = payload
    def complete(self, messages, model="x", temperature=0.0):
        return self.payload


class FakeTranscriber:
    def transcribe(self, pcm, rate=16000):
        return "Remind me to call marco by friday. We decided to launch v1."


def test_pipeline_full_llm_path():
    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    emitted = []
    payload = json.dumps([
        {"type": "task", "text": "call marco", "due": None, "confidence": 0.9},
        {"type": "decision", "text": "launch v1", "due": None, "confidence": 0.8},
    ])
    extr = LLMExtractor(keys=FakeKeys(ok=True), client=FakeClient(payload))
    pipe = Pipeline(store, transcriber=FakeTranscriber(), extractor=extr,
                    on_note=lambda n: emitted.append(n))
    notes = pipe.process_text("anything")
    assert len(notes) == 2
    assert all(n.candidate for n in notes)
    assert len(store.all()) == 2
    assert len(emitted) == 2
    os.remove(sp)


def test_pipeline_llm_failure_falls_back_to_rule():
    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    class Boom(LLMClient):
        def complete(self, *a, **k): raise LLMClientError("down")
    extr = LLMExtractor(keys=FakeKeys(ok=True), client=Boom())
    pipe = Pipeline(store, transcriber=StubTranscriber(), extractor=extr)
    notes = pipe.process_text("Remind me to water plants tomorrow")
    # rule fallback still produced a reminder despite the LLM being down
    assert any(n.type == "reminder" for n in notes)
    assert len(store.all()) >= 1
    os.remove(sp)


def test_pipeline_health_enrichment():
    sp = tempfile.mktemp(suffix=".jsonl")
    store = NoteStore(sp)
    class Health:
        def avg_hr_around(self, ms): return 72
    pipe = Pipeline(store, transcriber=StubTranscriber(), health=Health())
    pipe.process_text("idea: a new feature")
    n = store.all()[0]
    assert "72bpm" in n.text
    os.remove(sp)


if __name__ == "__main__":
    test_pipeline_full_llm_path()
    test_pipeline_llm_failure_falls_back_to_rule()
    test_pipeline_health_enrichment()
    print("ALL PIPELINE TESTS PASSED")
