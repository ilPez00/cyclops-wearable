# cad/ — how this directory works now

The enclosure work was **reset** on 2026-09-28: the models that were here were
built on wrong part dimensions (evidence table in `docs/44-case-redesign.md` §0),
so nothing in this directory is a source any more except the files listed below.

## Sources (edit these)

| File | What it is |
|---|---|
| `params.yaml` | **the only place a case dimension is written.** Every value carries a provenance tag: PROBED (vendor geometry), SPEC (datasheet), DEFAULT (docs/44 §4, confirmed by the coupon), UNVERIFIED (a guess + the caliper measurement that will replace it) |
| `fit_coupon.scad` | the first print: gap pockets, PCB slots, M2 pilots, USB-C and microSD openings, a snap latch. Includes `params.scad`; contains no dimensions of its own |
| `vendor/seeed/` | Seeed's own DXF/STEP assets for the XIAO ESP32-S3 Sense (see `vendor/seeed/SOURCE.md` for re-download commands) |
| `legacy/` | *(after docs/44 §7 step 5)* the retired `.scad` / `.blend` / `.stl` / FreeCAD presets, kept for history only |

## Generated (do not edit)

| File | Generator |
|---|---|
| `params.scad` | `python3 scripts/cad_params.py generate` |
| `stl/fit_coupon.stl` | `cad/fit_coupon.scad` via OpenSCAD |
| `renders/` | `cad/render_all_3d.sh` (Blender) — **git-ignored**, 54 MB of regenerable previews |

## Workflow

```bash
# 1. get a compiler without root (extracts the AppImage into ~/.local)
bash scripts/get_openscad.sh
OS=~/.local/share/openscad-appimage/squashfs-root/AppRun

# 2. edit cad/params.yaml, then regenerate and read the derived numbers
python3 scripts/cad_params.py            # generate + envelope
python3 scripts/cad_params.py envelope   # envelope only, lists UNVERIFIED inputs

# 3. build and verify the coupon
$OS --export-format binstl -o cad/stl/fit_coupon.stl cad/fit_coupon.scad
python3 scripts/cad_params.py check cad/stl/fit_coupon.stl      # watertight, bbox, mass
python3 scripts/cad_params.py section cad/stl/fit_coupon.stl 3.5  # do the pockets measure what they claim?

# 4. probe vendor geometry instead of guessing
python3 scripts/cad_probe.py dxf  cad/vendor/seeed/Sense_TOP.dxf
python3 scripts/cad_probe.py step 'cad/vendor/seeed/3d/Seeed Studio XIAO-ESP32-S3-Sense.step'
```

Dependencies (user site, no root): `pyyaml`, `trimesh` (+ `numpy`, `ezdxf` for
the probes). `scripts/cad_params.py` documents what each command needs.

## Hard rules

- A withdrawn number stays withdrawn. The old `screen_w/h = 35/36`,
  `screen_glass = 28` and the two conflicting accel sizes are **not** to be
  reintroduced, in any language.
- No dimension literal inside a model file: if a model needs a number, it comes
  from `params.scad`.
- Nothing here is "final" before a physical fit (`docs/44` §7 step 6).
