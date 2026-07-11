"""Offline tests for semantic/keyword note search (T3.1)."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.extractor import Note
from brain.store import NoteStore


def _store():
    path = tempfile.mktemp(suffix=".jsonl")
    st = NoteStore(path)
    texts = [
        "buy milk tomorrow",
        "call marco about the g2 glasses",
        "ship the firmware by friday",
        "the battery lasts six hours",
        "meeting notes: roadmap and priorities",
    ]
    for i, t in enumerate(texts):
        st.add(Note(id=f"n{i}", type="task" if "by" in t else "note", text=t))
    return st, path


def test_keyword_search_ranking():
    st, p = _store()
    try:
        res = st.search("firmware friday")
        assert res, "should find something"
        # top hit should contain both query tokens
        assert "firmware" in res[0].text and "friday" in res[0].text
    finally:
        os.remove(p)


def test_semantic_embedder_path():
    # tiny bag-of-words embedder to exercise the cosine branch without deps
    vocab = ["firmware", "friday", "battery", "glasses", "meeting", "milk", "marco"]

    def emb(s):
        return [1.0 if w in s.lower().split() else 0.0 for w in vocab]

    st, p = _store()
    try:
        res = st.search("ship firmware friday", embedder=emb)
        assert res and "firmware" in res[0].text
    finally:
        os.remove(p)


def test_empty_query_returns_recent():
    st, p = _store()
    try:
        assert len(st.search("")) == 5
    finally:
        os.remove(p)


if __name__ == "__main__":
    test_keyword_search_ranking()
    test_semantic_embedder_path()
    test_empty_query_returns_recent()
    print("ALL SEARCH TESTS PASSED")
