# docs/44 — Case redesign: dimensions & tolerances FIRST

Status: **research only (2026-09-28)**. No CAD is rewritten yet. Premise under
test: every existing blender / OpenSCAD / FreeCAD model is suspect. This doc is
the evidence base the redesign must be built on, with a source for every number
and an explicit "UNVERIFIED" wherever the source is a vendor listing rather than
a measurement on the actual part.

## 0. Why the current models cannot be trusted

Enclosure geometry only works if the *parts* are right. Grepping the committed
`.scad` files shows the opposite — the same physical component has different
sizes in different files, and one panel is simply the wrong part:

| Constant | File(s) | Value | Verdict |
|---|---|---|---|
| `screen_w` / `screen_h` | variant files | 35.0 / 36.0 | **wrong** — implies a square ~36 mm panel; the MVP display is a 128×32 0.91" part whose **active area is 22.384 × 5.584 mm** |
| `screen_glass` | `cyclops_xiao_enclosure_v2.scad` | 28.0 | **wrong** — labelled "ST7735 visible glass", but the MVP build is I2C SSD1306 128×32 |
| `win` (window reveal) | v2 | 24.0 | derived from the wrong panel; no tolerance note |
| `imu_l/w/h` | variant files | 20.0 / 15.0 / 2.5 | plausible for a GY-521-class breakout, **unverified** |
| `imu_w/h` (other file) | variants | 22 / 17 | **contradicts** the above — one part, two sizes |
| `batt_l/w/h` | v2 | 30.0 / 20.0 / 3.0 | 302030 Li-Po by part-number convention; **unverified** |
| `xiao_l/w` | v2 | 21.0 / 17.5 | matches the published board size; confirm from the vendor STEP/DXF |
| `btn_r` / `btn_d` | v2 | 6.5 / 4.2 | 6×6 mm tactile + 4.2 mm cap; **unverified** |

Also missing entirely from the models: camera + lens clearance and the SD slot
(reachable only with the expansion board *removed*), the USB-C plug-shell
cutout tolerance, the antenna keep-out, and any tolerance stack. A lid that
"fits" in the viewport is meaningless if the pocket is 2 mm short in Z.

## 1. Parts under design (MVP BOM, docs/43 §1)

| # | Part | Function | Qty |
|---|---|---|---|
| 1 | XIAO ESP32-S3 **Sense** (main board + camera expansion board) | compute, BLE, mic, cam, SD, USB-C, charger | 1 |
| 2 | SSD1306 **128×32** I2C OLED module (glass panel + carrier PCB) | the 4-row HUD | 1 |
| 3 | MPU-class accelerometer breakout (HW-123 / GY-521 class, `0x68`) | tilt / gestures / presence / posture | 1 |
| 4 | Li-Po 302030 (≈3.0 × 20 × 30 mm) | untethered power | 1 |
| 5 | Tactile button + cap (6×6 mm class) | the single input | 1 |
| 6 | Lanyard / clip attachment, M2 screws (×4 in Seeed's own shell) | mounting | 1 set |

## 2. Verified / derived dimensions

| Part | Dimension | Value | Source | Confidence |
|---|---|---|---|---|
| OLED panel (bare glass) | panel size | 30.00 × 11.50 × **1.45** mm | Adafruit #4440 datasheet block (panel vendor spec) | high (spec) |
| OLED panel | **active area** | **22.384 × 5.584** mm | same | high (spec) |
| OLED panel | pixel pitch / pixel | 0.175 / 0.159 mm | same | high (spec) |
| OLED panel | module size (incl. flex) | 46.30 × 11.50 × 1.45 mm | same | medium (module ≠ carrier) |
| OLED **carrier PCB** (Adafruit variant) | board | 35 × 20 × 4 mm | same page, "Dimensions" | **low — that page also claims a 7×25 mm display area, contradicting its own active-area line. Vendor listings lie; measure.** |
| Generic 4-pin 0.91" carrier (the cheap blue PCB in `docs/15-mini4.md`) | board | ~38 × 12 mm (varies by seller) | seller listings | **UNVERIFIED — measure the unit you own** |
| XIAO ESP32-S3 board | board | 21 × 17.5 mm | `docs/30-schematics-xiao.md`, vendor wiki | medium (published, not measured) |
| XIAO Sense assembly | stacked main + camera expansion board; camera/flex protrude; USB-C on the short edge | vendor STEP body cluster ≈ **28.6 × 15.0 × 28.6 mm** (contains the USB shell + screw bosses → *not* a clean board measurement) | `cad/vendor/seeed/3d/*.step`, grid-cluster heuristic | **low — needs a real STEP viewer. Do not CAD against it yet.** |
| Seeed's own 3D-printable **housing** (top + bottom) | 4 screw bosses **2.41 mm** square × 5.51 mm tall, centres **19.8 mm (X) × 12.9 mm (Y)**; wall segments 22.18 × 7.97 × 9.03 mm; envelope ≈ **22.2 × 15.3 × ~11 mm** | `cad/vendor/seeed/sense-housing-*.stp` | medium (derived, same heuristic) |
| Li-Po 302030 | 3.0 × 20 × 30 mm | part-number convention | **UNVERIFIED — measure (±0.3 mm, cells swell)** |
| Tactile button | 6×6 mm body, ~5 mm actuator (class) | standard part | **UNVERIFIED — measure** |
| GY-521-class accel breakout | ~21 × 16 mm, 2×4 header @2.54 mm | widely published | **UNVERIFIED — measure; and confirm which part is on the bench (`imu_whoami.h` refuses non-MPU)** |

**Stack-up consequence:** XIAO (21 × 17.5) + OLED carrier (≈38 × 12) + accel
(≈21 × 16) + Li-Po (30 × 20) **cannot** share one 22 × 15 × 11 mm shell —
Seeed's shell is deliberately board-only. A pendant that shows the HUD needs a
**≈45 × 25 mm footprint (flat stack) or ≈45 × 35 mm if the accel is not stacked
onto the XIAO**, or a two-layer arrangement. That is the first decision the
redesign must make, and it is a *product* decision, not a CAD knob. The
dominant part is the OLED carrier, not the MCU.

## 3. Vendor reference geometry (downloaded, in-repo)

`cad/vendor/seeed/` — Seeed's own mechanical assets (origin URLs in `SOURCE.md`):

| File | Use |
|---|---|
| `XIAO_ESP32S3_v1.1_Dimensioning.dxf` | board 2D dims |
| `Sense_TOP.dxf`, `Sense_BOTTOM.dxf` | Sense 2D dims, top/bottom |
| `Sense_ExpBoard_top.dxf`, `Sense_ExpBoard_bot.dxf` | **camera/mic/SD expansion board** 2D dims (the part that eats the pocket) |
| `3d/…-Sense.step` | 3D assembly — the shape to design around |
| `sense-housing-top.stp`, `sense-housing-bottom.stp` | Seeed's own 3D-printable shell — their clearances are a usable reference |

Honest limits: these files contain **multiple bodies/views laid out side by
side**, so a naive bounding box measures the sheet, not the part (first pass:
123 × 27 mm for a DXF view, 43 × 23.7 × 28.6 mm for the STEP). The per-body
numbers in §2 come from a grid-cluster heuristic — good enough to plan, **not**
good enough to cut plastic.

**Prerequisite for the redesign:** install a real STEP/DXF viewer on this box
(FreeCAD, or `pythonocc`/`trimesh`), then re-derive every number per solid.
Neither is installed today (`which freecad` → nothing; `import OCC` → ImportError).

**Second finding from the vendor wiki, upstream of any CAD:** newer Sense boards
ship an **OV3660** camera, not OV2640 (Seeed: "the OV2640 camera has been
discontinued"). Window/clearance design and the firmware sensor init both depend
on which module is on the board — check the physical part before modelling.

## 4. Tolerances (the part every printed case gets wrong)

Printer/material assumptions are stated, not implied: **FDM, 0.4 mm nozzle,
PLA/PETG, 0.2 mm layers**. The numbers are the working defaults for the first
print; the *gate* is a fit coupon, not belief.

| Interface | Nominal | Value | Why |
|---|---|---|---|
| Sliding pocket clearance (board into pocket) | per side | **+0.20 mm** (0.15 tight → 0.30 loose) | FDM XY error ≈ ±0.1 mm; tighter cracks walls |
| PCB thickness allowance | per board | 1.6 mm nominal → **1.75 mm pocket** | boards vary ±0.1 mm, solder blobs |
| Display window vs **active area** | active + | **+0.3 mm per side** | hide the panel bezel, never clip pixels |
| Panel recess depth | glass 1.45 | **1.6 mm** + 0.2 mm tape/foam allowance | protects the glass, stays flush-ish |
| Snap hook engagement | radial | **0.5–0.8 mm**, beam 1.5–2.0 mm thick | PETG beams snap twice, PLA once |
| Press-fit (no screws) | interference | **−0.10 to −0.15 mm** | only for parts meant to stay put |
| Self-tapping M2 screw | pilot hole | **Ø1.6 mm (PLA) / Ø1.7 mm (PETG)** | Seeed's own boss is 2.41 mm → ~2 mm wall around a Ø1.6 pilot |
| Wall thickness | body | **2.0 mm** (min 1.6) | Seeed's shell measures ~2.0–2.4 mm |
| Floor under battery | body | **1.2 mm** | weight + drop |
| USB-C plug cutout | receptacle ≈ 8.94 × 3.26 | **9.4 × 3.8 mm**, +0.3 mm chamfer | plugs have overmould; a tight cutout blocks the cable |
| Button travel hole | cap Ø4.2 | **Ø4.4 mm** + 0.5 mm counterbore | caps rub and stick otherwise |
| Antenna keep-out | XIAO antenna end | **no metal/battery within ~10 mm**; battery on the opposite half | BLE range dies silently next to a Li-Po pouch — and this is why a metal case was never an option here |
| Lanyard/clip slot | — | 3.0 × 1.5 mm, ≥1.6 mm wall around it | printed loops delaminate under load |

**Mandatory first artefact: a fit coupon, not the case.** One ~30-minute print
with gaps 0.10/0.15/0.20/0.25/0.30 mm, a Ø1.6/1.7/1.8 pilot trio, a snap hook,
and USB-C cutouts at 9.2/9.4/9.6 mm. Every value above is confirmed or corrected
against that print *before* the enclosure is modelled.

## 5. Redesign plan (after the coupon)

1. **Measure the real parts** (calipers, 3 samples where possible): OLED carrier
   + panel active area, XIAO stack height with the expansion board, accel board,
   Li-Po (incl. swelling allowance), button cap, USB-C plug shell. Record the
   numbers in this doc's §2 table, replacing every UNVERIFIED row.
2. **Install a viewer** (FreeCAD or pythonocc) and re-derive the vendor
   DXF/STEP per solid; keep the derived numbers next to the measured ones.
3. **Freeze a single parameter source** — one `cad/params.scad` (or
   `params.yaml` consumed by both the SCAD and `cad/freecad/build_pendant.py`)
   so the disagreeing constants in §0 can never recur. Variants then differ only
   by the parameters they include.
4. **Pick the arrangement** (flat stack ≈45 × 25 mm vs two-layer ≈45 × 35 mm) —
   a product decision, recorded here with the reasoning, before any modelling.
5. **Model one variant only** (the MVP pendant), in the parametrized source,
   with the antenna keep-out and the camera/SD access explicitly designed.
6. **Gate:** print the coupon → print the body → *fit the real parts* → only then
   regenerate STL previews and update `docs/30-schematics-xiao.md`.
   No STL/`.blend` is committed as "final" before a physical fit.

## 6. Open questions (blockers, in order)

1. Which OLED carrier is actually on the bench — the Adafruit-style 35 × 20 mm
   or the cheap 4-pin ~38 × 12 mm? (Determines the footprint.)
2. Is the accel stacked on the XIAO or on the pocket floor? (Determines Z.)
3. Camera: OV2640 or the newer OV3660 Sense revision? (Window + firmware.)
4. Is the SD slot expected to be usable while cased (needs an opening), or only
   for `/cyclops.log` with the camera board removed?
5. Charging while cased: USB-C must be reachable with the lid on (and the Li-Po
   must not sit against the antenna half).
6. Print material for the first article: PLA (dimensionally predictable) or PETG
   (snap-fit toughness) — the tolerance table assumes either, but the coupon
   decides which numbers ship.
