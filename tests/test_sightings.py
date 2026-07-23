import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.sightings import SightingLog, capture_and_tag


def _tmp_log():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)  # SightingLog creates it lazily; start from "doesn't exist"
    return SightingLog(path)


def test_add_and_all():
    log = _tmp_log()
    assert log.all() == []
    e = log.add("desk, laptop, coffee cup", ts=1000.0)
    assert e["tags"] == "desk, laptop, coffee cup"
    assert log.all() == [e]


def test_search_is_case_insensitive_substring():
    log = _tmp_log()
    log.add("Office Desk, Laptop", ts=1)
    log.add("kitchen, stove, kettle", ts=2)
    assert len(log.search("desk")) == 1
    assert len(log.search("KETTLE")) == 1
    assert log.search("keys") == []


def test_search_empty_query_returns_nothing():
    log = _tmp_log()
    log.add("desk", ts=1)
    assert log.search("") == []
    assert log.search("   ") == []


def test_capture_and_tag_happy_path():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8FAKEJPEG\xff\xd9"
    vision = lambda b64, prompt: "desk, laptop, coffee cup"
    entry = capture_and_tag("http://device/capture", vision, log, fetch=fetch)
    assert entry is not None
    assert entry["tags"] == "desk, laptop, coffee cup"
    assert log.all() == [entry]


def test_capture_and_tag_discards_bytes_never_logs_image():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8REALJPEGBYTES\xff\xd9"
    vision = lambda b64, prompt: "kitchen"
    capture_and_tag("http://device/capture", vision, log, fetch=fetch)
    raw = log.path.read_text(encoding="utf-8")
    assert "REALJPEGBYTES" not in raw
    assert "kitchen" in raw


def test_capture_and_tag_fetch_failure_returns_none():
    log = _tmp_log()
    fetch = lambda url: None  # camera unreachable / offline
    vision = lambda b64, prompt: "should not be called"
    assert capture_and_tag("http://device/capture", vision, log, fetch=fetch) is None
    assert log.all() == []


def test_capture_and_tag_vision_exception_returns_none():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8x\xff\xd9"

    def boom(b64, prompt):
        raise RuntimeError("vision backend down")

    assert capture_and_tag("http://device/capture", boom, log, fetch=fetch) is None
    assert log.all() == []


def test_capture_and_tag_offline_or_error_stub_not_logged():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8x\xff\xd9"
    vision = lambda b64, prompt: "offline: vision would analyze frame (12 b64 chars)"
    assert capture_and_tag("http://device/capture", vision, log, fetch=fetch) is None
    assert log.all() == []
