"""Tests for brain/calendar_loop.py (W8): calendar entries -> capture actions.

Pure-function tests; no scheduler, no network. The gate the doc names
(one real week) needs a live feed, but the trigger logic is deterministic
and is proven here.
"""

import json
import os
import tempfile
from datetime import datetime

from brain.calendar_loop import (
    DEFAULT_TRAVEL_MIN,
    apply_actions,
    due_actions,
    load_events,
    load_state,
    save_state,
)


def _ev(**kw):
    e = {"when": "2026-09-18", "at": "14:30", "duration_min": 30,
         "title": "Standup", "kind": "event"}
    e.update(kw)
    return e


def test_all_day_entry_never_arms():
    # no `at` -> nothing to time, skip entirely
    acts, st = due_actions([_ev(at="")], datetime(2026, 9, 18, 14, 30))
    assert acts == []
    assert st["armed"] == set()


def test_arm_file_leave_lifecycle():
    ev = _ev(place="office")
    # 14:10 = start - travel(20): leave fires once
    acts, st = due_actions([ev], datetime(2026, 9, 18, 14, 10))
    assert [a["action"] for a in acts] == ["leave"]
    # 14:29: arm (lead 1 min), leave already consumed
    acts, st = due_actions([ev], datetime(2026, 9, 18, 14, 29), st)
    assert [a["action"] for a in acts] == ["arm"]
    # 15:00: file
    acts, st = due_actions([ev], datetime(2026, 9, 18, 15, 0), st)
    assert [a["action"] for a in acts] == ["file"]
    # idempotent: nothing fires twice
    acts, st = due_actions([ev], datetime(2026, 9, 18, 15, 1), st)
    assert acts == []


def test_no_leave_without_place():
    acts, _ = due_actions([_ev()], datetime(2026, 9, 18, 14, 0))
    assert "leave" not in [a["action"] for a in acts]


def test_leave_only_before_end():
    # a meeting already over must not produce a leave nudge (only arm/file)
    acts, _ = due_actions([_ev(place="office")], datetime(2026, 9, 18, 16, 0))
    kinds = [a["action"] for a in acts]
    assert "leave" not in kinds
    assert "file" in kinds


def test_state_roundtrip_is_json_safe():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.unlink(path)
    acts, st = due_actions([_ev()], datetime(2026, 9, 18, 14, 30))
    save_state(st, path)
    back = load_state(path)
    assert set(back["armed"]) == st["armed"]
    acts2, st2 = due_actions([_ev()], datetime(2026, 9, 18, 14, 31), back)
    assert acts2 == []  # state survived the roundtrip


def test_load_events_skips_malformed(tmp_path="/tmp/cyclops_cal_test.jsonl"):
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(_ev()) + "\n")
        f.write("not json\n")
        f.write("\n")
    evs = load_events(tmp_path)
    assert len(evs) == 1 and evs[0]["title"] == "Standup"
    os.unlink(tmp_path)


def test_apply_actions_arms_and_files_bridge():
    from brain.hud_bridge import HudBridge
    from brain.transcriber import StubTranscriber

    class Cap:
        def __init__(self):
            self.frames = []

        def write(self, b):
            self.frames.append(b)

    # offline by design: stub transcriber, never machine keys/network
    b = HudBridge(sink=Cap(), transcriber=StubTranscriber())
    lines = apply_actions(
        [{"action": "arm", "id": "x", "title": "Standup", "at": "14:30"},
         {"action": "file", "id": "x", "title": "Standup", "at": "15:00"}],
        b,
    )
    assert lines == ["armed: Standup", "filed: Standup"]
    assert b.last_banner == "filed: Standup"
    assert b.recording is False
