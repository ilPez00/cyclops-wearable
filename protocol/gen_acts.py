#!/usr/bin/env python3
"""protocol/gen_acts.py — regenerate ACT_* constants from protocol/acts.yaml (B4).

Reads the single source of truth and rewrites the three generated blocks:
  firmware/lib/cyclops_shared/include/hud.h  (C++ Action enum)
  brain/protocol_v2.py                       (Python ACT_* constants)
  android/core/.../HudBridge.kt              (Kotlin const vals)

Stdlib-only (the yaml is a fixed tiny subset — parsed by regex, not PyYAML).
Idempotent: rerunning without yaml changes is a no-op (byte-identical).
Run from repo root: python3 protocol/gen_acts.py [--check]
--check exits 1 on drift without writing (CI gate).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "protocol" / "acts.yaml"

HUD_H = ROOT / "firmware" / "lib" / "cyclops_shared" / "include" / "hud.h"
PROTO_PY = ROOT / "brain" / "protocol_v2.py"
BRIDGE_KT = (
    ROOT / "android" / "core" / "src" / "main" / "kotlin" / "com" / "cyclops"
    / "companion" / "core" / "HudBridge.kt"
)

BEGIN = "GENERATED from protocol/acts.yaml"
END = "END GENERATED"


def load_acts() -> list[tuple[str, int]]:
    acts = []
    for m in re.finditer(r"name:\s*(\w+),\s*id:\s*(\d+)", YAML.read_text()):
        acts.append((m.group(1), int(m.group(2))))
    if not acts:
        raise SystemExit("gen_acts: no acts parsed from acts.yaml")
    ids = [i for _, i in acts]
    assert len(set(ids)) == len(ids), "gen_acts: duplicate ids in acts.yaml"
    return acts


def cpp_block(acts) -> str:
    lines = [
        "// " + BEGIN + " — do not hand-edit, run protocol/gen_acts.py",
        "enum Action : uint8_t {",
    ]
    # 4 per row like the existing style; the trailing partial row keeps
    # one act per line so future appends diff cleanly
    rows: list[list[str]] = []
    cur: list[str] = []
    for name, i in acts:
        cur.append(f"ACT_{name}={i}")
        if len(cur) == 4:
            rows.append(cur)
            cur = []
    if cur:
        rows.append(cur)
    for r in rows:
        lines.append("    " + ", ".join(r) + ",")
    lines.append("};")
    lines.append("// " + END)
    return "\n".join(lines)


def py_block(acts) -> str:
    lines = [
        "# " + BEGIN + " — do not hand-edit, run protocol/gen_acts.py",
        "# HUD action ids (mirror of firmware/lib/cyclops_shared/include/hud.h Action)",
    ]
    lines += [f"ACT_{name} = {i}" for name, i in acts]
    lines.append("# " + END)
    return "\n".join(lines)


def kt_block(acts) -> str:
    lines = [
        "        // " + BEGIN + " — do not hand-edit, run protocol/gen_acts.py",
    ]
    lines += [f"        const val ACT_{name} = {i}" for name, i in acts]
    lines.append("        // " + END)
    return "\n".join(lines)


def splice(path: Path, new_block: str) -> bool:
    """Replace the BEGIN..END region; returns True if the file changed."""
    text = path.read_text()
    # match from the BEGIN marker line's start to the END marker line's end,
    # tolerant of the comment prefix (// vs # vs //) already in the block
    pat = re.compile(
        r"^.*GENERATED from protocol/acts\.yaml.*\n(?:.*\n)*?.*END GENERATED.*$",
        re.MULTILINE,
    )
    m = pat.search(text)
    if not m:
        raise SystemExit(f"gen_acts: no generated block found in {path}")
    new_text = text[: m.start()] + new_block + text[m.end():]
    if new_text == text:
        return False
    path.write_text(new_text)
    return True


def main() -> int:
    check = "--check" in sys.argv
    acts = load_acts()
    jobs = [(HUD_H, cpp_block(acts)), (PROTO_PY, py_block(acts)), (BRIDGE_KT, kt_block(acts))]
    changed = []
    for path, block in jobs:
        # dry-run compare first so --check never writes
        text = path.read_text()
        pat = re.compile(
            r"^.*GENERATED from protocol/acts\.yaml.*\n(?:.*\n)*?.*END GENERATED.*$",
            re.MULTILINE,
        )
        m = pat.search(text)
        if not m:
            print(f"gen_acts: no generated block in {path}")
            return 2
        drifted = text[: m.start()] + block + text[m.end():] != text
        if drifted and not check:
            splice(path, block)
        if drifted:
            changed.append(str(path))
    if changed:
        print("gen_acts: drift in: " + ", ".join(changed))
        return 1 if check else 0
    print(f"gen_acts: in sync ({len(acts)} acts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
