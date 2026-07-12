"""Experience log (PDCA): record graded actions, roll up per-domain. Offline."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.experiences import ExperienceStore, grade_label, pdca_state


def _s():
    return ExperienceStore(path=os.path.join(tempfile.mkdtemp(), "exp.jsonl"))


def test_grade_label_bands():
    assert grade_label(0.0) == "fail"
    assert grade_label(0.5) == "fair"
    assert grade_label(1.0) == "great"


def test_pdca_state_from_avg():
    assert pdca_state(0.0, 0) == "Plan"
    assert pdca_state(0.2, 3) == "Check"
    assert pdca_state(0.5, 3) == "Do"
    assert pdca_state(0.9, 5) == "Act"


def test_record_clamps_and_persists():
    s = _s()
    r = s.record("lifting", "squats 5x5", 1.5, "felt strong")  # clamps to 1.0
    assert r["grade"] == 1.0 and r["domain"] == "lifting"
    assert len(s.all()) == 1
    print("OK record clamps grade + persists")


def test_domains_rollup():
    s = _s()
    s.record("lifting", "squat", 0.9)
    s.record("lifting", "bench", 0.7)
    s.record("study", "kant", 0.3)
    doms = {d["domain"]: d for d in s.domains()}
    assert doms["lifting"]["count"] == 2
    assert abs(doms["lifting"]["avg"] - 0.8) < 1e-6
    assert doms["lifting"]["pdca"] == "Act"
    assert doms["study"]["pdca"] == "Check"
    print("OK per-domain rollup: count, avg, PDCA state")


def test_for_domain_filter():
    s = _s()
    s.record("a", "x", 0.5)
    s.record("b", "y", 0.5)
    assert len(s.for_domain("a")) == 1
    print("OK for_domain filters")
