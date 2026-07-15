"""Offline: P2-B multi-source context fusion (notes + health + calendar)."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.context import ContextAssembler
from brain.extractor import extract
from device.health_fuse import HealthAggregator


def test_fuse_notes_health_calendar():
    notes = extract(
        "Remind me to send the invoice by friday. We decided to ship the MVP next week."
    )
    agg = HealthAggregator().from_colmi(hr=72, spo2=98, battery=85, ts=1)
    cal_path = tempfile.mktemp(suffix=".jsonl")
    with open(cal_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"title": "Standup", "start": "2026-07-10T09:00"}) + "\n")
        f.write(json.dumps({"title": "Dentist", "start": "2026-07-11T15:00"}) + "\n")
    a = ContextAssembler().add_notes(notes).set_health(agg).load_calendar(cal_path)
    d = a.build()
    assert any(n["type"] == "reminder" for n in d["notes"])
    assert any(n["type"] == "decision" for n in d["notes"])
    assert d["health"]["hr"] == 72 and d["health"]["spo2"] == 98
    assert d["calendar"][0]["title"] == "Standup"
    rendered = a.render()
    assert "=== LIVE CONTEXT ===" in rendered and "=== END CONTEXT ===" in rendered
    assert "[health]" in rendered and "[calendar]" in rendered and "[notes]" in rendered
    # the body must sit strictly between the markers
    assert rendered.index("[health]") > rendered.index("=== LIVE CONTEXT ===")
    assert rendered.index("=== END CONTEXT ===") > rendered.index("[notes]")
    os.remove(cal_path)
    print("OK fused notes+health+calendar ->", repr(rendered))


def test_empty_safe():
    a = ContextAssembler()
    out = a.render()
    assert out.startswith("=== LIVE CONTEXT ===")
    assert out.endswith("=== END CONTEXT ===")
    assert "[context] empty" in out
    assert a.build()["notes"] == [] and a.build()["calendar"] == []
    print("OK empty assembler -> empty context")


def test_in_memory_calendar():
    a = ContextAssembler().set_calendar([{"title": "X", "start": "2026-07-12"}])
    assert a.build()["calendar"][0]["title"] == "X"
    print("OK in-memory calendar accepted")


if __name__ == "__main__":
    test_fuse_notes_health_calendar()
    test_empty_safe()
    test_in_memory_calendar()
    print("PASS tests/test_context.py")
