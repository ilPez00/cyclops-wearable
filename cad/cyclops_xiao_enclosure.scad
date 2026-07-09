// Cyclops — XIAO ESP32-S3 Sense wearable enclosure
// Parametric OpenSCAD. Renders with: openscad -o xiao.stl cyclops_xiao_enclosure.scad
//
// Two parts: a body (holds the XIAO + ST7735 1.8" TFT) and a lid.
// Holes: USB-C cutout, screen window, 2 button holes (BTN_A/BTN_B = GPIO3/5),
// wheel B hole (GPIO4); BOOT/WHEEL_A (GPIO0) is the onboard button (no hole).
// Mounting: a wrist-strap slot on each side.

// ---- parameters ----
xiao_l = 21.0;   // XIAO S3 Sense board length (mm)
xiao_w = 17.5;   // board width
wall   = 2.0;    // wall thickness
base_h = 6.0;    // base pocket depth (board sits in it)
lid_h  = 10.0;   // total inner height to lid underside
screen_w = 35.0; // ST7735 module (1.8") outer width
screen_h = 36.0; // module height
win_w   = 28.0;  // visible glass window
win_h   = 28.0;

// module sits on top of board; model as a raised bezel
body_l = xiao_l + 2*wall + 4;
body_w = max(xiao_w, screen_w) + 2*wall;
body_h = lid_h + 2;

$fn = 24;

module rounded_box(l,w,h,r=2.0){
  hull(){
    translate([ r-r, r-r, 0]) cube([l-2*r+0.01, w-2*r+0.01, h]);
    translate([ r-r, w-r, 0]) cube([l-2*r+0.01, 0.01, h]);
    translate([ l-r, r-r, 0]) cube([0.01, w-2*r+0.01, h]);
    translate([ l-r, w-r, 0]) cube([0.01, 0.01, h]);
  }
}

// button hole helper (cylindrical, through top)
module btn_hole(x, y, d=6.0){
  translate([x, y, body_h-2]) cylinder(d=d, h=4, $fn=20);
}

// strap slot helper (through side wall)
module strap_slot(y){
  translate([-1, y, body_h/2-4]) cube([4, 8, 3]);
}

module body(){
  difference(){
    rounded_box(body_l, body_w, body_h, 3);
    // hollow interior pocket
    translate([wall, wall, base_h])
      cube([body_l-2*wall, body_w-2*wall, body_h-base_h+1]);
    // board seat lip (thinner floor under board)
    // screen window (top, centered along length)
    translate([body_l/2 - win_w/2, body_w/2 - win_h/2, body_h-3])
      cube([win_w, win_h, 4]);
    // USB-C cutout on -X end
    translate([-1, body_w/2-5, base_h+1]) cube([4, 10, 5]);
    // button holes: BTN_A (GPIO3) and BTN_B (GPIO5) near +X end
    btn_hole(body_l-wall-4, body_w/2-7);
    btn_hole(body_l-wall-4, body_w/2+7);
    // wheel B (GPIO4) hole, mid
    btn_hole(body_l-wall-4, body_w/2);
    // strap slots both sides
    strap_slot(body_w/2-7);
    strap_slot(body_w/2+7);
  }
}

module lid(){
  // thin cover with screen opening
  difference(){
    rounded_box(body_l, body_w, 2.0, 3);
    translate([body_l/2 - win_w/2, body_w/2 - win_h/2, -1])
      cube([win_w, win_h, 4]);
  }
}

// render: PART=body | PART=lid | PART=all (default: both side by side)
// is_undef(PART) -> show both so the GUI is never empty.
if (!is_undef(PART) && PART == "body") {
  body();
} else if (!is_undef(PART) && PART == "lid") {
  lid();
} else {
  body();
  translate([body_l+6, 0, 0]) lid();
}

// ---- printable orientation note ----
// Print body upside-down (screen window up). Lid glues/snaps on top.
// Scale holes 1.05x if your printer runs tight.
