#!/usr/bin/env python3
"""Single parameter source for the case work (docs/44 §7 step 3).

`cad/params.yaml` is the only place a case dimension is written down. This
script turns it into `cad/params.scad` — so the SCAD models and the python
checks consume byte-identical numbers — computes the derived envelope that
docs/44 §5.1 states in prose, and validates a built STL numerically instead of
by eye.

Commands:
    python3 scripts/cad_params.py generate            # yaml -> cad/params.scad
    python3 scripts/cad_params.py envelope            # derived case numbers
    python3 scripts/cad_params.py check <file.stl>    # bbox / volume / watertight
    python3 scripts/cad_params.py                     # = generate + envelope

Provenance travels with every value: PROBED (vendor geometry via
scripts/cad_probe.py), SPEC (datasheet), DEFAULT (docs/44 §4 working tolerance,
confirmed by the fit coupon), UNVERIFIED (a guess — the M-number in docs/44 §6
is the caliper measurement that replaces it). `envelope` prints every
UNVERIFIED value the result depends on, so no number silently looks settled.

Requires: pyyaml (generate), trimesh (check).
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAML = os.path.join(ROOT, "cad", "params.yaml")
SCAD = os.path.join(ROOT, "cad", "params.scad")

# `  key: value   # TAG comment`  -> the tag is carried into the .scad output.
TAGGED = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):\s*(.+?)\s{2,}#\s*(.*)$")


def load():
    """Return (params, tags) from cad/params.yaml."""
    import yaml

    with open(YAML) as handle:
        text = handle.read()
    params = yaml.safe_load(text)

    tags = {}
    for line in text.splitlines():
        match = TAGGED.match(line)
        if match:
            tags[match.group(2)] = match.group(4).strip()
    return params, tags


def _scad_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_scad_value(item) for item in value) + "]"
    raise TypeError(f"unsupported parameter value: {value!r}")


def generate(params, tags):
    """Write cad/params.scad. Returns the number of emitted parameters."""
    lines = [
        "// GENERATED FILE — do not edit.",
        "// Source of truth: cad/params.yaml  (case dimensions live there).",
        "// Regenerate: python3 scripts/cad_params.py generate",
        "//",
        "// Provenance of every value: PROBED (vendor geometry, scripts/cad_probe.py)",
        "// SPEC (datasheet) | DEFAULT (docs/44 §4, confirmed by the fit coupon) |",
        "// UNVERIFIED (M-number = the caliper measurement in docs/44 §6 that",
        "// replaces it). Quote the tag when a dimension is questioned.",
        "",
    ]
    count = 0
    for group, items in params.items():
        if not isinstance(items, dict):
            continue
        lines.append(f"// ---- {group}")
        for key, value in items.items():
            tag = tags.get(key, "")
            suffix = f"  // {tag}" if tag else ""
            lines.append(f"{group}_{key} = {_scad_value(value)};{suffix}")
            count += 1
        lines.append("")

    with open(SCAD, "w") as handle:
        handle.write("\n".join(lines).rstrip() + "\n")
    return count


def envelope(params):
    """Print the derived case numbers (docs/44 §5.1) from the parameters."""
    parts, tol = params["parts"], params["tolerance"]
    case, printer = params["case"], params["printer"]
    play = tol["pocket_per_side"]
    wall = printer["wall"]

    layers = [
        ("display band (4-pin carrier)", parts["oled_carrier_x"], parts["oled_carrier_y"]),
        ("XIAO + expansion assembly", parts["sense_outline_x"], parts["sense_outline_y"]),
        ("accel breakout", parts["accel_x"], parts["accel_y"]),
        ("Li-Po 302030", parts["batt_x"], parts["batt_y"]),
    ]
    inner_x = max(l[1] for l in layers) + 2 * play
    inner_y = max(l[2] for l in layers) + 2 * play
    outer_x, outer_y = inner_x + 2 * wall, inner_y + 2 * wall

    print("== derived envelope (docs/44 §5.1) — layered arrangement")
    print(f"   {'layer':<30} {'X':>7} {'Y':>7}   (part, mm)")
    for name, x, y in layers:
        print(f"   {name:<30} {x:7.2f} {y:7.2f}")
    print(f"   + pocket play {play} per side, wall {wall}")
    print(f"   inner pocket {inner_x:.2f} x {inner_y:.2f}"
          f"  ->  outer {outer_x:.2f} x {outer_y:.2f} x Z")

    z_terms = [
        ("lid face", case["lid_t"]),
        ("display recess", tol["panel_recess"]),
        ("display carrier (incl. glass)", parts["oled_carrier_t"]),
        ("stack play (upper)", case["assembly_gap_z"] / 2),
        ("XIAO board", parts["xiao_thickness"]),
        ("XIAO<->expansion mate", parts["mate_height"]),
        ("expansion board", parts["exp_thickness"]),
        ("accel board", parts["accel_t"]),
        ("stack play (lower)", case["assembly_gap_z"] / 2),
        ("Li-Po", parts["batt_t"]),
        ("floor", printer["floor"]),
    ]
    print("\n   Z stack (headers scenario, mate_height = "
          f"{parts['mate_height']}):")
    for name, value in z_terms:
        print(f"   {name:<32} {value:6.2f}")
    total = sum(v for _, v in z_terms)
    swing = parts["mate_height"] - parts["mate_height_alt"]
    print(f"   {'TOTAL':<32} {total:6.2f}")
    print(f"   alt scenario (soldered/low-profile mate {parts['mate_height_alt']})"
          f": {total - swing:.2f}   [swing {swing:.2f} mm]")

    active_x = parts["oled_active_x"] + 2 * tol["window_over_active"]
    active_y = parts["oled_active_y"] + 2 * tol["window_over_active"]
    card_x = params["standard"]["microsd_w"] + tol["card_clear_w"]
    card_y = params["standard"]["microsd_t"] + tol["card_clear_h"]
    print("\n== derived features (what the case must cut)")
    print(f"   display window       {active_x:.3f} x {active_y:.3f}"
          f"   (active {parts['oled_active_x']} x {parts['oled_active_y']}"
          f" + {tol['window_over_active']}/side)")
    print(f"   USB-C opening        {tol['usb_cut_w']:.2f} x {tol['usb_cut_h']:.2f}"
          f"   (shell {parts['usb_shell_x']} x {parts['usb_shell_y']}"
          f" x {parts['usb_shell_t']})")
    print(f"   microSD opening      {card_x:.2f} x {card_y:.2f}")
    print(f"   PCB slot height      {tol['pcb_slot_h']:.2f}")
    print(f"   button hole          Ø{tol['button_hole']:.2f}"
          f" + Ø{tol['button_hole'] + 2 * tol['button_cbore']:.2f} counterbore")
    print(f"   M2 self-tapping      pilot Ø{tol['screw_pilot_pla']:.2f} PLA /"
          f" Ø{tol['screw_pilot_petg']:.2f} PETG")
    print(f"   antenna keep-out     {tol['antenna_keepout']:.1f}")

    tags = _load_tags()
    open_items = sorted(
        (key, tag) for key, tag in tags.items() if tag.startswith("UNVERIFIED")
    )
    print(f"\n== NOT settled: {len(open_items)} parameters still UNVERIFIED"
          " (docs/44 §6 calipers)")
    for key, tag in open_items:
        print(f"   {key:<24} {tag}")
    print("\n   The Z total above cannot be frozen before M6 (the mate height) is"
          " measured;\n   the footprint cannot be frozen before M1 (OLED carrier).")
    return 0


def _load_tags():
    _, tags = load()
    return tags


def check(path):
    """Validate a built STL: every body watertight, sensible volume, real bbox.

    Multi-body is expected and fine (the coupon prints loose parts beside the
    plate); what is *not* fine is a body a slicer has to guess at, which is how
    a face-to-face CGAL union fails.
    """
    import trimesh

    mesh = trimesh.load(path, force="mesh")
    bodies = mesh.split(only_watertight=False)
    size = mesh.extents
    print(f"== {path}")
    print(f"   bbox    {size[0]:.3f} x {size[1]:.3f} x {size[2]:.3f} mm")
    print(f"   bodies  {len(bodies)}   facets {len(mesh.faces)}"
          f"   vertices {len(mesh.vertices)}")

    problems = []
    total = 0.0
    for index, body in enumerate(bodies):
        total += body.volume
        state = "ok" if body.is_watertight else "NOT WATERTIGHT"
        print(f"     body {index}: {len(body.faces):<6} facets"
              f"  {body.volume / 1000:8.4f} cm3  {state}"
              f"  bbox {body.extents[0]:.2f} x {body.extents[1]:.2f}"
              f" x {body.extents[2]:.2f}")
        if not body.is_watertight:
            problems.append(f"body {index} is not watertight")
        if body.volume <= 0:
            problems.append(f"body {index} has non-positive volume")
    print(f"   volume  {total / 1000:.3f} cm3 total (PLA ~{total / 1000 * 1.24:.1f} g)")
    if min(size) <= 0:
        problems.append("degenerate bounding box")
    for problem in problems:
        print(f"   FAIL {problem}")
    if not problems:
        print("   OK — every body is printable")
    return 1 if problems else 0


def section(path, z):
    """Print the cross-section at a given Z, one line per closed loop.

    Every loop is a boundary: the outline of a solid, or the edge of a pocket /
    hole. The loop boxes are the numbers to compare with the parameters — the
    coupon's five blind pockets must read 8.10 / 8.15 / 8.20 / 8.25 / 8.30 by
    13.00 at z = 3.5.

    The loops are walked by hand from the cut's edge lists: trimesh's own
    path machinery pulls in shapely *and* networkx for this, and neither is
    needed to read a manifold cut.
    """
    import collections

    import trimesh

    mesh = trimesh.load(path, force="mesh")
    cut = mesh.section(plane_origin=[0, 0, float(z)], plane_normal=[0, 0, 1])
    if cut is None:
        print(f"== {path} @ z={z}: nothing there")
        return 1

    neighbours = collections.defaultdict(set)
    for index, edge in enumerate(cut.vertex_nodes):
        neighbours[edge[0]].add(edge[1])
        neighbours[edge[1]].add(edge[0])

    visited, loops = set(), []
    for start in neighbours:
        if start in visited:
            continue
        chain, current = [start], start
        visited.add(start)
        while True:
            following = next(
                (n for n in neighbours[current] if n not in visited), None
            )
            if following is None:
                break
            chain.append(following)
            visited.add(following)
            current = following
        if len(chain) > 2:
            loops.append(cut.vertices[chain])

    def _area_box(loop):
        span = loop.max(axis=0) - loop.min(axis=0)
        return float(span[0]) * float(span[1])

    loops.sort(key=lambda loop: -_area_box(loop))
    print(f"== {path} @ z={z}: {len(loops)} loops")
    for loop in loops:
        low, high = loop.min(axis=0), loop.max(axis=0)
        print(f"   x {low[0]:8.2f}..{high[0]:8.2f}  y {low[1]:8.2f}..{high[1]:8.2f}"
              f"   {high[0] - low[0]:8.3f} x {high[1] - low[1]:8.3f}"
              f"   pts {len(loop)}")
    return 0


def main(argv):
    if len(argv) > 1 and argv[1] == "check":
        if len(argv) < 3:
            print("usage: cad_params.py check <file.stl>")
            return 2
        return check(argv[2])

    if len(argv) > 1 and argv[1] == "section":
        if len(argv) < 4:
            print("usage: cad_params.py section <file.stl> <z>")
            return 2
        return section(argv[2], argv[3])

    params, tags = load()
    if argv[1:2] in ([], ["generate"], ["envelope"]):
        if argv[1:2] != ["envelope"]:
            count = generate(params, tags)
            print(f"wrote {SCAD} ({count} parameters from cad/params.yaml)")
        if argv[1:2] != ["generate"]:
            envelope(params)
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))

