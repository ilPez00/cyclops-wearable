import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.physis_notes import memory_search, _embed, _cos, main
from brain.store import NoteStore
from brain.extractor import Note


def test_embed_norm():
    v = _embed("hello world")
    assert abs(sum(x * x for x in v) - 1.0) < 1e-6


def test_memory_rank():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "n.jsonl")
        s = NoteStore(p)
        s.add(Note("1", "task", "send invoice to marco", "2026-01-01"))
        s.add(Note("2", "idea", "vibration alert", "2026-01-02"))
        r = memory_search(NoteStore(p), "marco invoice")
        assert r and "marco" in r[0].text


def test_cli_dictate_notebook():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "n.jsonl")
        assert main(["--store", p, "dictate", "remind me to water plants tomorrow"]) == 0
        assert main(["--store", p, "notebook", "--limit", "5"]) == 0
        assert main(["--store", p, "memory", "plants"]) == 0
        assert main(["--store", p, "auto", "--chunks", "2"]) == 0
