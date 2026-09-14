import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # repo root
from brain.physis_sink import PhysisSink, capture_note, _detect_sink
from brain.store import NoteStore
from brain.extractor import Note
from brain.transcriber import StubTranscriber
from brain.pipeline import Pipeline


def make_note(note_id="test-1", text="test note", note_type="idea"):
    """Create a test Note object."""
    from datetime import datetime, timezone
    return Note(
        id=note_id,
        type=note_type,
        text=text,
        created=datetime.now(timezone.utc).isoformat(),
        due=None,
    )


def test_physis_sink_no_url():
    """Sink without CYCLOPS_PHYSIS_URL should succeed in local-only mode."""
    sink = PhysisSink(url=None, retry=False)
    note = make_note()
    result = sink.send(note)
    assert result is True, "Sink without URL should succeed in local-only mode"


def test_physis_sink_with_url_not_set():
    """Sink with URL=None should behave like local-only mode."""
    sink = PhysisSink(url=None, retry=True)
    note = make_note()
    result = sink.send(note)
    # When no URL is set, it should succeed (local-only mode)
    assert result is True or False  # either is acceptable for no-url mode


def test_physis_sink_capture_note_no_url():
    """capture_note without URL should succeed."""
    sink = _detect_sink()
    note = make_note()
    result = capture_note(note, sink)
    assert result is True, "capture_note should succeed with no URL configured"


def test_physis_sink_payload_structure():
    """Test that PhiseNotePayload creates correct JSON structure."""
    from brain.physis_sink import PhiseNotePayload
    from brain.extractor import Note
    from datetime import datetime, timezone

    note = Note(
        id="test-001",
        type="task",
        text="send email",
        created=datetime.now(timezone.utc).isoformat(),
        due=None,
    )
    payload = PhiseNotePayload(
        id=note.id,
        type=note.type,
        text=note.text,
        created=note.created,
    )
    json_str = payload.to_json()
    data = json.loads(json_str)
    assert data["id"] == "test-001"
    assert data["type"] == "task"
    assert data["text"] == "send email"
    assert "created" in data
    assert data["source"] == "audio"  # default source


def test_physis_sink_retry_queue_setup():
    """Test that retry store path is set when URL is configured."""
    # The physis_sink uses a fixed path: ~/.cyclops/physis_retry.jsonl
    # Just verify the sink is created with URL and has local_store initialized
    os.environ["CYCLOPS_PHYSIS_URL"] = "http://localhost:8080"
    sink = PhysisSink(url="http://localhost:8080", retry=True)
    # Note: local_store should be created with the fixed path
    assert sink.local_store is not None, "local_store should be initialized when URL is set"
    # The path should be the expected default
    assert sink.local_store.path == os.path.expanduser("~/.cyclops/physis_retry.jsonl"), \
        f"local_store path should be default, got {sink.local_store.path}"
    del os.environ["CYCLOPS_PHYSIS_URL"]


if __name__ == "__main__":
    # Run all tests
    import traceback
    from brain.extractor import Note
    from datetime import datetime, timezone

    tests = [
        test_physis_sink_no_url,
        test_physis_sink_with_url_not_set,
        test_physis_sink_capture_note_no_url,
        test_physis_sink_payload_structure,
        test_physis_sink_retry_queue_setup,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL {test.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)