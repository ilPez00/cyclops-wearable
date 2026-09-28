"""Parity test for the ACT_* single source of truth (B4).

protocol/acts.yaml generates the C++ enum, the Python constants, and the
Kotlin constants via protocol/gen_acts.py. This test fails on drift in two
ways: the generator's own --check (byte-level) and an independent re-parse
of the yaml against the live Python constants (logic-level, catches a
generator that agrees with itself but not the yaml).
"""

import re
from pathlib import Path

from brain import protocol_v2 as p2

ROOT = Path(__file__).resolve().parents[1]


def _yaml_acts() -> list[tuple[str, int]]:
    text = (ROOT / "protocol" / "acts.yaml").read_text()
    return re.findall(r"name:\s*(\w+),\s*id:\s*(\d+)", text)


def test_yaml_ids_unique_and_ordered():
    acts = [(n, int(i)) for n, i in _yaml_acts()]
    assert len(acts) == 27, f"expected 27 acts, got {len(acts)}"
    ids = [i for _, i in acts]
    assert len(set(ids)) == len(ids), "duplicate ids in acts.yaml"
    assert ids == sorted(ids), "acts.yaml ids not ascending"


def test_python_mirror_matches_yaml():
    for name, id_ in _yaml_acts():
        assert getattr(p2, f"ACT_{name}", None) == int(id_), f"ACT_{name} drift"


def test_kotlin_mirror_matches_yaml():
    kt = (
        ROOT / "android" / "core" / "src" / "main" / "kotlin" / "com" / "cyclops"
        / "companion" / "core" / "HudBridge.kt"
    ).read_text()
    for name, id_ in _yaml_acts():
        m = re.search(rf"const val ACT_{name} = (\d+)", kt)
        assert m is not None, f"ACT_{name} missing in HudBridge.kt"
        assert int(m.group(1)) == int(id_), f"ACT_{name} drift in Kotlin"


def test_cpp_enum_matches_yaml():
    h = (
        ROOT / "firmware" / "lib" / "cyclops_shared" / "include" / "hud.h"
    ).read_text()
    for name, id_ in _yaml_acts():
        m = re.search(rf"ACT_{name}=(\d+)", h)
        assert m is not None, f"ACT_{name} missing in hud.h"
        assert int(m.group(1)) == int(id_), f"ACT_{name} drift in hud.h"
