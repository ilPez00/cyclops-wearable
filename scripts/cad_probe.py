#!/usr/bin/env python3
"""Mechanical probe for case design (docs/44).

Answers the question a naive bounding box gets wrong: *which physical part is
which size?* Vendor CAD exports (Seeed's DXFs and STEPs) lay several views or
bodies side by side, so `bbox(file)` measures the drawing sheet, not a part.

Two probes, no CAD kernel required (pure-python `ezdxf` + a hand-rolled STEP
entity walker — no FreeCAD/pythonocc on this box):

  dxf <file.dxf> [...]
      Explode INSERTs, split every segment into connected components
      (union-find on endpoints), print each component's bbox. Board-relativises
      any component inside a 17.8 x 21.1 mm outline (the XIAO/Sense board), so
      camera, USB-C, SD slot and headers come out in board coordinates.

  step <file.stp> [...]
      Read MANIFOLD_SOLID_BREP bodies and print each body's bbox in *part*
      space. Sizes are trustworthy; **positions are not** when the export has
      assembly placements (NEXT_ASSEMBLY_USAGE_OCCURRENCE /
      ITEM_DEFINED_TRANSFORMATION) — those are reported so the caveat travels
      with the numbers. Use the DXF probe for positions.

Usage:
    python3 scripts/cad_probe.py dxf cad/vendor/seeed/Sense_TOP.dxf
    python3 scripts/cad_probe.py step 'cad/vendor/seeed/3d/Seeed Studio XIAO-ESP32-S3-Sense.step'

Numbers produced this way and quoted in docs/44 §2 are marked "[probe]".
Requires: pip install ezdxf (dxf probe only).
"""

import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The XIAO / Sense board outline (mm) used to board-relativise components.
BOARD_W, BOARD_H, BOARD_TOL = 17.8, 21.1, 0.35

STEP_NUM3 = re.compile(
    r"\(\s*(-?\d+\.?\d*(?:[Ee][-+]?\d+)?)\s*,\s*(-?\d+\.?\d*(?:[Ee][-+]?\d+)?)"
    r"\s*,\s*(-?\d+\.?\d*(?:[Ee][-+]?\d+)?)\s*\)"
)
STEP_HEAD = re.compile(r"#(\d+)\s*=\s*([A-Za-z_0-9]+)\s*\(")
STEP_QUOTED = re.compile(r"'[^']*'")
STEP_REFS = re.compile(r"#(\d+)")


class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, item):
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _walk(entities):
    """Yield entities, exploding INSERTs (vendor DXFs nest their views)."""
    for ent in entities:
        if ent.dxftype() == "INSERT":
            try:
                yield from _walk(ent.virtual_entities())
            except Exception:  # a broken block should not kill the report
                continue
        else:
            yield ent


def _segments(ent):
    kind = ent.dxftype()
    if kind == "LINE":
        a, b = ent.dxf.start, ent.dxf.end
        return [((a.x, a.y), (b.x, b.y))]
    if kind == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in ent.get_points()]
        return list(zip(pts, pts[1:]))
    if kind == "POLYLINE":
        pts = [(v.dxf.location.x, v.dxf.location.y) for v in ent.vertices]
        return list(zip(pts, pts[1:]))
    if kind == "CIRCLE":
        c, r = ent.dxf.center, ent.dxf.radius
        return [((c.x - r, c.y), (c.x + r, c.y)), ((c.x, c.y - r), (c.x, c.y + r))]
    if kind == "SOLID":
        pts = [
            (ent.dxf.vtx0.x, ent.dxf.vtx0.y),
            (ent.dxf.vtx1.x, ent.dxf.vtx1.y),
            (ent.dxf.vtx2.x, ent.dxf.vtx2.y),
            (ent.dxf.vtx3.x, ent.dxf.vtx3.y),
        ]
        return list(zip(pts, pts[1:] + pts[:1]))
    return []


def probe_dxf(path, top=14):
    import ezdxf

    doc = ezdxf.readfile(path)
    uf, segs = UnionFind(), []
    for ent in _walk(doc.modelspace()):
        for a, b in _segments(ent):
            ka = (round(a[0], 2), round(a[1], 2))
            kb = (round(b[0], 2), round(b[1], 2))
            if ka == kb:
                continue
            uf.union(ka, kb)
            segs.append((ka, kb))

    groups = collections.defaultdict(list)
    for a, b in segs:
        groups[uf.find(a)].append((a, b))

    comps = []
    for members in groups.values():
        xs = [p[0] for s in members for p in s]
        ys = [p[1] for s in members for p in s]
        comps.append({
            "segs": len(members),
            "w": max(xs) - min(xs),
            "h": max(ys) - min(ys),
            "x0": min(xs),
            "y0": min(ys),
        })
    comps.sort(key=lambda c: -(c["w"] * c["h"]))

    print(f"== {path}: {len(segs)} segments -> {len(comps)} components")
    for comp in comps[:top]:
        print(
            f"   segs={comp['segs']:<6} bbox {comp['w']:9.3f} x {comp['h']:9.3f}"
            f"  at ({comp['x0']:9.3f},{comp['y0']:9.3f})"
        )

    boards = [
        c
        for c in comps
        if abs(c["w"] - BOARD_W) < BOARD_TOL and abs(c["h"] - BOARD_H) < BOARD_TOL
    ]
    for idx, board in enumerate(boards):
        print(
            f"   BOARD#{idx} {board['w']:.3f} x {board['h']:.3f}"
            f" at ({board['x0']:.3f},{board['y0']:.3f}) — parts, board-relative mm:"
        )
        inside = [
            c
            for c in comps
            if c is not board
            and c["x0"] >= board["x0"] - 0.05
            and c["y0"] >= board["y0"] - 0.05
            and c["x0"] + c["w"] <= board["x0"] + board["w"] + 0.05
            and c["y0"] + c["h"] <= board["y0"] + board["h"] + 0.05
            and c["w"] * c["h"] > 0.6
        ]
        inside.sort(key=lambda c: -(c["w"] * c["h"]))
        for c in inside[:top]:
            print(
                f"      {c['w']:7.3f} x {c['h']:7.3f}  at x"
                f" {c['x0'] - board['x0']:7.3f}  y {c['y0'] - board['y0']:7.3f}"
                f"   segs={c['segs']}"
            )


def _step_index(path):
    text = open(path, errors="ignore").read()
    ents, pos, size = {}, 0, len(text)
    while True:
        match = STEP_HEAD.search(text, pos)
        if not match:
            break
        idx, depth, start = match.end() - 1, 0, match.end() - 1
        while idx < size:
            char = text[idx]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            idx += 1
        ents[int(match.group(1))] = (match.group(2), text[start : idx + 1])
        pos = idx
    return ents


def probe_step(path, top=14):
    ents = _step_index(path)
    kinds = collections.Counter(kind for kind, _ in ents.values())
    solids = [i for i, (kind, _) in ents.items() if kind == "MANIFOLD_SOLID_BREP"]
    placements = kinds.get("NEXT_ASSEMBLY_USAGE_OCCURRENCE", 0)

    print(f"== {path}: {len(ents)} entities, {len(solids)} solids")
    print(
        f"   assembly placements: {placements}"
        + (
            "  -> part SIZES ok, part POSITIONS need transform resolution"
            if placements
            else "  -> flat export, positions usable"
        )
    )

    rows = []
    for eid in solids:
        seen, stack = set(), list(STEP_REFS.findall(ents[eid][1]))
        count, lo, hi = 0, [1e18] * 3, [-1e18] * 3
        while stack:
            ref = stack.pop()
            if ref in seen or ref not in ents:
                continue
            seen.add(ref)
            kind, body = ents[ref]
            if kind == "CARTESIAN_POINT":
                match = STEP_NUM3.search(STEP_QUOTED.sub("", body))
                if match:
                    count += 1
                    for axis, value in enumerate(float(g) for g in match.groups()):
                        lo[axis] = min(lo[axis], value)
                        hi[axis] = max(hi[axis], value)
                continue
            stack.extend(STEP_REFS.findall(body))
        if count:
            name = re.match(r"\s*\(\s*'([^']*)'", ents[eid][1])
            rows.append((
                name.group(1) if name else f"#{eid}",
                count,
                hi[0] - lo[0],
                hi[1] - lo[1],
                hi[2] - lo[2],
            ))
    rows.sort(key=lambda r: -(r[2] * r[3] * r[4]))
    for name, count, dx, dy, dz in rows[:top]:
        print(f"   {dx:8.3f} x {dy:8.3f} x {dz:8.3f}  pts={count:<6} {name[:40]!r}")


def main(argv):
    if len(argv) < 3 or argv[1] not in ("dxf", "step"):
        print(__doc__)
        return 2
    probe = {"dxf": probe_dxf, "step": probe_step}[argv[1]]
    for path in argv[2:]:
        if not os.path.exists(path):
            print(f"== {path}: MISSING")
            continue
        probe(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
