"""Offline tests for the unified note extractor (rule + llm backends)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.extractor import (extract, RuleExtractor, get_extractor, Note,
                             NOTE_TYPES)
from brain.llm_extractor import LLMExtractor, LLMClient, LLMClientError


class FakeKeys:
    def __init__(self, ok=False): self.ok = ok
    def get_key(self, p): return "k" if self.ok else None
    def get_endpoint(self, p): return None if self.ok else None
    def provider(self, p): return {"key": ("k" if self.ok else None), "endpoint": None}


class FakeClient:
    def __init__(self, payload): self.payload = payload
    def complete(self, messages, model="x", temperature=0.0):
        return self.payload


def test_rule_extract():
    notes = extract("Remind me to send the invoice by friday. We decided to ship the MVP.")
    types = {n.type for n in notes}
    assert "reminder" in types and "decision" in types
    rem = [n for n in notes if n.type == "reminder"][0]
    assert rem.due is not None  # friday resolved


def test_rule_extractor_class():
    e = RuleExtractor()
    out = e.extract("idea: add vibration alert")
    assert out[0].type == "idea"


def test_llm_extractor_candidates():
    payload = json.dumps([
        {"type": "task", "text": "email marco", "due": None, "confidence": 0.9},
        {"type": "summary", "text": "discussed roadmap", "due": None, "confidence": 0.6},
    ])
    ex = LLMExtractor(keys=FakeKeys(ok=True), client=FakeClient(payload))
    notes = ex.extract("blah blah")
    assert all(n.candidate for n in notes)
    assert notes[0].confidence == 0.9 and notes[0].type == "task"


def test_llm_falls_back_on_error():
    class BoomClient:
        def complete(self, *a, **k): raise RuntimeError("boom")
    ex = LLMExtractor(keys=FakeKeys(ok=True), client=BoomClient())
    notes = ex.extract("Remind me to call mom tomorrow")
    # rule fallback still produces a reminder
    assert any(n.type == "reminder" for n in notes)


def test_llm_no_key_falls_back_to_rule():
    ex = LLMExtractor(keys=FakeKeys(ok=False))  # no client -> raises, caught
    notes = ex.extract("idea: a new feature")
    assert notes[0].type == "idea"


def test_get_extractor_auto_rule_without_keys():
    e = get_extractor("auto", keys=FakeKeys(ok=False))
    assert isinstance(e, RuleExtractor)


def test_get_extractor_llm_with_keys():
    e = get_extractor("llm", keys=FakeKeys(ok=True), client=FakeClient("[]"))
    assert isinstance(e, LLMExtractor)
