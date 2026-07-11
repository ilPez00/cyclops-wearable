"""Tests for LLMExtractor (F3) — offline via injected fake LLM client."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.aikeys import AiKeys
from brain.extractor import Note, extract
from brain.llm_extractor import LLMClient, LLMExtractor


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, payload):
        self._p = payload
        self.last = None

    def post(self, url, data=None, headers=None, timeout=30, files=None):
        self.last = {"url": url, "data": data, "headers": headers}
        return FakeResp(self._p)


class FakeLLMClient:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    def complete(self, messages, model=None, temperature=0.0):
        self.calls += 1
        return self.reply


def _keys(tmp_dir, body="groq:gsk_x\ngroq_endpoint:https://api.groq.com/openai/v1\n"):
    p = os.path.join(tmp_dir, "ai_api.txt")
    with open(p, "w") as f:
        f.write(body)
    return AiKeys(ai_api_txt=p, env_paths=[])


def test_llm_emits_candidate_notes_with_confidence():
    reply = json.dumps(
        [
            {
                "type": "reminder",
                "text": "send the invoice to Marco",
                "due": "2026-07-13",
                "confidence": 0.9,
            },
            {
                "type": "decision",
                "text": "ship the MVP",
                "due": None,
                "confidence": 0.8,
            },
        ]
    )
    with tempfile.TemporaryDirectory() as d:
        ex = LLMExtractor(keys=_keys(d), client=FakeLLMClient(reply))
        notes = ex.extract("we should send the invoice to Marco and ship the MVP")
        assert len(notes) == 2
        assert all(n.candidate is True for n in notes)
        assert notes[0].type == "reminder" and notes[0].due == "2026-07-13"
        assert notes[0].confidence == 0.9
        # to_dict keeps candidate/confidence only when candidate
        assert "candidate" in notes[0].to_dict()


def test_fallback_when_no_key():
    with tempfile.TemporaryDirectory():
        keys = AiKeys(ai_api_txt="/nope/ai_api.txt", env_paths=[])
        ex = LLMExtractor(keys=keys, client=FakeLLMClient("SHOULD NOT BE USED"))
        notes = ex.extract("Remind me to call Marco by friday")
        # fell back to rule engine -> no candidate flag, has reminder
        assert any(n.type == "reminder" for n in notes)
        assert all(not n.candidate for n in notes)


def test_fallback_on_bad_json():
    with tempfile.TemporaryDirectory() as d:
        ex = LLMExtractor(keys=_keys(d), client=FakeLLMClient("not json at all"))
        notes = ex.extract("We decided to launch on monday")
        # transparent fallback to rule extractor
        assert any(n.type == "decision" for n in notes)


def test_fallback_on_llm_exception():
    class BoomClient:
        def complete(self, *a, **k):
            raise RuntimeError("network down")

    with tempfile.TemporaryDirectory() as d:
        ex = LLMExtractor(keys=_keys(d), client=BoomClient())
        notes = ex.extract("Idea: add a vibration alert")
        assert any(n.type == "idea" for n in notes)


def test_real_rule_extractor_unaffected():
    notes = extract("Remind me to send the invoice by friday")
    assert notes[0].type == "reminder"
    assert notes[0].candidate is False
    assert "candidate" not in notes[0].to_dict()
