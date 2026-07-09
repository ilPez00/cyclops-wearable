// Cyclops — Arduino Nano HUD desktop enclosure
// Parametric OpenSCAD. Renders with: openscad -o arduino.stl cyclops_arduino_enclosure.scad
//
// Holds an Arduino Nano on standoffs + a ST7735 1.8" TFT mounted on the lid
// (wired via dupont cables). Controls (buttons/wheel) stick through the top.
// Open bottom (or add a base plate) so the USB-mini of the Nano is reachable
// for the serial link to the brain.

nano_l = 45.0;   // Nano board length
nano_w = 18.0;   // Nano width
wall   = 2.0;
floor_h= 4.0;    // base floor
inner_h= 26.0;   // height under lid
body_l = nano_l + 2*wall + 6;
body_w = max(nano_w, 40.0) + 2*wall;
body_h = floor_h + inner_h;
$fn = 24;

// ST7735 module (1.8") mounted on lid, facing up
mod_w = 35.0;
mod_h = 36.0;
win_w = 28.0;
win_h = 28.0;

module rbox(l,w,h,r=2.0){
  hull(){
    translate([ r, r, 0]) cube([l-2*r, w-2*r, h]);
    translate([ r, w-r, 0]) cube([l-2*r, 0.01, h]);
    translate([ l-r, r, 0]) cube([0.01, w-2*r, h]);
    translate([ l-r, w-r, 0]) cube([0.01, 0.01, h]);
  }
}

// standoff post for an M3 screw
module standoff(x,y,h){
  difference(){
    cylinder(d=6, h=h, $fn=20);
    translate([0,0,-1]) cylinder(d=3.2, h=h+2, $fn=16);
  }
}

module body(){
  difference(){
    rbox(body_l, body_w, body_h, 3);
    // hollow
    translate([wall, wall, floor_h])
      cube([body_l-2*wall, body_w-2*wall, body_h-floor_h+1]);
    // Nano USB-mini cutout on -X end (reachable for serial)
    translate([-1, body_w/2-7, floor_h+2]) cube([4, 14, 8]);
  }
  // 4 standoffs at Nano corners (raised from floor)
  for (p = [[wall+3, wall+3], [wall+3, wall+nano_w-1],
            [wall+3+nano_l-2, wall+3], [wall+3+nano_l-2, wall+nano_w-1]])
    translate([p[0], p[1], floor_h]) standoff(p[0], p[1], inner_h-4);
}

module lid(){
  // top plate with screen window + control holes
  difference(){
    rbox(body_l, body_w, 3.0, 3);
    // screen window centered
    translate([body_l/2 - win_w/2, body_w/2 - win_h/2, -1])
      cube([win_w, win_h, 5]);
    // control holes (BTN_A=D5, BTN_B=D6, WHEEL_A=D2, WHEEL_B=D3, WHEEL_BTN=D4)
    // laid out in a row near the front (+X)
    for (i = [0:4])
      translate([wall+12 + i*7, body_w/2+10, -1]) cylinder(d=5, h=5, $fn=16);
  }
  // a thin raised bezel ring around the screen
  difference(){
    translate([body_l/2 - mod_w/2 - 1, body_w/2 - mod_h/2 - 1, 3])
      cube([mod_w+2, mod_h+2, 2]);
    translate([body_l/2 - win_w/2, body_w/2 - win_h/2, 2])
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

// Note: wire the ST7735 (CS=D10, DC=D9, RST=D8, SCK=D13, MOSI=D11) to the
// Nano with Dupont jumpers before closing the lid. VBAT/prox/joystick are
// optional. See docs/31-schematics-arduino.md.
