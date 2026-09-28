"""Offline tests for brain/concepts.py (concept retrieval + truth audit)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.concepts import (
    ConceptIndex,
    HashEmbedder,
    delete_note,
    edit_memory_card,
    edit_note_text,
    read_truth_log,
)
from brain.extractor import Note
from brain.store import NoteStore


def _store(texts):
    path = tempfile.mktemp(suffix=".jsonl")
    st = NoteStore(path)
    for i, t in enumerate(texts):
        st.add(Note(id=f"n{i}", type="task", text=t))
    return st, path


class _FakeCards:
    def __init__(self, cards):
        self.cards = list(cards)

    def list(self, target="agent"):
        return [{"text": c} for c in self.cards]

    def edit(self, index, text, target="agent"):
        if not 0 <= index < len(self.cards) or not text.strip():
            return False
        self.cards[index] = text.strip()
        return True


def test_hash_embedder_deterministic_and_normalized():
    e = HashEmbedder()
    a, b = e.embed("battery lasts six hours"), e.embed("battery lasts six hours")
    assert a == b, "same input must give same vector"
    import math

    assert abs(math.sqrt(sum(x * x for x in a)) - 1.0) < 1e-6
    assert e.similarity("ship firmware friday", "ship firmware friday") > 0.99
    assert e.similarity("ship firmware friday", "buy milk tomorrow") < 0.9


def test_concept_search_ranks_relevant_first():
    st, p = _store([
        "buy milk tomorrow",
        "ship the firmware by friday",
        "the battery lasts six hours",
    ])
    try:
        idx = ConceptIndex(store=st)
        hits = idx.search("firmware friday", k=3)
        assert hits, "should find something"
        assert "firmware" in hits[0]["text"]
        assert hits[0]["kind"] == "note"
        assert "score" in hits[0]
    finally:
        os.remove(p)


def test_concept_search_empty_query_returns_recent():
    st, p = _store(["one", "two", "three"])
    try:
        assert len(ConceptIndex(store=st).search("")) == 3
    finally:
        os.remove(p)


def test_concept_search_covers_memory_and_entities():
    st, p = _store(["buy milk tomorrow"])

    class _Ent:
        def all(self):
            return [{"key": "marco", "name": "Marco", "type": "person",
                     "seen_count": 2, "notes": ["g2 glasses expert"]}]

    try:
        idx = ConceptIndex(store=st, memory=_FakeCards(["user likes dark mode"]),
                           entities=_Ent())
        hits = idx.search("glasses expert", k=5)
        assert any(h["kind"] == "entity" for h in hits)
        hits2 = idx.search("dark mode", k=5)
        assert any(h["kind"] == "memory" for h in hits2)
    finally:
        os.remove(p)


def test_groups_auto_organize():
    st, p = _store([
        "ship the firmware by friday",
        "firmware build takes ten minutes",
        "buy milk tomorrow",
        "buy bread and milk",
    ])
    try:
        groups = ConceptIndex(store=st).groups()
        assert groups, "should produce groups"
        labels = [g["label"] for g in groups]
        assert "firmware" in labels or "milk" in labels
        total = sum(g["count"] for g in groups)
        assert total == 4, f"every doc must land somewhere, got {total}"
    finally:
        os.remove(p)


def test_truth_edit_note_and_audit():
    st, p = _store(["buy milk tomorrow"])
    log = tempfile.mktemp(suffix=".jsonl")
    try:
        ok, entry = edit_note_text(st, "n0", "buy oat milk tomorrow", log_path=log)
        assert ok and entry["action"] == "edit_note"
        assert entry["before"] == "buy milk tomorrow"
        assert st.all()[0].text == "buy oat milk tomorrow"
        # persisted: reload from disk
        st2 = NoteStore(p)
        assert st2.all()[0].text == "buy oat milk tomorrow"
        assert read_truth_log(log_path=log)[-1]["after"] == "buy oat milk tomorrow"
    finally:
        os.remove(p)
        if os.path.exists(log):
            os.remove(log)


def test_truth_delete_note_and_audit():
    st, p = _store(["one", "two"])
    log = tempfile.mktemp(suffix=".jsonl")
    try:
        ok, entry = delete_note(st, "n0", log_path=log)
        assert ok and entry["action"] == "delete_note"
        assert len(st.all()) == 1
        assert read_truth_log(log_path=log)[-1]["before"] == "one"
    finally:
        os.remove(p)
        if os.path.exists(log):
            os.remove(log)


def test_truth_edit_memory_card():
    mem = _FakeCards(["user likes dark mode"])
    log = tempfile.mktemp(suffix=".jsonl")
    try:
        ok, entry = edit_memory_card(mem, "agent", 0, "user likes light mode", log_path=log)
        assert ok and entry["action"] == "edit_memory"
        assert mem.cards[0] == "user likes light mode"
    finally:
        if os.path.exists(log):
            os.remove(log)


def test_truth_edit_rejects_bad_ref():
    st, p = _store(["one"])
    try:
        assert edit_note_text(st, "nope", "x")[0] is False
        assert edit_note_text(st, "n0", "  ")[0] is False
        assert delete_note(st, "nope")[0] is False
    finally:
        os.remove(p)


if __name__ == "__main__":
    test_hash_embedder_deterministic_and_normalized()
    test_concept_search_ranks_relevant_first()
    test_concept_search_empty_query_returns_recent()
    test_concept_search_covers_memory_and_entities()
    test_groups_auto_organize()
    test_truth_edit_note_and_audit()
    test_truth_delete_note_and_audit()
    test_truth_edit_memory_card()
    test_truth_edit_rejects_bad_ref()
    print("ALL CONCEPTS TESTS PASSED")


# --- HTTP endpoint tests (same harness as test_app_api.py) -------------------
# HOME is redirected to a tmp dir so memory + truth_log stay hermetic.

import importlib.util
import json as _json
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "appserver_concepts", os.path.join(_REPO, "app", "server.py")
)
appserver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(appserver)


def _start(tmp):
    home = os.path.join(tmp, "home")
    os.makedirs(home, exist_ok=True)
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = home
    store = os.path.join(tmp, "notes.jsonl")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), appserver.H)
    appserver.STORE_PATH = store
    appserver.pipeline = appserver.build_pipeline(store_path=store)
    appserver.pipeline.store.clear()
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port, old_home


def _stop(srv, old_home):
    srv.shutdown()
    if old_home is None:
        os.environ.pop("HOME", None)
    else:
        os.environ["HOME"] = old_home


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, _json.loads(r.read())


def _post(port, path, data):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=_json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, _json.loads(r.read())


def test_api_concepts_search():
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _start(d)
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ingest?text="
                + urllib.parse.quote("ship the firmware by friday"),
                timeout=5,
            ).read()
            st, body = _get(port, "/api/concepts?q=firmware&k=5")
            assert st == 200 and isinstance(body, list), body
            assert body and "firmware" in body[0]["text"], body
            assert "score" in body[0] and body[0]["kind"] == "note"
        finally:
            _stop(srv, home)


def test_api_concepts_groups():
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _start(d)
        try:
            for t in ("firmware build takes ten minutes",
                      "ship the firmware by friday",
                      "buy milk tomorrow"):
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/ingest?text=" + urllib.parse.quote(t),
                    timeout=5,
                ).read()
            st, body = _get(port, "/api/concepts/groups")
            assert st == 200 and isinstance(body, list), body
            assert sum(g["count"] for g in body) >= 3, body
        finally:
            _stop(srv, home)


def test_api_truth_edit_note_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _start(d)
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ingest?text="
                + urllib.parse.quote("buy milk tomorrow"),
                timeout=5,
            ).read()
            st, notes = _get(port, "/api/notes")
            ref = notes[0]["id"]
            st, out = _post(port, "/api/truth",
                            {"action": "edit_note", "ref": ref, "text": "buy oat milk"})
            assert st == 200 and out.get("ok") is True, out
            assert out["entry"]["before"] == "buy milk tomorrow"
            st, notes = _get(port, "/api/notes")
            assert notes[0]["text"] == "buy oat milk", notes
            st, log = _get(port, "/api/truth/log?limit=5")
            assert st == 200 and log and log[-1]["action"] == "edit_note", log
        finally:
            _stop(srv, home)


def test_api_truth_rejects_unknown_action():
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _start(d)
        try:
            try:
                _post(port, "/api/truth", {"action": "rewrite_history"})
                assert False, "expected HTTP 400"
            except urllib.error.HTTPError as e:
                assert e.code == 400, e.code
                out = _json.loads(e.read())
                assert "error" in out, out
        finally:
            _stop(srv, home)
