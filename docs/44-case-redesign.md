# docs/44 — Case redesign: dimensions & tolerances FIRST

Status: **evidence base done (2026-09-28)** — no CAD rewritten yet, on purpose.
The premise is confirmed: every committed blender / OpenSCAD / FreeCAD model is
built on part data that is wrong, contradictory or absent (§0). This doc carries
the numbers, their source and their confidence level. §5 records the product
decisions, §6 is the caliper sheet that closes the last UNVERIFIED rows, §7 is
the gated plan.

Rule for this doc: a number is only "usable" when it is either **probed** from
the vendor's own geometry or **measured** on the actual part. Vendor *listing*
text is a lead, never a value.

## 0. Why the current models cannot be trusted

Enclosure geometry only works if the parts are right. Grepping the committed
`.scad` files shows the opposite — the same physical component has different
sizes in different files, and one panel is simply the wrong part:

| Constant | File(s) | Value | Verdict |
|---|---|---|---|
| `screen_w` / `screen_h` | variant files | 35.0 / 36.0 | **wrong** — implies a square ~36 mm panel; the MVP display is a 128×32 0.91" part with an **active area of 22.384 × 5.584 mm** |
| `screen_glass` | `cyclops_xiao_enclosure_v2.scad` | 28.0 | **wrong** — labelled "ST7735 visible glass"; the MVP build is an I2C SSD1306 128×32 |
| `win` (window reveal) | v2 | 24.0 | derived from the wrong panel; no tolerance note |
| `imu_l/w/h` | variant files | 20.0 / 15.0 / 2.5 | plausible for a GY-521-class breakout, **unverified** |
| `imu_w/h` (other file) | variants | 22 / 17 | **contradicts** the row above — one part, two sizes |
| `batt_l/w/h` | v2 | 30.0 / 20.0 / 3.0 | 302030 Li-Po by part-number convention; **unverified** |
| `xiao_l/w` | v2 | 21.0 / 17.5 | close to the drawing, but the **fab outline measures 17.790 × 21.140** (§2) → the pocket is 0.29 mm short on one axis |
| `btn_r` / `btn_d` | v2 | 6.5 / 4.2 | 6×6 mm tactile + 4.2 mm cap; **unverified** |

Missing from every model: the camera and its window, the SD card path, the
XIAO↔expansion-board mating height (the single biggest Z term, §5.2), the
antenna keep-out, the USB-C plug shell, and any tolerance stack. A lid that
"fits" in the viewport is meaningless if the pocket is 2 mm short in Z.

**Inventory to retire** (52 committed artefacts, none of them buildable against
real parts): 6 `.blend` + 4 `.blend1`, 11 `.scad`, 36 `.stl` (`cad/stl/`,
`cad/variants/`, `cad/freecad/`), 11 FreeCAD files (`build_pendant.py`,
`CyclopsPendant.FCStd`, `pendant_{body,cap}_v{4,5}.{step,stl}`), 36 renders.
They are *presets*, not sources: in §7 step 5 they move to `cad/legacy/` once
the parametrized replacement exists. Nothing is deleted before its replacement
exists.

## 1. Parts under design (locked, docs/43 §1 + the §5 decisions)

| # | Part | Exact part | Role |
|---|---|---|---|
| 1 | XIAO ESP32-S3 **Sense** | main board + camera expansion board (mated) | compute, BLE, PDM mic, OV3660 camera, microSD, USB-C, charger |
| 2 | SSD1306 **128×32 I2C, 4-pin** carrier | cheap blue PCB class (not the Adafruit STEMMA board) | the 4-row HUD |
| 3 | MPU-class accel breakout | HW-123 / GY-521 class, `0x68` — **stacked below the XIAO stack** | tilt / gestures / presence / posture |
| 4 | Li-Po 302030 | ≈3.0 × 20 × 30 mm | untethered power |
| 5 | One tactile button + cap | 6×6 mm class, bound to GPIO3 (docs/43 §2) | the single input |
| 6 | Lanyard / clip, M2 screws | Seeed's own shell uses 4 bosses Ø2.41 | mounting |

## 2. Numbers from vendor geometry (reproducible — `scripts/cad_probe.py`)

Everything marked **[probe]** was derived from Seeed's own files with
`python3 scripts/cad_probe.py dxf|step <file>` (pure-python: `ezdxf` + a STEP
entity walker). Coordinates are in the drawing's own frame.

### 2a. XIAO ESP32-S3 main board — `XIAO_ESP32S3_v1.1_Dimensioning.dxf`

| Feature | Value | Note |
|---|---|---|
| Fabrication outline | **17.790 × 21.140 mm** | [probe] one closed component, 20 segments. Published nominal is 17.5 × 21.0 → **design against the drawing** |
| Pin rows | **14 pads, 7 per side, exactly 2.54 mm pitch** | [probe] 14 components of 2.04 × 1.52 mm at y = 15.37 → 30.61 in 2.54 steps, both sides identical |
| Pad size | 2.04 × 1.52 mm | [probe] |
| Pad columns | flush with the two long edges (left pads start at the outline edge, right pads end at it) | [probe] → there are **no mounting holes**: the only retention features are these edges |
| Row-centre distance | **15.745 mm** | [probe] derived from pad-column centres; the drawing's own insets look asymmetric (0.38 vs 1.03 mm) → re-check with calipers (M4) |
| Board thickness | 1.6 mm nominal | **not probed** (2D drawing) → M5 |

### 2b. Sense camera/expansion board — `Sense_ExpBoard_top.dxf`, `_bot.dxf`

| Feature | Value | Note |
|---|---|---|
| Outline | **17.780 × 15.370 mm** | [probe] shorter than the XIAO: the **XIAO overhangs the expansion board** by ~5.8 mm |
| Corner marks | 4 × 1.905 mm squares at x = −0.635 / 15.240, y = 12.573 / 26.035 | [probe] that drawing's mechanical datums |
| Content | 613 polylines on layers 17/20/21/25 + `Defpoints` | [probe] a mechanical-only export (no copper) → good for outlines, useless for component IDs |

### 2c. Sense assembly (main + expansion) — `Sense_TOP.dxf`, `Sense_BOTTOM.dxf`

Board-relative mm, origin = board min corner:

| Feature | Value | Note |
|---|---|---|
| Board outline | **17.790 × 21.150** | [probe] matches §2a → the assembly envelope is the XIAO outline |
| **Camera footprint** | **5.050 × 4.720** at x 7.890, y 6.590 | [probe] |
| **Camera body / lens boss** | **4.050 × 3.750** at x 8.390, y 7.080 | [probe] |
| ⇒ camera axis | ≈ **x 10.4, y 8.9** from the board corner | [probe] derived: ~2.5 mm inboard of one long edge, 8.9 mm from the near short edge — **the window anchor** |
| Bottom-side pad grid | 8 × 1.2 mm pads, 2 cols × 4 rows, 2.54 pitch, at x 7.02 / 9.56, y 11.02…18.64 | [probe] the main-board↔expansion mating pattern (§5.2) |
| Connector-shaped strips | 11.45 × 0.71 at y 13.84; 11.80 × 0.51 at y 3.44 | [probe] **identify on the real board (M7) before cutting the SD slot** |

### 2d. Connector / display / module data

| Part | Value | Source | Confidence |
|---|---|---|---|
| USB-C receptacle body | 8.942 × 7.300 × **4.200 mm** | [probe] one STEP solid; 8.94 × 7.30 is the standard USB-C footprint, 4.2 = shell + SMT pegs | high |
| OLED **glass** (0.91", 128×32) | panel 30.00 × 11.50 × **1.45**; **active 22.384 × 5.584**; pitch 0.175; 1/32 duty; I2C `0x3C` | panel-maker spec quoted verbatim by Adafruit (#4440) for this glass | high (spec) |
| OLED **4-pin carrier PCB** | ~38 × 12 mm (seller-dependent, and more than one 4-pin pinout exists) | seller listings | **UNVERIFIED → M1** |
| Camera module | **OV3660** (locked, §5.3) | Seeed wiki: "the OV2640 camera has been discontinued" | high |
| Li-Po 302030 | 3.0 × 20 × 30 (cells also swell) | part-number convention | **UNVERIFIED → M10** |
| Accel breakout | ~21 × 16 × 2.5 (must be MPU-register class or `imu_whoami.h` refuses it) | GY-521/HW-123 class | **UNVERIFIED → M9** |
| Tactile button | 6 × 6 mm body, ~5 mm actuator | standard part | **UNVERIFIED → M11** |

## 3. What the vendor files actually are (and their limits)

`cad/vendor/seeed/` holds Seeed's own mechanical assets (origin URLs and
re-download commands in `SOURCE.md`). Read with `scripts/cad_probe.py`:

| File | What it really is | Usable for |
|---|---|---|
| `XIAO_ESP32S3_v1.1_Dimensioning.dxf` | 7486 entities, one view, 3403 connected components | §2a — the board outline and pin rows |
| `Sense_TOP.dxf` / `Sense_BOTTOM.dxf` | **panel sheets** (95 × 25 mm) containing two board copies at (139.61, −115.58) | §2c — the assembly, in board-relative coords |
| `Sense_ExpBoard_top.dxf`, `_bot.dxf` | mechanical-only exports (17.78 × 15.37 outline) | §2b |
| `3d/Seeed Studio XIAO-ESP32-S3-Sense.step` | 116 872 entities, **97 solids, 41 assembly placements** (`NEXT_ASSEMBLY_USAGE_OCCURRENCE` + `ITEM_DEFINED_TRANSFORMATION`) | part **sizes** only (e.g. the USB-C shell) |
| `sense-housing-top.stp`, `sense-housing-bottom.stp` | 1 solid each, but the solids carry reference geometry out at ±40.0 / ±45.95 mm | Seeed's own shell: **not** a usable envelope. The earlier "22.2 × 15.3 × 11 mm" cluster reading was a heuristic artefact — do not design against it |

Consequences, stated plainly:

- **Part sizes are trustworthy from the STEP; positions are not.** With 41
  assembly placements, a raw coordinate bbox is a valid size only for parts
  whose rotation happens to be identity. Positions come from the DXFs (2D, no
  transforms) or from calipers.
- Nothing in this repo can *view* the STEP today (no FreeCAD, no `pythonocc`,
  no `trimesh`; pip is PEP-668-blocked except for pure-python wheels — `ezdxf`
  works). Resolving the 41 transforms is optional future work; it is **not** on
  the critical path, because the case needs measured Z, not placed Z.
- Reproduce everything: `python3 scripts/cad_probe.py dxf <file.dxf>` /
  `... step <file.stp>`. If a number in §2 cannot be reproduced this way, treat
  it as wrong.

## 4. Tolerances (the part every printed case gets wrong)

Printer/material assumptions are stated, not implied: **FDM, 0.4 mm nozzle,
PLA/PETG, 0.2 mm layers**. These are working defaults for the first print; the
*gate* is a fit coupon (§7 step 2), not belief.

| Interface | Nominal | Value | Why |
|---|---|---|---|
| PCB in pocket | boards vary ±0.1 mm, solder blobs | **+0.20 mm per side** | 0.4 mm total play: snug, still assemblable by hand |
| Board thickness in a slot | 1.6 mm PCB | slot **1.75 mm** | solder wicks + HASL add height |
| Display window vs **active area** | active 22.384 × 5.584 | **active + 0.3 mm per side** (→ 22.98 × 6.18) | hides the bezel, never clips pixels |
| Panel recess depth | glass 1.45 mm | **1.6 mm** + 0.2 mm foam/tape allowance | protects the glass, sits flush-ish |
| OLED carrier pocket | 4-pin carrier + 4 solder blobs | per M1/M2, +0.2 mm per side | the carrier, not the MCU, sets the footprint |
| Camera window | lens barrel Ø (M8) | barrel **+0.4 mm**, 1.5 mm wall around it | the lens must not see the print's edge |
| microSD opening | card 11.0 × 1.0 (M7) | card **+0.6 mm wide, +0.3 mm high** + 0.5 mm lead-in chamfer | a tight slot jams the card; a loose one lets it fall out |
| Snap hook engagement | radial | **0.5–0.8 mm**, beam 1.5–2.0 mm | PETG beams snap twice, PLA once |
| Press-fit (no screws) | interference | **−0.10 to −0.15 mm** | only for parts meant to stay put |
| Self-tapping M2 | Seeed's boss Ø2.41 | pilot **Ø1.6 (PLA) / Ø1.7 (PETG)**, wall ≥2.0 | reuses Seeed's own boss geometry |
| Wall thickness | body | **2.0 mm** (min 1.6) | Seeed's shell measures ~2.0–2.4 |
| Floor under battery | body | **1.2 mm** | weight + drop |
| USB-C plug cutout | receptacle 8.942 × 7.300 × 4.200 | opening **9.4 × 3.8 mm**, 0.3 mm chamfer | plugs have an overmould; a tight cutout blocks the cable |
| Button travel hole | cap Ø4.2 (M11) | **Ø4.4 mm** + 0.5 mm counterbore | caps rub and stick otherwise |
| Antenna keep-out | XIAO antenna end | **no metal/battery within ~10 mm**, Li-Po on the opposite half | a pouch next to the antenna kills BLE range silently |
| Lanyard/clip slot | — | 3.0 × 1.5 mm, ≥1.6 mm wall around it | printed loops delaminate under load |

## 5. Locked decisions (2026-09-28) and what each forces

The six blockers from the first revision of this doc, answered:

1. **Display = 128×32, 4-pin carrier** (not the Adafruit STEMMA board) → the
   carrier PCB (~38 × 12 mm) is the longest and most seller-variable part.
   Pocket it from the *measured* carrier (M1/M2), key the window to the glass
   active area (22.984 × 6.184 with the §4 allowance), and clear the four
   solder blobs (+0.4 mm depth). If the carrier ever changes, only M1/M2 change.
2. **Accel stacked below the XIAO stack** → 4-layer Z: display / XIAO+expansion /
   accel / Li-Po. Z is dominated by the *mating* between the XIAO and its
   expansion board, which the vendor files do **not** fix: 2.54 female headers
   mate at ~8.5 mm, soldered castellated pads (or a low-profile board-to-board
   mate) at ~3.0–3.5 mm. That is a **5–5.5 mm swing on the case height** — the
   biggest lever in this build. See §5.2.
3. **Camera = OV3660** → window Ø = lens barrel + 0.4 mm (M8), anchored at the
   §2c camera axis (x 10.4, y 8.9 board-relative). The camera sits on the
   *expansion* board, i.e. on the opposite face from the display — for a chest
   pendant that is exactly right (display toward the wearer, camera away).
   Confirm the camera FPC length before assuming the module can be re-routed
   to the other face (M13).
4. **microSD usable while cased** → card opening in a side wall, aligned with
   the socket mouth: 11.6 × 1.3 mm + 0.5 mm chamfer (§4) plus a fingernail
   relief. Which of the two §2c connector strips is the socket gets decided by
   M7; the wall and the socket must line up within ±0.3 mm or the card scrapes.
5. **USB-C reachable with the lid on, Li-Po off the antenna half** → one end
   wall gets the 9.4 × 3.8 mm opening; the antenna end stays empty (keep-out,
   §4) and the Li-Po sits at the opposite end (M14 confirms which short edge
   carries the antenna).
6. **First-article material** — answered "yes" to a PLA-or-PETG question; read
   as **PLA first** (dimensionally predictable, so coupon numbers transfer),
   PETG only if the coupon shows PLA snap hooks fail after one cycle. This is
   an interpretation of a one-word answer — say so if you meant PETG first.

### 5.1 Envelope first (before any CAD)

Floor plan = the largest part per axis, from §2 and M1…M14:

| Layer | Parts | Footprint driver |
|---|---|---|
| Front (wearer side) | OLED carrier 38 × 12 | **38 mm** |
| Middle | XIAO + expansion 17.79 × 21.14 + mating | 21.14 mm |
| Back 1 | accel ~21 × 16 | 21 mm |
| Back 2 | Li-Po 30 × 20 | 30 mm |

The battery (30 mm) and the display (38 mm) cannot share a layer, and the
battery must stay away from the antenna → battery under the display band, accel
beside the board. With 2.0 mm walls and 0.4 mm pocket play:

- **case ≈ 42.40 × 25.55 mm** footprint (inner pocket 38.40 × 21.55);
  Z ≈ **25.60 mm** with 2.54 header mating, **20.30 mm** with a soldered
  low-profile mate — a **5.30 mm swing from one decision**.

These are no longer hand-written: `python3 scripts/cad_params.py envelope`
computes them from `cad/params.yaml` and prints every UNVERIFIED input they
depend on (16 today). Run it before quoting anything from this section — the
first revision of this doc guessed "42 × 26 mm / Z 14–20 mm", 5 mm adrift.

Levers if that is too fat, in order of payoff: (a) mate without headers
(−5.30 mm); (b) drop the carrier and pocket a bare 30 × 11.5 mm COG panel
(−8 mm length, −1.5 mm Z, needs a short flex); (c) thinner Li-Po (302020);
(d) move the accel onto the board's own back face.

### 5.2 Decision needed before modelling

Mate hardware: 2.54 mm female header (hand-assembled, tall) **or** soldered
castellated pads (short, but the expansion board becomes permanent). Pick from
M6: firmware flashing goes over USB-C, so the camera board never needs to come
off — which argues for the soldered/low-profile mate and the slimmer case.

## 6. Caliper sheet (fill before any CAD)

One sitting with digital calipers (~30 min) closes the case. Values go straight
into §2 with the row's UNVERIFIED tag removed and the date added.

| # | Measure | Blocks |
|---|---|---|
| M1 | 4-pin OLED carrier: L × W × T (PCB only) | the pocket footprint — the dominant part |
| M2 | glass position on the carrier (offset from each edge) + pin/solder-blob height behind it | window centring; carrier pocket depth |
| M3 | dark bezel width around the glass active area | whether +0.3 mm/side (§4) hides it or clips |
| M4 | XIAO: pad-row centre distance across the board; board W across the pad columns | the retention scheme (§2a says "flush pads, no holes") |
| M5 | XIAO board thickness; expansion-board thickness | slot height (1.75 mm default) |
| M6 | **XIAO↔expansion board mated height** (pin to pin, headers installed) + which mate hardware is fitted | **case Z and §5.2** — the biggest number in the build |
| M7 | microSD socket: mouth position relative to the board edge, and card thickness | the card opening's X/Y in the wall |
| M8 | camera: lens barrel OD, protrusion above the expansion board, FPC length | window Ø and whether the module can be re-routed (M13) |
| M9 | accel breakout: L × W × T and which face carries the pads | accel layer Z |
| M10 | Li-Po: L × W × T + wire exit side | base layer; swelling allowance |
| M11 | button: cap OD, actuator height, travel | Ø4.4 hole + counterbore |
| M12 | how the button is mounted (soldered pad / flying lead) and its height above the board | button boss + lid clearance |
| M13 | camera FPC: total free length from the connector | re-route feasibility |
| M14 | which short edge of the XIAO carries the antenna; distance from the antenna to the nearest metal part in the current build | the keep-out side of the case |

## 7. Redesign plan (gated — no step starts before the previous gate passes)

1. **Fill §6.** No CAD before every UNVERIFIED row in §2 has a caliper number.
2. **Fit coupon — DONE (2026-09-28).** `cad/fit_coupon.scad` (every dimension
   pulled from `cad/params.yaml`) builds `cad/stl/fit_coupon.stl`: 5 pocket
   gaps, 3 PCB-edge slots, 3 M2 pilots, 3 USB-C openings, 3 microSD openings
   and a slide-in snap latch (arm, engagement, detent), with raised index dots.
   ~13.3 g PLA, ~1 h, no supports, loose parts printed beside the plate.
   **Verified numerically, not by eye** — `scripts/cad_params.py section` reads
   the built mesh back at z = 3.5: pockets **8.10 / 8.15 / 8.20 / 8.25 / 8.30
   × 13.00**, PCB slots **1.60 / 1.75 / 1.90**, pilots **Ø1.60 / 1.70 / 1.80**,
   latch detent **3.00 × 2.00**, and at their own heights the USB-C opening
   **9.20** and the card opening **11.40**. `check` reports 3 bodies, all
   watertight. **Print it, then record the winner of each set here.**
3. **One parameter source — DONE (2026-09-28).** `cad/params.yaml` is the only
   place a case dimension is written down; every value carries a provenance tag
   (PROBED / SPEC / DEFAULT / UNVERIFIED + the M-number that will replace it).
   `scripts/cad_params.py generate` writes `cad/params.scad` for OpenSCAD, so a
   model and a check cannot disagree. The 52 legacy artefacts move to
   `cad/legacy/` in step 5's commit, when their replacement actually exists —
   moving them now would leave the repo with no geometry at all.
4. **Decide §5.2** (mate hardware) and record the reasoning here.
5. **Model one variant** — the MVP pendant only: camera window anchored at
   §2c's axis, card opening, USB-C opening, antenna keep-out, button boss.
   No STL/`.blend` is committed as "final".
6. **Print the body, fit the real parts, iterate.** Only after a physical fit:
   regenerate STL previews and update `docs/30-schematics-xiao.md`.
7. **Gate to close this doc:** a printed case that (a) closes without force,
   (b) reads the HUD through the window without clipping pixels, (c) takes a
   microSD card with the lid on, (d) charges over USB-C with the lid on, and
   (e) keeps BLE range (a walk test with the battery strapped in place).

Until step 6, any dimension in `cad/` is a proposal; §2 + §6 are the truth.

### 7.1 Toolchain (no distro CAD package on this box, no sudo)

- `scripts/get_openscad.sh` extracts the official OpenSCAD **2021.01** AppImage
  into `~/.local/share/openscad-appimage/` — no FUSE, no root:
  `OS=~/.local/share/openscad-appimage/squashfs-root/AppRun`
  `$OS --export-format binstl -o cad/stl/fit_coupon.stl cad/fit_coupon.scad`
- **Gotcha:** this build rejects the quoted include form. `include "params.scad"`
  fails with `Parser error: syntax error`; `include <params.scad>` works (the
  search path includes the main file's directory, so a sibling resolves).
- `scripts/cad_params.py` needs `pyyaml`; `check` and `section` need `trimesh`:
  `python3 -m pip install --user --break-system-packages pyyaml trimesh`
- **Manifold discipline** (learned by building this coupon): CGAL turns
  face-to-face contact into non-manifold edges. Every solid added to another
  must *interpenetrate* by ≥0.2 mm — dots, bosses, walls, rails, the latch arm
  into its handle, the nib into the arm. Symptom when you forget: `ERROR: The
  given mesh is not closed`, or `WARNING: Object may not be a valid
  2-manifold`, plus one edge with four faces (find it by counting edge uses).




