"""Entity store: dedup upsert, seen-count, search, types. Offline."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.entities import EntityStore


def _s():
    return EntityStore(path=os.path.join(tempfile.mkdtemp(), "ent.jsonl"))


def test_touch_creates_then_increments():
    s = _s()
    r1 = s.touch("Marco", "person")
    assert r1["seen_count"] == 1 and r1["type"] == "person"
    r2 = s.touch("marco")  # same entity, different case
    assert r2["seen_count"] == 2  # deduped + incremented
    assert len(s.all()) == 1
    print("OK touch upserts + increments (case-insensitive)")


def test_notes_accumulate_deduped():
    s = _s()
    s.touch("workshop", "place", "has a lathe")
    s.touch("workshop", "place", "has a lathe")  # dup note dropped
    s.touch("workshop", "place", "smells of oil")
    r = s.all()[0]
    assert r["notes"] == ["has a lathe", "smells of oil"]
    print("OK notes accumulate without duplicates")


def test_all_sorted_by_seen_then_recency():
    s = _s()
    s.touch("a")
    s.touch("b")
    s.touch("b")
    s.touch("b")
    s.touch("c")
    s.touch("c")
    names = [r["name"] for r in s.all()]
    assert names[0] == "b" and names[1] == "c" and names[2] == "a"
    print("OK all() ranks by seen_count")


def test_type_filter_and_search():
    s = _s()
    s.touch("Marco", "person")
    s.touch("Lathe", "thing", "in the workshop")
    assert len(s.all("person")) == 1
    assert s.search("workshop")[0]["name"] == "Lathe"
    assert s.types() == {"person": 1, "thing": 1}
    print("OK type filter + note search + type counts")


def test_empty_name_ignored():
    s = _s()
    assert s.touch("   ") == {}
    assert s.all() == []
    print("OK blank name is ignored")
