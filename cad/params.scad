// GENERATED FILE — do not edit.
// Source of truth: cad/params.yaml  (case dimensions live there).
// Regenerate: python3 scripts/cad_params.py generate
//
// Provenance of every value: PROBED (vendor geometry, scripts/cad_probe.py)
// SPEC (datasheet) | DEFAULT (docs/44 §4, confirmed by the fit coupon) |
// UNVERIFIED (M-number = the caliper measurement in docs/44 §6 that
// replaces it). Quote the tag when a dimension is questioned.

// ---- meta
meta_updated = "2026-09-28";
meta_doc = "docs/44-case-redesign.md";
meta_units = "mm";

// ---- printer
printer_nozzle = 0.4;  // DEFAULT  process assumption
printer_layer = 0.2;  // DEFAULT
printer_wall = 2.0;  // DEFAULT
printer_wall_min = 1.6;  // DEFAULT
printer_floor = 1.2;  // DEFAULT
printer_fillet = 1.5;  // DEFAULT

// ---- tolerance
tolerance_pocket_per_side = 0.2;  // DEFAULT  PCB into a pocket
tolerance_pcb_slot_h = 1.75;  // DEFAULT  1.6 board + solder wick/HASL
tolerance_window_over_active = 0.3;
tolerance_panel_recess = 1.6;  // DEFAULT  glass 1.45 + tape/foam
tolerance_camera_over_barrel = 0.4;
tolerance_card_clear_w = 0.6;  // DEFAULT  microSD opening width
tolerance_card_clear_h = 0.3;  // DEFAULT  microSD opening height
tolerance_snap_engagement = 0.65;  // DEFAULT  radial hook engagement
tolerance_press_fit = -0.12;  // DEFAULT  interference for keep-put parts
tolerance_screw_pilot_pla = 1.6;  // DEFAULT  M2 self-tapping
tolerance_screw_pilot_petg = 1.7;  // DEFAULT
tolerance_usb_cut_w = 9.4;  // DEFAULT  USB-C plug opening
tolerance_usb_cut_h = 3.8;  // DEFAULT
tolerance_usb_chamfer = 0.3;  // DEFAULT
tolerance_button_hole = 4.4;  // DEFAULT  button cap Ø4.2 + 0.2
tolerance_button_cbore = 0.5;  // DEFAULT
tolerance_antenna_keepout = 10.0;  // DEFAULT  no metal/battery this close to the antenna
tolerance_lanyard_slot_w = 3.0;  // DEFAULT
tolerance_lanyard_slot_h = 1.5;  // DEFAULT
tolerance_lanyard_wall = 1.6;  // DEFAULT

// ---- parts
parts_xiao_outline_x = 17.79;  // PROBED   fab outline (published nominal 17.5)
parts_xiao_outline_y = 21.14;  // PROBED   fab outline (published nominal 21.0)
parts_xiao_thickness = 1.6;  // UNVERIFIED M5
parts_xiao_pin_pitch = 2.54;  // PROBED   exactly 2.54 on all 7 rows
parts_xiao_pins_per_side = 7;  // PROBED
parts_xiao_pad_x = 2.04;  // PROBED   pad size, flush with the long edges
parts_xiao_pad_y = 1.52;  // PROBED
parts_xiao_row_centres = 15.745;
parts_exp_outline_x = 17.78;  // PROBED
parts_exp_outline_y = 15.37;  // PROBED   the XIAO overhangs it by ~5.8
parts_exp_thickness = 1.6;  // UNVERIFIED M5
parts_sense_outline_x = 17.79;  // PROBED
parts_sense_outline_y = 21.15;  // PROBED
parts_cam_foot_x = 5.05;  // PROBED   camera footprint
parts_cam_foot_y = 4.72;  // PROBED
parts_cam_at_x = 7.89;  // PROBED   footprint origin from the board corner
parts_cam_at_y = 6.59;  // PROBED
parts_cam_axis_x = 10.415;  // PROBED   derived: cam_at_x + cam_foot_x/2
parts_cam_axis_y = 8.95;  // PROBED   derived: cam_at_y + cam_foot_y/2
parts_mate_height = 8.5;  // UNVERIFIED M6 — XIAO↔expansion, 2.54 female headers.
parts_mate_height_alt = 3.2;  // UNVERIFIED M6 — the other scenario: soldered
parts_oled_active_x = 22.384;  // SPEC
parts_oled_active_y = 5.584;  // SPEC
parts_oled_panel_x = 30.0;  // SPEC     glass
parts_oled_panel_y = 11.5;  // SPEC     glass
parts_oled_panel_t = 1.45;  // SPEC     glass
parts_oled_carrier_x = 38.0;  // UNVERIFIED M1
parts_oled_carrier_y = 12.0;  // UNVERIFIED M1
parts_oled_carrier_t = 2.6;  // UNVERIFIED M1  PCB + solder side
parts_accel_x = 21.0;  // UNVERIFIED M9
parts_accel_y = 16.0;  // UNVERIFIED M9
parts_accel_t = 2.5;  // UNVERIFIED M9
parts_batt_x = 30.0;  // UNVERIFIED M10
parts_batt_y = 20.0;  // UNVERIFIED M10
parts_batt_t = 3.0;  // UNVERIFIED M10
parts_btn_cap_d = 4.2;  // UNVERIFIED M11
parts_btn_body = 6.0;  // UNVERIFIED M11
parts_btn_height = 5.0;  // UNVERIFIED M11
parts_usb_shell_x = 8.942;  // PROBED
parts_usb_shell_y = 7.3;  // PROBED
parts_usb_shell_t = 4.2;  // PROBED   shell + SMT pegs

// ---- standard
standard_microsd_w = 11.0;  // SPEC  microSD card width
standard_microsd_t = 1.0;  // SPEC  microSD card thickness
standard_m2_screw_d = 2.0;  // SPEC  M2 self-tapping screw

// ---- case
case_lid_t = 2.0;  // DEFAULT  lid face (carries the display window)
case_assembly_gap_z = 1.0;  // DEFAULT  total Z slop, split between the two

// ---- coupon
coupon_gaps = [0.1, 0.15, 0.2, 0.25, 0.3];  // PCB play per side
coupon_gauge_w = 8.0;  // the loose gauge bar tested in each slot
coupon_pilots = [1.6, 1.7, 1.8];  // M2 self-tapping PILOT Ø
coupon_pilot_depth = 6.0;
coupon_usb_cuts = [9.2, 9.4, 9.6];  // USB-C slot widths (plug test)
coupon_card_slots = [11.4, 11.6, 11.8];  // microSD opening widths
coupon_card_t = 1.3;  // microSD opening height
coupon_pcb_slots = [1.6, 1.75, 1.9];  // PCB-edge slot heights
coupon_snap_beam_t = 1.8;  // cantilever beam thickness
coupon_snap_beam_l = 14.0;
coupon_plate_x = 70.0;
coupon_plate_y = 36.0;
coupon_plate_t = 4.0;
