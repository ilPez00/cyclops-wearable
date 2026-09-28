"""Tests for brain/events.py — the event ledger (docs/34 Phase 1a) and the
presence claim-boundary wiring it feeds (docs/43 C5)."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.events import Event, EventLog, seconds_since


def test_event_shape_carries_duration_and_provenance():
    e = Event(kind="note", body="called Marco", duration_s=0.0, source="app",
              locator="notes.jsonl#n1")
    d = e.to_dict()
    # duration_s is a mandatory field, not an optional extra: it is what turns
    # "what happened while X" from a join into a query (docs/34 §1a).
    assert set(d) == {"ts", "kind", "body", "duration_s", "source", "locator"}, d
    assert d["ts"].endswith("Z") and len(d["ts"]) == 20      # 2026-09-28T10:12:03Z
    assert Event.from_dict(d) == e


def test_append_persists_and_reloads():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        log = EventLog(path)
        assert log.count() == 0
        log.append(kind="voice", body="ship it", duration_s=12.5,
                   source="wearable", locator="ble:vnote")
        log.append(kind="photo", body="menu", source="camera")
        assert os.path.exists(path)
        again = EventLog(path)
        assert again.count() == 2
        assert again.all()[0].body == "ship it"
        assert again.all()[0].duration_s == 12.5


def test_recent_is_newest_first_and_limit_can_be_zero():
    with tempfile.TemporaryDirectory() as d:
        log = EventLog(os.path.join(d, "events.jsonl"))
        for i, ts in enumerate(("2026-09-28T10:00:00Z", "2026-09-28T11:00:00Z",
                                "2026-09-28T12:00:00Z")):
            log.append(kind="note", body=f"n{i}", ts=ts)
        assert [e.body for e in log.recent(2)] == ["n2", "n1"]
        assert log.recent(0) == []


def test_search_matches_body_kind_and_source():
    with tempfile.TemporaryDirectory() as d:
        log = EventLog(os.path.join(d, "events.jsonl"))
        log.append(kind="presence", body="off-body", source="wearable")
        log.append(kind="note", body="standup at 14:30", source="app")
        assert [e.kind for e in log.search("standup")] == ["note"]
        assert len(log.search("wearable")) == 1     # source leg
        assert len(log.search("presence")) == 1     # kind leg
        assert len(log.search("")) == 2             # empty query -> recent
        assert log.search("nothing here") == []


def test_by_kind():
    with tempfile.TemporaryDirectory() as d:
        log = EventLog(os.path.join(d, "events.jsonl"))
        log.append(kind="presence", body="on-body")
        log.append(kind="note", body="n")
        log.append(kind="presence", body="off-body")
        kinds = [e.body for e in log.by_kind("presence")]
        assert sorted(kinds) == ["off-body", "on-body"]


def test_seconds_since():
    assert seconds_since("2026-09-28T10:00:00Z", "2026-09-28T10:01:30Z") == 90.0
    assert seconds_since("nonsense", "2026-09-28T10:01:30Z") == 0.0
    # a stamp in the future (clock skew) must not yield a negative duration
    assert seconds_since("2026-09-28T10:02:00Z", "2026-09-28T10:00:00Z") == 0.0


def test_corrupt_line_does_not_hide_the_ledger():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "events.jsonl")
        with open(path, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"kind": "note", "body": "ok",
                                "duration_s": 1}) + "\n")
        log = EventLog(path)
        assert log.count() == 1 and log.all()[0].body == "ok"


def test_presence_edge_becomes_a_ledger_event():
    """docs/43 C5: the firmware's pres bit is a claim boundary, not a silent
    sensor gap — the bridge writes an Event carrying how long the state lasted
    (docs/34 §5c: a sensor gap must be visible in the ledger, not implied)."""
    from brain.hud_bridge import HudBridge
    from brain.protocol import MSG

    class _Null:
        def write(self, b):
            pass

        def render_text(self, t):
            pass

    with tempfile.TemporaryDirectory() as d:
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = d          # EventLog() resolves its path at call time
        try:
            br = HudBridge(_Null())
            # first frame only establishes state: nothing has ended yet
            br.dispatch(MSG["STATUS"], json.dumps({"t": 8, "pres": 1, "batt": 3900}))
            assert br.last_status["batt"] == 3900
            assert EventLog().count() == 0

            br.dispatch(MSG["STATUS"], json.dumps({"t": 8, "pres": 0, "pos": 1}))
            log = EventLog()
            assert log.count() == 1
            ev = log.all()[0]
            assert ev.kind == "presence" and ev.body == "on-body"
            assert ev.source == "wearable" and ev.locator == "ble:status"
            assert ev.duration_s >= 0.0

            # back on body -> the off-body stretch closes as its own row
            br.dispatch(MSG["STATUS"], json.dumps({"t": 8, "pres": 1}))
            assert EventLog().count() == 2
            assert EventLog().all()[1].body == "off-body"
            assert br.last_status["pres"] == 1

            # ACT_IMAGE_ANALYSIS is ALSO 8: a payload that is not a status body
            # must still reach the image-analysis handler (a status frame is
            # decided by its body, never by the shared integer)
            assert br.dispatch(MSG["STATUS"], "note-4f2a") == (
                "image_analysis", "stub")

            # garbage must never BECOME a recorded status frame: it falls to the
            # handler that shares the integer (documented fallback), and the last
            # good frame survives
            assert br.dispatch(MSG["STATUS"], "not json") == ("image_analysis", "stub")
            assert br.last_status["pres"] == 1
            # a frame without a pres bit (older firmware) is recorded, and must
            # not invent a presence edge
            br.dispatch(MSG["STATUS"], json.dumps({"t": 8, "batt": 3700}))
            assert br.last_status["batt"] == 3700
            assert EventLog().count() == 2
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


def test_status_frames_reach_the_bridge_through_every_router():
    """ACT_IMAGE_ANALYSIS is 8 and MSG_STATUS is 8 — one integer, two
    namespaces. Where the type comes from the frame HEADER the meaning is
    unambiguous, and a status frame must never be dropped as "not a command"
    (presence/posture ride it, docs/43 C5)."""
    from brain.hud_bridge import FrameReceiver, HudBridge, looks_like_status
    from brain.protocol import MSG, encode
    from device.ble import BleLink, FakeBleBackend

    class _Null:
        def write(self, b):
            pass

        def render_text(self, t):
            pass

    body = json.dumps({"t": 8, "batt": 3900, "pres": 1})
    # the disambiguator itself
    assert looks_like_status(body) is True
    assert looks_like_status({"t": 8}) is True
    assert looks_like_status("note-4f2a") is False    # an ACT arg, not a body
    assert looks_like_status("") is False
    assert looks_like_status("[1,2]") is False

    frame = encode(MSG["STATUS"], body.encode())

    # FrameReceiver (USB-serial/BLE glue)
    br = HudBridge(_Null())
    FrameReceiver(br).feed(frame)
    assert br.last_status["batt"] == 3900

    # BleLink (the radio path)
    br2 = HudBridge(_Null())
    link = BleLink(br2, backend=FakeBleBackend())
    link._on_frame(MSG["STATUS"], body.encode())
    assert br2.last_status["batt"] == 3900

    # the header path is the ONE place a bad status body is reported as such
    # (and still must not raise into the radio thread)
    link._on_frame(MSG["STATUS"], b"not json")
    assert br2.last_status["batt"] == 3900             # last good frame survives

    # ...while an ACT_IMAGE_ANALYSIS command wrapped in a v2 CMD frame still
    # arrives as the action it is
    inner = json.dumps({"a": MSG["STATUS"], "arg": "note-4f2a"}).encode()
    br3 = HudBridge(_Null())
    link3 = BleLink(br3, backend=FakeBleBackend())
    link3._on_frame(9, inner)                          # 9 = MSG_CMD
    assert br3.last_status == {}                       # not mistaken for status


if __name__ == "__main__":
    test_event_shape_carries_duration_and_provenance()
    test_append_persists_and_reloads()
    test_recent_is_newest_first_and_limit_can_be_zero()
    test_search_matches_body_kind_and_source()
    test_by_kind()
    test_seconds_since()
    test_corrupt_line_does_not_hide_the_ledger()
    test_presence_edge_becomes_a_ledger_event()
    print("ALL EVENT-LEDGER TESTS PASSED")
