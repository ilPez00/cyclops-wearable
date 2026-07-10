// Cyclops — XIAO ESP32-S3 Sense wearable enclosure  ·  V2
// Parametric OpenSCAD.  Render:  openscad cyclops_xiao_enclosure_v2.scad
// Export:  openscad -D 'PART="body"' -o v2_body.stl cyclops_xiao_enclosure_v2.scad
//          openscad -D 'PART="lid"'  -o v2_lid.stl  cyclops_xiao_enclosure_v2.scad
//
// COORDINATE FRAME (consistent everywhere): corner-origin.
//   body : x[0..body_l]  y[0..body_w]  z[0..body_H], sits on z=0.
//   +X / -X = the SHORT ends (button bank on +X, USB-C + lanyard on -X).
//   +Y / -Y = the LONG side walls (ventilation banks live here).
//   Pocket interior is carved x[wall..body_l-wall] y[wall..body_w-wall]
//   z[base_h..body_H]; it is OPEN at the top so the board + screen drop in and
//   the lid caps the rim. The wall above z=body_h is the lock lip (a rim).
//
// V2 changes over v1:
//   1. VENTILATION — the XIAO + ST7735 get warm; v1 trapped heat and muffled
//      the MEMS mic. v2 adds lateral vent slots on BOTH long side walls, each
//      backed by an inboard air-gap baffle (pocket stays closed to fingers /
//      splash while air curls over the baffle into the pocket), a clear front
//      mic port, and a floor chimney for convection.
//   2. CLIP FIT — a real cantilever snap-fit: the body top wall forms a lock
//      lip; the lid overhangs and caps the whole top, and four living-hinge
//      claws on its underside drop past the lip and hook under the rim, clicking
//      home with no glue / tools / hardware. Four ratchet dots on the lid
//      underside catch the lip top for a satisfying detent.
//
// Board: XIAO ESP32-S3 Sense (21.0 x 17.5 mm). Screen: ST7735 1.8" (glass 28x28).
// Pins: BTN_A=GPIO3, BTN_B=GPIO5, WHEEL_B=GPIO4 (holes on +X end). Mic = MEMS
// on the Sense module (front -Y wall port).

// ---- parameters ----
xiao_l   = 21.0;   // board length (mm)
xiao_w   = 17.5;   // board width
wall     = 2.0;    // wall thickness
base_h   = 6.0;    // pocket floor depth (board sits on it)
pocket_h = 9.0;    // interior pocket height above floor
lip_h    = 2.4;    // raised lock lip height above body top
body_h   = base_h + pocket_h;        // 15.0 main body height
body_H   = body_h + lip_h;           // 17.4 total height (incl lip)

// the screen glass drives the case width (it is the biggest component)
screen_glass = 28.0;  // ST7735 visible glass
body_l = screen_glass + 2*wall + 4;  // 36.0  (length, incl end caps)
body_w = screen_glass + 2*wall + 2;  // 34.0  (width)

// lid overhangs the body so it caps the lip from outside
lid_overhang = 1.5;
lid_l  = body_l + 2*lid_overhang;    // 39.0
lid_w  = body_w + 2*lid_overhang;    // 37.0
win    = 24.0;    // lid viewing window (reveal); < lid so plate + claws stay

// closure geometry
tab_w      = 5.0;   // snap claw footprint
tab_drop   = 4.2;   // how far claws hang below the lid
tab_hook   = 3.0;   // inward hook length at claw tip
ratch_d    = 1.8;   // ratchet detent dot diameter
c          = tab_w/2 + 0.5;   // corner anchor inset (3.0)

// ventilation geometry
vent_rows  = 3;     // rows of vents per side (vertical)
vent_cols  = 4;     // vents per row (along X)
vent_w     = 2.2;   // individual slot width (along X)
vent_h     = 5.0;   // individual slot height (vertical, Z)
vent_gap_x = 3.0;   // spacing along X
vent_gap_y = 3.0;   // spacing between rows (Z)
vent_z     = 7.0;   // first row height above floor
mic_port_d = 4.0;   // acoustic mic port diameter

$fn = 24;

// ---- helpers ----
module rounded_box(l,w,h,r=2.0){
  hull(){
    translate([ r,   r,    0]) cube([l-2*r, w-2*r, h]);
    translate([ r,   w-r,   0]) cube([l-2*r, 0.01,  h]);
    translate([ l-r, r,     0]) cube([0.01,  w-2*r, h]);
    translate([ l-r, w-r,   0]) cube([0.01,  0.01,  h]);
  }
}

// round-rect prism (long axis = local Z); used for vent slots
module vent_slot(w,h,depth){
  hull(){
    for(sx=[-1,1])
      translate([sx*(w/2-1), -h/2+1, 0]) cube([1, h-2, depth]);
    for(sx=[-1,1])
      translate([sx*(w/2-1), h/2-1, 0]) cube([1, 1, depth]);
  }
}

// cylindrical hole driven along X (pierces a short END wall)
module end_hole(x_wall, y, z, d){
  translate([x_wall, y, z]) rotate([0,90,0])
    cylinder(d=d, h=wall+3, $fn=20);
}
// cylindrical hole driven along Y (pierces a long SIDE wall)
module side_hole(y_wall, x, z, d){
  translate([x, y_wall, z]) rotate([90,0,0])
    cylinder(d=d, h=wall+3, $fn=20);
}

// ---- ventilation: banks on the two long side walls ----
// Slot long-axis runs along X, height is vertical (Z); the hole is driven along
// Y so it pierces the side wall. y_face = the wall centre in corner-origin frame.
module vent_bank_side(y_face){
  for(r=[0:vent_rows-1])
    for(col=[0:vent_cols-1]){
      vx = body_l/2 + (col - (vent_cols-1)/2) * vent_gap_x;
      vz = vent_z + r * vent_gap_y;
      translate([vx, y_face, vz])
        rotate([90,0,0])
          vent_slot(vent_w, vent_h, wall+3);
    }
}

// air-gap baffles: a thin fin parallel to each long side wall, attached to the
// pocket floor, rising most of the pocket height, set inboard. The vent slot
// opens into the narrow channel between the wall and the baffle; sightline from
// the exterior to the interior is blocked (no finger/splash straight-through)
// but air enters the channel and curls over the baffle top into the pocket.
// ADDED (unioned) to the body, attached to the floor => one manifold, printable.
module airgap_baffles(){
  baffle_off = (body_w/2) - wall - 3.0;   // inboard of each side wall
  baffle_t   = 1.5;                       // fin thickness (Y)
  baffle_top = body_h - 1.0;              // leave 1mm gap over the top
  for(side=[-1,1]){
    yc = body_w/2 + side*baffle_off;
    translate([wall, yc - baffle_t/2, base_h])
      cube([body_l - 2*wall, baffle_t, baffle_top - base_h]);
  }
}

// board-clearance chimney through the pocket floor (passive convection)
module chimney(){
  translate([body_l/2, body_w/2 - 4, base_h-1])
    cylinder(d=4.0, h=base_h+2, $fn=16);
}

// ---- BODY (single watertight solid) ----
// Outer shell (full height incl. lip) with the pocket carved OPEN to the top so
// the board drops in and the lid caps the rim. The outer wall stays solid all
// the way up to form the lock lip. All subtractive features pierce fully so the
// carves stay watertight. Air-gap baffles are UNIONED onto the shell (attached
// to the floor) so they add structure, not void. Screen is visible through the
// open pocket (no top window needed on the body).
module body(){
  union(){
    difference(){
      rounded_box(body_l, body_w, body_H, 3);
      // interior pocket, OPEN at top (carved to body_H)
      translate([wall, wall, base_h])
        cube([body_l-2*wall, body_w-2*wall, body_H - base_h]);
      // USB-C cutout on -X end (rectangular slot piercing the end wall)
      translate([-2, body_w/2-5, base_h+1]) cube([6, 10, 5]);
      // button holes on +X end: BTN_A (3) / BTN_B (5) / WHEEL_B (4)
      end_hole(body_l - wall/2, body_w/2-7, base_h+4.0, 6.0);
      end_hole(body_l - wall/2, body_w/2+7, base_h+4.0, 6.0);
      end_hole(body_l - wall/2, body_w/2,   base_h+4.5, 6.0);
      // two lanyard/strap slots on -X end
      translate([-1, body_w/2-11, body_H/2-1.5]) cube([4, 8, 3]);
      translate([-1, body_w/2+3,  body_H/2-1.5]) cube([4, 8, 3]);
      // ventilation banks on both long side walls
      vent_bank_side( body_w - wall/2);   // +Y wall
      vent_bank_side( wall/2);            // -Y wall
      // front mic port on -Y wall (clear acoustic path, no baffle)
      side_hole( wall/2, body_l/2-6, base_h+3, mic_port_d);
      chimney();
    }
    airgap_baffles();
  }
}

// ---- LID (snap-fit) ----
// Overhangs and caps the whole top (footprint = body + overhang). Four claws
// hang from the underside at the corners, drop past the lip, and hook inward
// under the rim. Four ratchet dots on the underside catch the lip top. A viewing
// window is cut through the plate so the ST7735 shows through. Authored at
// z=0..lid_t; everything overlaps the plate => one manifold solid.
module snap_claw(cx, cy, dirx, diry){
  // cx,cy = corner anchor on the lid underside; dirx/diry = outward direction
  // post overlaps 0.6 into the plate so the union is one manifold
  translate([cx, cy, -tab_drop]){
    cube([tab_w, tab_w, tab_drop + 0.6]);
    // inward hook at the bottom that grabs the lip underside
    translate([dirx*(tab_w/2 - tab_hook/2),
               diry*(tab_w/2 - tab_hook/2),
               tab_drop - 1.2])
      cube([dirx*tab_hook, diry*tab_hook, 1.4]);
  }
}

module lid(){
  lid_t = 2.0;
  // center the lid over the body (body 0..body_l, lid overhangs symmetrically)
  off = (lid_l - body_l)/2;   // 1.5
  translate([-off, -off, 0])
  difference(){
    union(){
      // lid plate (caps the top, overhangs the lip)
      rounded_box(lid_l, lid_w, lid_t, 3);
      // four snap claws at the corners (attached to plate underside)
      snap_claw( c,            c,            1,  1);
      snap_claw( lid_l - c,    c,           -1,  1);
      snap_claw( c,            lid_w - c,    1, -1);
      snap_claw( lid_l - c,    lid_w - c,   -1, -1);
      // ratchet detent dots (catch the lip top), just inside the rim, poking down
      for(sx=[0:1], sy=[0:1]){
        px = sx ? lid_l - (wall+3) : (wall+3);
        py = sy ? lid_w - (wall+3) : (wall+3);
        // ball centred in the plate so it is one manifold (not a floating bead)
        translate([px, py, lid_t/2])
          sphere(d=ratch_d, $fn=16);
      }
    }
    // viewing window through the lid plate (matches the pocket so the ST7735
    // shows through). win < lid so the plate + claws stay intact.
    translate([lid_l/2 - win/2, lid_w/2 - win/2, -1])
      cube([win, win, lid_t+2]);
  }
}

// ---- render dispatcher ----
// Do NOT set `PART = undef;` here — it overrides the -D command-line value and
// silently breaks per-part export. Leave PART undefined; the is_undef guard
// below renders the default (both parts) when no -D is passed.
if (!is_undef(PART) && PART=="body") body();
else if (!is_undef(PART) && PART=="lid") lid();
else { body(); translate([body_l+8,0,0]) lid(); }

// ---- printable orientation / notes ----
// Print body upside-down (open pocket up). Lid print flat, claws up.
// Snap claws are thin living hinges — tune tab_drop/tab_hook if brittle.
// Scale holes 1.05x if your printer runs tight. Air-gap baffles keep the pocket
// closed to fingers/splash while the side vents + floor chimney give passive
// convection. Lid drops over the body: plate seats over the lock lip, claws snap
// under the rim, ratchet dots settle on the lip top for a tool-free detent.
