"""Tests for brain/store.py — persistent note store (JSONL + markdown).

Zero-dependency: uses a temp dir for the store path so no real
~/.cyclops notes are touched. Run with:
    python3 tests/run_tests.py tests/test_store.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo root

from brain.extractor import Note, NOTE_TYPES
from brain.store import NoteStore


def _mk(tmp, **kw):
    path = os.path.join(tmp, "notes.jsonl")
    n = Note(
        id=kw.get("id", "n1"),
        type=kw.get("type", "task"),
        text=kw.get("text", "buy milk"),
        created=kw.get("created", "2026-07-11T10:00:00"),
        due=kw.get("due"),
    )
    return NoteStore(path=path), n


def test_add_persists_and_reloads():
    with tempfile.TemporaryDirectory() as d:
        s, n = _mk(d)
        s.add(n)
        # a new store on the same path must reload the note
        s2 = NoteStore(path=os.path.join(d, "notes.jsonl"))
        assert len(s2.all()) == 1
        assert s2.all()[0].text == "buy milk"


def test_add_many_and_all():
    with tempfile.TemporaryDirectory() as d:
        s, _ = _mk(d)
        s.add_many([
            Note(id="a", type="task", text="alpha"),
            Note(id="b", type="idea", text="beta"),
            Note(id="c", type="task", text="gamma"),
        ])
        assert len(s.all()) == 3


def test_by_type_filters():
    with tempfile.TemporaryDirectory() as d:
        s, _ = _mk(d)
        s.add_many([
            Note(id="a", type="task", text="alpha"),
            Note(id="b", type="idea", text="beta"),
            Note(id="c", type="task", text="gamma"),
        ])
        tasks = s.by_type("task")
        assert len(tasks) == 2
        assert all(t.type == "task" for t in tasks)
        assert len(s.by_type("idea")) == 1


def test_search_keyword_ranking():
    with tempfile.TemporaryDirectory() as d:
        s, _ = _mk(d)
        s.add_many([
            Note(id="a", type="task", text="buy milk tomorrow"),
            Note(id="b", type="idea", text="refactor the parser"),
            Note(id="c", type="task", text="milk is running low"),
        ])
        res = s.search("milk")
        assert len(res) == 2
        # both matches contain "milk"; first should be the one with 2 token overlaps
        assert res[0].text == "buy milk tomorrow"


def test_search_empty_query_returns_recent():
    with tempfile.TemporaryDirectory() as d:
        s, _ = _mk(d)
        s.add_many([
            Note(id="a", type="task", text="alpha"),
            Note(id="b", type="idea", text="beta"),
        ])
        res = s.search("")
        assert len(res) == 2
        assert res[-1].text == "beta"  # most recent last


def test_search_semantic_with_embedder():
    # Fake embedder: bag-of-chars cosine so "mil" is closer to "milk" than "parser".
    def emb(s):
        v = [0.0] * 26
        for ch in s.lower():
            if "a" <= ch <= "z":
                v[ord(ch) - ord("a")] += 1.0
        return v

    with tempfile.TemporaryDirectory() as d:
        s, _ = _mk(d)
        s.add_many([
            Note(id="a", type="task", text="buy milk"),
            Note(id="b", type="idea", text="refactor parser"),
        ])
        res = s.search("mil", embedder=emb)
        assert res and res[0].text == "buy milk"


def test_dump_markdown_writes_file():
    with tempfile.TemporaryDirectory() as d:
        s, n = _mk(d, type="task", text="buy milk", due="2026-07-12")
        s.add(n)
        s.add(Note(id="b", type="idea", text="try glasses mirror"))
        out = os.path.join(d, "notes.md")
        txt = s.dump_markdown(out)
        assert os.path.exists(out)
        assert "# Cyclops Notes" in txt
        assert "## Tasks" in txt
        assert "buy milk" in txt
        assert "## Ideas" in txt


def test_clear_removes_file_and_empties():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "notes.jsonl")
        s, n = _mk(d)
        s.add(n)
        assert os.path.exists(path)
        s.clear()
        assert not os.path.exists(path)
        assert len(s.all()) == 0


def test_note_types_are_known():
    # sanity: the store relies on NOTE_TYPES sections in dump_markdown
    assert "task" in NOTE_TYPES
    assert "summary" in NOTE_TYPES


def test_max_notes_evicts_oldest():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "notes.jsonl")
        s = NoteStore(path=path, max_notes=3)
        s.add(Note(id="a", type="note", text="first", created="2026-01-01"))
        s.add(Note(id="b", type="note", text="second", created="2026-01-02"))
        s.add(Note(id="c", type="note", text="third", created="2026-01-03"))
        assert len(s.all()) == 3
        s.add(Note(id="d", type="note", text="fourth", created="2026-01-04"))
        assert len(s.all()) == 3
        texts = [n.text for n in s.all()]
        assert "first" not in texts
        assert "fourth" in texts


def test_max_notes_load_respects_cap():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "notes.jsonl")
        s1 = NoteStore(path=path, max_notes=0)
        s1.add(Note(id="a", type="note", text="first", created="2026-01-01"))
        s1.add(Note(id="b", type="note", text="second", created="2026-01-02"))
        s1.add(Note(id="c", type="note", text="third", created="2026-01-03"))
        assert len(s1.all()) == 3
        # reload with a cap of 2
        s2 = NoteStore(path=path, max_notes=2)
        assert len(s2.all()) == 2
        assert s2.all()[0].text == "second"


def test_prune_explicit():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "notes.jsonl")
        s = NoteStore(path=path, max_notes=0)
        s.add(Note(id="a", type="note", text="first"))
        s.add(Note(id="b", type="note", text="second"))
        s.add(Note(id="c", type="note", text="third"))
        assert len(s.all()) == 3
        s.prune(keep=2)
        assert len(s.all()) == 2
        texts = [n.text for n in s.all()]
        assert "first" not in texts
        # file must also be trimmed
        s2 = NoteStore(path=path, max_notes=0)
        assert len(s2.all()) == 2


def test_zero_max_notes_unlimited():
    with tempfile.TemporaryDirectory() as d:
        s = NoteStore(path=os.path.join(d, "notes.jsonl"), max_notes=0)
        for i in range(100):
            s.add(Note(id=str(i), type="note", text=f"note-{i}"))
        assert len(s.all()) == 100
