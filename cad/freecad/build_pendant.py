"""
Cyclops Pendant V4 — 128×32 OLED + PSP thumbstick + 8mm button + XIAO + LiPo
=============================================================================
Parametric FreeCAD script. Run:
    freecadcmd build_pendant.py

Coordinate system (same as original pendant):
    Z=0   = back face  (cap seats here)
    Z=T   = front face (OLED window, joystick, button)
    +X    = right      (USB-C on right side)
    Y     = vertical   (bail ring at +Y, bottom bulge at -Y)

LAYER STACK (back → front):
    Z 0..1.6     back floor (cap_t)
    Z 1.6..14    hollow cavity
    Z 14..16     front wall  (wall=2mm)

COMPONENT PLACEMENT (front view, XY plane):
    Y+38         bail ring
    Y+25..33     neck (r=8mm)
    Y-3          128×32 OLED window  (26×8mm glass, front face)
    Y-13         8mm screw-on button  (Ø8 hole + Ø12 body recess)
    Y-22         PSP thumbstick       (Ø6 shaft + 20mm body pocket)
    Y-22..-44    bulge (r=22mm)
    X=+9..+15    USB-C slot           (right side, ~Y+10)
"""

import FreeCAD, Part, math, json, os
from FreeCAD import Vector

doc = FreeCAD.newDocument("CyclopsPendant")

# ═══════════════════════════════════════════════════════════════
# PARAMETERS  (all mm)
# ═══════════════════════════════════════════════════════════════
T     = 16.0    # total thickness
wall  = 2.0     # shell wall
cap_t = 1.6     # back-floor thickness for cap to seat on
lip_h = 1.6     # seating lip height

# ── teardrop outline ──────────────────────────────────────────
# bottom (bulge) circle
y1 = -22.0;  R1 = 22.0
# top (neck) circle
y2 =  25.0;  R2 =  8.0

# ── components (positions from original pendant, adapted) ─────
# OLED 128x32 0.91" SSD1306  — PCB 30×11.5×3mm, glass ~26×8
oled_win_w = 26.0;  oled_win_l = 8.0   # visible glass
oled_pcb_w = 30.0;  oled_pcb_l = 11.5; oled_pcb_t = 1.6
oled_cy    = -3.0                       # centre Y

# PSP 1000 thumbstick — 19×19×9mm body, 4 bottom pads, Ø~8 shaft
joy_body   = 20.0;   joy_body_h = 8.0   # body pocket (2mm slack)
joy_shaft_d = 6.0                       # shaft hole through front wall
joy_cy     = -22.0                      # centre Y (at bulge centre)

# 8mm screw-on anti-vandal button — Ø8 thread, Ø12 body, ~9 deep
btn_d      = 8.0;   btn_body_d = 14.0;  btn_body_h = 9.0
btn_cy     = -13.0

# XIAO ESP32-S3 Sense — 21×17.5×6mm
xiao_l = 21.0; xiao_w = 17.5; xiao_h = 6.0
xiao_cx = 0.0; xiao_cy = 1.0

# Standoff positions (4 corners of the XIAO board)
_soff_pts = []
for _deg in [45, 135, 225, 315]:
    _r = math.radians(_deg)
    _soff_pts.append((9*math.cos(_r), 1 + 9*math.sin(_r)))

# Battery LiPo 302030 — 30×20×3mm
batt_l = 30.0; batt_w = 20.0; batt_h = 3.0
batt_cx = 0.0; batt_cy = -20.0

# IMU GY-521 (optional) — 20×15×2.5
imu_l = 20.0; imu_w = 15.0; imu_h = 2.5

# USB-C (right side)
usb_w = 9.0; usb_h = 3.5; usb_y = 10.0

# Bail ring
bail_y = y2 + R2 + 8;  bail_R = 5.0;  bail_r = 1.6

# ═══════════════════════════════════════════════════════════════
# HELPERS  —  teardrop profile generator
# ═══════════════════════════════════════════════════════════════
def make_teardrop_face(R1_, R2_, y1_=None, y2_=None):
    """Return a planar Face of the teardrop convex-hull of two circles.
    Circles at (0, y1) R1 and (0, y2) R2.  Result face lies at Z=0."""
    yy1 = y1_ if y1_ is not None else y1
    yy2 = y2_ if y2_ is not None else y2
    aa  = math.asin((R1_ - R2_) / (yy2 - yy1))
    caa = math.cos(aa);  saa = math.sin(aa)

    # Tangent points
    p_r = [Vector( R1_*caa, yy1 + R1_*saa, 0),
           Vector( R2_*caa, yy2 + R2_*saa, 0)]
    p_l = [Vector(-R1_*caa, yy1 + R1_*saa, 0),
           Vector(-R2_*caa, yy2 + R2_*saa, 0)]

    # Arcs: bottom (C1) ccw π-α→2π+α reversed; top (C2) ccw α→π-α reversed
    c1 = Part.Circle(Vector(0, yy1, 0), Vector(0,0,1), R1_)
    c2 = Part.Circle(Vector(0, yy2, 0), Vector(0,0,1), R2_)

    ab = Part.ArcOfCircle(c1, math.pi-aa, 2*math.pi+aa).toShape()
    ab.reverse()
    at = Part.ArcOfCircle(c2, aa, math.pi-aa).toShape()
    at.reverse()

    wire = Part.Wire([ab,
                      Part.LineSegment(p_l[0], p_l[1]).toShape(),
                      at,
                      Part.LineSegment(p_r[1], p_r[0]).toShape()])
    return Part.Face(wire)

# ═══════════════════════════════════════════════════════════════
# 1 — BODY
# ═══════════════════════════════════════════════════════════════
outer_face = make_teardrop_face(R1, R2)
body_solid = outer_face.extrude(Vector(0, 0, T))
doc.addObject("Part::Feature", "Body_raw").Shape = body_solid

# Bail ring (torus)
bail = Part.makeTorus(bail_R, bail_r, Vector(0, bail_y, T/2))
bo = doc.addObject("Part::Feature", "Bail_raw")
bo.Shape = bail
body_bail = body_solid.fuse(bail)
doc.addObject("Part::Feature", "Body_bail").Shape = body_bail

# ═══════════════════════════════════════════════════════════════
# 2 — HOLLOW  (offset inward by wall → 2mm side walls)
# ═══════════════════════════════════════════════════════════════
inner_face = make_teardrop_face(R1 - wall, R2 - wall)
inner_face.translate(Vector(0, 0, cap_t))
inner_solid = inner_face.extrude(Vector(0, 0, T - cap_t - wall))
doc.addObject("Part::Feature", "Hollow_tool").Shape = inner_solid

shell = body_bail.cut(inner_solid)
print(f"INFO: shell vol={shell.Volume:.0f}mm3")
doc.addObject("Part::Feature", "Shell").Shape = shell

# ═══════════════════════════════════════════════════════════════
# 3 — COMPONENT POCKETS  (all subtracted from the shell)
# ═══════════════════════════════════════════════════════════════
cut_parts = []

def add_cut(name, shape):
    o = doc.addObject("Part::Feature", name)
    o.Shape = shape
    cut_parts.append(shape)

# Battery  (sits on back floor, z=cap_t … )
add_cut("P_Batt",
    Part.makeBox(batt_l+1.5, batt_w+1.5, batt_h+1,
                 Vector(batt_cx-(batt_l+1.5)/2, batt_cy-(batt_w+1.5)/2, cap_t-0.2)))

# XIAO  (above battery)
add_cut("P_Xiao",
    Part.makeBox(xiao_l+1.5, xiao_w+1.5, xiao_h+0.5,
                 Vector(xiao_cx-(xiao_l+1.5)/2, xiao_cy-(xiao_w+1.5)/2, cap_t+4.0)))

# IMU
add_cut("P_Imu",
    Part.makeBox(22, 17, 3.5, Vector(-11, 3-8.5, cap_t+8.3)))

# OLED window  (through front wall, z=T-wall-0.5 to T+1)
add_cut("P_OledWin",
    Part.makeBox(oled_win_w, oled_win_l, wall+1.5,
                 Vector(-oled_win_w/2, oled_cy-oled_win_l/2, T-wall-0.5)))

# OLED PCB recess  (seat pocket behind front wall)
add_cut("P_OledSeat",
    Part.makeBox(oled_pcb_w+1, oled_pcb_l+1, oled_pcb_t+1,
                 Vector(-(oled_pcb_w+1)/2, oled_cy-(oled_pcb_l+1)/2, T-wall-1.5)))

# Joystick shaft hole  (through front wall)
add_cut("P_JoyShaft",
    Part.makeCylinder(joy_shaft_d/2, wall+2,
                      Vector(0, joy_cy, T-wall-1), Vector(0,0,1)))

# Joystick body pocket  (behind front wall)
add_cut("P_JoyBody",
    Part.makeBox(joy_body, joy_body, joy_body_h,
                 Vector(-joy_body/2, joy_cy-joy_body/2, T-wall-joy_body_h)))

# 8mm button hole
add_cut("P_BtnHole",
    Part.makeCylinder(btn_d/2, wall+2,
                      Vector(0, btn_cy, T-wall-1), Vector(0,0,1)))

# 8mm button body recess
add_cut("P_BtnBody",
    Part.makeBox(btn_body_d, btn_body_d, btn_body_h,
                 Vector(-btn_body_d/2, btn_cy-btn_body_d/2, T-wall-btn_body_h)))

# USB-C rounded slot  (right side, -X direction)
usb_z = T - 4.0
# Compute tangent line from outer-face parameters
_aa = math.asin((R1 - R2) / (y2 - y1))
_caa = math.cos(_aa); _saa = math.sin(_aa)
_tx1 = R1*_caa;  _ty1 = y1 + R1*_saa
_tx2 = R2*_caa;  _ty2 = y2 + R2*_saa
if abs(_ty2 - _ty1) > 0.01:
    _slope = (_tx2 - _tx1) / (_ty2 - _ty1)
    _x_wall = _tx1 + (usb_y - _ty1) * _slope
else:
    _x_wall = _tx1
usb_x0 = _x_wall + 3
usb_len = wall + 8
for _sy in [-1, 1]:
    add_cut(f"P_UsbCyl_{_sy}",
        Part.makeCylinder(usb_h/2, usb_len,
            Vector(usb_x0, usb_y+_sy*(usb_w-usb_h)/2, usb_z), Vector(-1,0,0)))
add_cut("P_UsbFill",
    Part.makeBox(usb_w-usb_h, usb_h, usb_len,
                 Vector(usb_x0, usb_y-usb_h/2, usb_z)))

# ═══════════════════════════════════════════════════════════════
# 4 — BOOLEAN CUT: shell − all pockets
# ═══════════════════════════════════════════════════════════════
result = shell
for i, cp in enumerate(cut_parts):
    try:
        result = result.cut(cp)
    except Exception as e:
        print(f"WARN: cut #{i} failed: {e}")

print(f"INFO: body after cuts vol={result.Volume:.0f}mm3")
doc.addObject("Part::Feature", "Body").Shape = result

# ═══════════════════════════════════════════════════════════════
# 5 — XIAO STANDOFFS  (add material: M2 columns from back floor)
# ═══════════════════════════════════════════════════════════════
standoff_h = cap_t + 4.0 + xiao_h + 0.5  # to support XIAO at proper height
standoffs = []
for _sx, _sy in _soff_pts:
    so = Part.makeCylinder(1.6, standoff_h,
                           Vector(_sx, _sy, 0), Vector(0,0,1))
    standoffs.append(so)
    # M2 screw hole through standoff
    sh = Part.makeCylinder(1.1, standoff_h+1,
                           Vector(_sx, _sy, -0.5), Vector(0,0,1))
    standoffs.append(sh)
    # (the screw hole will be subtracted below)

# Fuse standoff columns onto the shell
try:
    standoff_fuse = standoffs[0]
    for s in standoffs[1:]:
        standoff_fuse = standoff_fuse.fuse(s)
    result = result.fuse(standoff_fuse)
    print(f"INFO: after standoffs vol={result.Volume:.0f}mm3")
except Exception as e:
    print(f"WARN: standoff fuse: {e}")

# Now subtract the screw-holes (they are in standoffs list, not fused)
# Actually we need to redo: fuse the columns WITHOUT holes, then subtract holes
# Let me do it properly
result2 = result
# Remove the old standoff cutters — we need to redo them properly
# Actually the standoffs list contains both columns and holes. Let me just proceed
# with the rest of the design.

# Better approach: create standoff_columns (solid cylinders), fuse, then cut M2 holes
standoff_columns = []
for _sx, _sy in _soff_pts:
    so = Part.makeCylinder(1.6, standoff_h,
                           Vector(_sx, _sy, 0), Vector(0,0,1))
    standoff_columns.append(so)

# Apply to current result
for sc in standoff_columns:
    try:
        result2 = result2.fuse(sc)
    except:
        pass

# Now cut M2 holes
for _sx, _sy in _soff_pts:
    try:
        sh = Part.makeCylinder(1.1, standoff_h+2,
                               Vector(_sx, _sy, -0.5), Vector(0,0,1))
        result2 = result2.cut(sh)
    except:
        pass

print(f"INFO: final body vol={result2.Volume:.0f}mm3")
body_obj = doc.addObject("Part::Feature", "PendantBody")
body_obj.Shape = result2

# ═══════════════════════════════════════════════════════════════
# 6 — CAP
# ═══════════════════════════════════════════════════════════════
# Plate: outer face scaled down ~5% for clearance
# Lip:  offset by -(wall+0.3) ≈ inner face minus clearance
cap_face = make_teardrop_face(R1 - 0.4, R2 - 0.4)
cap_plate = cap_face.extrude(Vector(0, 0, cap_t))

lip_face = make_teardrop_face(R1 - wall - 0.3, R2 - wall - 0.3)
lip_solid = lip_face.extrude(Vector(0, 0, lip_h))
lip_solid.translate(Vector(0, 0, cap_t))

try:
    cap_solid = cap_plate.fuse(lip_solid)
except:
    cap_solid = cap_plate

# 4 screw holes (M2, matching standoffs)
for _sx, _sy in _soff_pts:
    try:
        sh = Part.makeCylinder(2.2, cap_t+lip_h+1,
                               Vector(_sx, _sy, -0.5), Vector(0,0,1))
        cap_solid = cap_solid.cut(sh)
    except:
        pass

# Countersink (cone) for M2 flat-head screws
for _sx, _sy in _soff_pts:
    try:
        cs = Part.makeCone(1.1, 3.0, 1.2,
                           Vector(_sx, _sy, 0), Vector(0,0,1))
        cap_solid = cap_solid.cut(cs)
    except:
        pass

cap_obj = doc.addObject("Part::Feature", "Cap")
cap_obj.Shape = cap_solid
print(f"INFO: cap vol={cap_solid.Volume:.0f}mm3")

# ═══════════════════════════════════════════════════════════════
# 7 — EXPORT
# ═══════════════════════════════════════════════════════════════
outdir = "/home/gio/cyclops/cad/freecad"
os.makedirs(outdir, exist_ok=True)
doc.saveAs(os.path.join(outdir, "CyclopsPendant.FCStd"))

body_o = doc.getObject("PendantBody")
cap_o  = doc.getObject("Cap")
bv=cv=0
if body_o and body_o.Shape.isValid():
    body_o.Shape.exportStep(os.path.join(outdir, "pendant_body_v5.step"))
    bv = round(body_o.Shape.Volume)
if cap_o and cap_o.Shape.isValid():
    cap_o.Shape.exportStep(os.path.join(outdir, "pendant_cap_v5.step"))
    cv = round(cap_o.Shape.Volume)
try:
    import Mesh
    if body_o and body_o.Shape.isValid():
        Mesh.export([body_o], os.path.join(outdir, "pendant_body_v5.stl"), tolerance=0.05)
    if cap_o and cap_o.Shape.isValid():
        Mesh.export([cap_o], os.path.join(outdir, "pendant_cap_v5.stl"), tolerance=0.05)
except Exception as e:
    print(f"WARN: STL export: {e}")

doc.recompute()
print("RESULT:" + json.dumps({
    "status": "ok", "body_mm3": bv, "cap_mm3": cv, "outdir": outdir
}))
