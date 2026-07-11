"""Tests for F6 — digiGio bridge (offline, no digigio package needed)."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.bridge import BridgeContext, DigigioAdapter, DigigioBridge
from brain.extractor import Note


class FakeDigigio:
    def __init__(self):
        self.persona = "digiGio, warm philosophy companion"
        self._rag = [
            "MVP = the wearable we decided to ship next week",
            "Marco teaches the monday lecture",
        ]

    def get_persona(self):
        return self.persona

    def retrieve(self, q):
        return self._rag


def test_pull_context_from_adapter():
    b = DigigioBridge(adapter=FakeDigigio())
    ctx = b.pull_context("what is the MVP")
    assert "digiGio" in ctx.persona
    assert any("MVP" in c for c in ctx.rag_chunks)


def test_enrich_note_adds_bridge_meta():
    b = DigigioBridge(adapter=FakeDigigio())
    ctx = b.pull_context()
    n = Note("1", "decision", "ship the MVP", "2026-07-08")
    d = b.enrich_note(n, ctx)
    assert "bridge" in d
    assert d["bridge"]["bridge_source"] == "digigio"
    assert "MVP" in d["bridge"]["rag_hint"]


def test_push_notes_persists_and_callback():
    calls = []
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "bridge.jsonl")
        b = DigigioBridge(context_path=path, on_push=calls.append)
        notes = [Note("1", "task", "call Marco", "2026-07-08", due="2026-07-13")]
        payload = b.push_notes(notes)
        assert payload["count"] == 1
        assert len(calls) == 1
        assert os.path.exists(path)
        with open(path) as f:
            saved = json.loads(f.readline())
        assert saved["event"] == "cyclops_notes"
        assert saved["notes"][0]["text"] == "call Marco"


def test_adapter_shim_wraps_brain():
    class MiniBrain:
        persona_text = "x"

        class wiki:
            @staticmethod
            def retrieve(q):
                return ["chunk-a"]

    a = DigigioAdapter(MiniBrain())
    assert a.get_persona() == "x"
    assert a.retrieve("q") == ["chunk-a"]


def test_offline_no_adapter_is_safe():
    b = DigigioBridge()  # no adapter, no path
    ctx = b.pull_context()
    assert ctx.persona == "" and ctx.rag_chunks == []
    n = Note("2", "idea", "add vibration alert", "2026-07-08")
    d = b.enrich_note(n)
    assert d["bridge"]["bridge_source"] == "digigio"
