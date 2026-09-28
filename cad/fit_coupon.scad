// Cyclops fit coupon — the FIRST print (docs/44 §7 step 2).
//
// It validates the §4 tolerance defaults BEFORE any enclosure is modelled:
//   * 5 blind pockets 0.10 / 0.15 / 0.20 / 0.25 / 0.30 mm play for the loose
//     8.00 mm gauge bar (per-side pocket clearance)
//   * 3 PCB-edge slots 1.60 / 1.75 / 1.90 (board thickness in a slot)
//   * 3 M2 self-tapping pilots Ø1.60 / 1.70 / 1.80
//   * 3 USB-C plug openings 9.20 / 9.40 / 9.60 × 3.80 in a 2 mm wall
//   * 3 microSD openings 11.40 / 11.60 / 11.80 × 1.30 in a 2 mm wall
//   * 1 slide-in cantilever snap latch (arm 1.80 thick, engagement 0.65)
//   * raised dots index each row: 1 dot = first variant, 2 dots = second, ...
//
// Only the row index is printed geometry; every *dimension* comes from
// cad/params.yaml through the generated cad/params.scad. Do not add numbers
// here — add them to params.yaml and re-run scripts/cad_params.py.
//
// Build (OpenSCAD with no root: scripts/get_openscad.sh):
//   OS=~/.local/share/openscad-appimage/squashfs-root/AppRun
//   $OS -o cad/stl/fit_coupon.stl cad/fit_coupon.scad
//   $OS -D 'MODE="loose"' -o /tmp/loose.stl cad/fit_coupon.scad
// Validate: python3 scripts/cad_params.py check cad/stl/fit_coupon.stl
// Print: PLA, 0.2 mm layers, no supports, no raft. ~1 h.
//
// Layout (plate corner at the origin, Z up):
//   y 22..34   gap pockets row          x 4..52
//   y 6..18    PCB slots + M2 pilots    x 4..32 / x 40..60
//   y 22..24   USB-C wall (z 4..29.5)   x 52..68
//   y 18..20   microSD wall (z 4..15.5) x 52..68
//   y 2..12    the snap latch's female half
//   y < 0      LOOSE parts: the gauge bar and the latch's male half

include <params.scad>

$fn = 48;
MODE = "all";   // "all" | "plate" | "loose"

plate_x = coupon_plate_x;
plate_y = coupon_plate_y;
plate_t = coupon_plate_t;
wall = printer_wall;

// ---- layout only (positions are arbitrary, never product dimensions) -----
gap_row_y = 28;
gap_pitch = 10;
pcb_row_y = 12;
pilot_x = [40, 50, 60];
usb_wall = [52, 22];    // [x, y]
card_wall = [52, 18];   // [x, y]
latch_female = [34, 2]; // [x, y]
loose_bar_xy = [4, -14];     // [x, y]
loose_latch_xy = [18, -14];  // [x, y]
arm_t = coupon_snap_beam_t;  // arm cross-section (Y and Z)
arm_l = coupon_snap_beam_l;
// latch channel: two rails on the plate surface, gap = arm + 0.2
rail_w = 1.4;
rail_y0 = 2;
channel_w = arm_t + 0.2;
channel_y0 = rail_y0 + rail_w;
arm_y = (8 - arm_t) / 2;     // arm position inside the loose handle

// ---- helpers ------------------------------------------------------------
module dot(n, x, y, z = plate_t) {   // raised index marker
  for (i = [0 : n - 1])
    translate([x + (i - (n - 1) / 2) * 2.4, y, z - 0.2])
      cylinder(d = 1.2, h = 0.8);   // embeds 0.2: never touch face-to-face
}

module blind_slot(x, y, width, length, depth) {
  translate([x - width / 2, y - length / 2, plate_t - depth])
    cube([width, length, depth + 0.1]);
}

module wall_slot(x, y, width_x, height_z, wall_t, z_centre) {
  translate([x - width_x / 2, y - 0.1, z_centre - height_z / 2])
    cube([width_x, wall_t + 0.2, height_z]);
}

// ---- plate with the measured features -----------------------------------
module plate() {
  difference() {
    union() {
      cube([plate_x, plate_y, plate_t]);

      // bosses: the M2 pilots are deeper than the 4 mm plate.
      // Every solid added to the plate embeds 0.2 mm: face-to-face contact
      // alone makes CGAL emit non-manifold edges (proven by the first build).
      for (x = pilot_x)
        translate([x - 3.5, pcb_row_y - 3.5, plate_t - 0.2]) cube([7, 7, 6.2]);

      // guarding walls: USB-C (3 openings) and microSD (3 openings)
      translate([usb_wall[0], usb_wall[1], plate_t - 0.2]) cube([16, wall, 22.2]);
      translate([card_wall[0], card_wall[1], plate_t - 0.2]) cube([16, wall, 12.2]);

      // the latch's female half: two guide rails straight on the plate
      translate([latch_female[0], latch_female[1], plate_t - 0.2]) {
        translate([1, rail_y0, 0]) cube([12, rail_w, 4.2]);
        translate([1, channel_y0 + channel_w, 0]) cube([12, rail_w, 4.2]);
      }
    }

    // 1. pocket clearance: 5 blind pockets, width = gauge bar + gap
    for (i = [0 : len(coupon_gaps) - 1])
      blind_slot(6 + i * gap_pitch, gap_row_y,
                 coupon_gauge_w + coupon_gaps[i], 13, 3);

    // 2. PCB thickness in a slot: 1.60 / 1.75 / 1.90
    for (i = [0 : len(coupon_pcb_slots) - 1])
      blind_slot(6 + i * gap_pitch, pcb_row_y, coupon_pcb_slots[i], 10, 3);

    // 3. M2 self-tapping pilots: Ø1.60 / 1.70 / 1.80, 6 deep in the boss
    for (i = [0 : len(coupon_pilots) - 1])
      translate([pilot_x[i], pcb_row_y, plate_t - 6])
        cylinder(d = coupon_pilots[i], h = 12);

    // 4. USB-C plug openings in a 2 mm wall (3.80 high)
    for (i = [0 : len(coupon_usb_cuts) - 1])
      wall_slot(usb_wall[0] + 8, usb_wall[1], coupon_usb_cuts[i],
                tolerance_usb_cut_h, wall, plate_t + 5 + i * 6);

    // 5. microSD openings in a 2 mm wall (1.30 high)
    for (i = [0 : len(coupon_card_slots) - 1])
      wall_slot(card_wall[0] + 8, card_wall[1], coupon_card_slots[i],
                coupon_card_t, wall, plate_t + 3 + i * 3);

    // 6. the latch detent: a pocket in the plate surface, inside the channel
    translate([latch_female[0] + 9, latch_female[1] + channel_y0,
               plate_t - tolerance_snap_engagement])
      cube([3, channel_w, tolerance_snap_engagement + 0.01]);
  }

  // raised index dots (1 dot = first variant, 2 = second, ...)
  for (i = [0 : len(coupon_gaps) - 1])
    dot(i + 1, 6 + i * gap_pitch, gap_row_y - 9);
  for (i = [0 : len(coupon_pcb_slots) - 1])
    dot(i + 1, 6 + i * gap_pitch, pcb_row_y - 8);
  for (i = [0 : len(coupon_pilots) - 1])
    dot(i + 1, pilot_x[i], pcb_row_y - 8);
  for (i = [0 : len(coupon_usb_cuts) - 1])
    dot(i + 1, usb_wall[0] + 8, usb_wall[1] - 2.5);
  for (i = [0 : len(coupon_card_slots) - 1])
    dot(i + 1, card_wall[0] + 8, card_wall[1] - 2.5);
}

// ---- loose parts (printed beside the plate) ------------------------------
module loose() {
  // the gauge bar: slides into the 5 pockets; only its width is under test
  translate([loose_bar_xy[0], loose_bar_xy[1], 0])
    cube([coupon_gauge_w, 12, 3.5]);

  // the latch's male half: handle, cantilever arm, nib with a 45° lead-in.
  // The handle is 0.5 taller than the plate and the arm starts 0.5 inside it,
  // so the two overlap in volume (coplanar contact alone is non-manifold).
  // Arm underside = plate_t, i.e. level with the female channel floor, so the
  // nib's 0.65 engagement lands in the detent cut into the plate.
  translate([loose_latch_xy[0], loose_latch_xy[1], 0]) {
    cube([8, 8, plate_t + 0.5]);
    translate([7.5, arm_y, plate_t]) cube([arm_l, arm_t, arm_t]);
    // nib: symmetric 45° trapezoid in XZ, 0.65 below the arm underside and
    // 0.2 up inside it (volume overlap = a clean union; the polygon's origin
    // is the arm underside minus the engagement).
    translate([7.5 + arm_l - 3, arm_y + arm_t, plate_t - tolerance_snap_engagement])
      rotate([90, 0, 0])
        linear_extrude(height = arm_t)
          polygon(points = [[0, tolerance_snap_engagement + 0.2],
                            [tolerance_snap_engagement, 0],
                            [3 - tolerance_snap_engagement, 0],
                            [3, tolerance_snap_engagement + 0.2]]);
  }
}

// ---- assembly -----------------------------------------------------------
if (MODE == "all" || MODE == "plate") plate();
if (MODE == "all" || MODE == "loose") loose();

