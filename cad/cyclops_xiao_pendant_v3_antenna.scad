// Cyclops — XIAO ESP32-S3 Sense PENDANT case  ·  V3 (antenna strain-relief)
// Parametric OpenSCAD.  Screenless capture puck.  Extends the V2 teardrop
// pendant (cyclops_xiao_pendant.scad) by replacing the flat u.FL exit slot
// with a proper STRAIN-RELIEF cable-grip at the bail tip: the whip pigtail is
// dressed through an internal bore and pinched by two ribs, then a dab of
// silicone in the relief pocket locks it so a yank can't pop the u.FL off the
// XIAO.  All other V2 features are preserved.
//
// Render both:    openscad cyclops_xiao_pendant_v3_antenna.scad
// Export parts:   openscad -D 'PART="body"' -o pendant_v3_antenna_body.stl cyclops_xiao_pendant_v3_antenna.scad
//                 openscad -D 'PART="cap"'  -o pendant_v3_antenna_cap.stl  cyclops_xiao_pendant_v3_antenna.scad
//
// Component dims (researched, mm):
//   XIAO ESP32-S3 Sense .... 21.0 x 17.5, Sense piggyback stack ~6 tall
//   External IMU GY-521 .... 20 x 15 x 2.5  (on D6/D7 I2C, avoids GPIO5/6 colln)
//   LiPo 302030 ............ 30 x 20 x 3
//   EC11 encoder ........... shaft Ø6, body ~11.5 sq, side "crown"
//   2x SMD side tact ....... ~4x4x1.6
//   u.FL whip antenna ...... pigtail exits at bail tip, gripped by relief

// ---- parameters ----
wall      = 2.0;     // shell wall thickness
T         = 16.0;    // total pendant thickness (front face at +Z)
inset     = wall;    // interior pocket inset

xiao_l = 21.0;  xiao_w = 17.5;  xiao_h = 6.0;
imu_l  = 20.0;  imu_w  = 15.0;  imu_h  = 2.5;
batt_l = 30.0;  batt_w = 20.0;  batt_h = 3.0;

bulge_r   = 22.0;   bulge_y = -22.0;
neck_r    = 7.0;    neck_y  = 30.0;
tip_y     = 37.0;

enc_d     = 7.2;    enc_body = 12.0;  wheel_y = 22.0;
btn_d     = 4.2;    btn_y  = -4.0;    btn_y2 = -16.0;
led_d     = 6.0;    led_x  = 0.0;    led_y  = 16.0;
mic_w     = 3.0;    mic_h  = 5.0;    mic_x  = -7.0;  mic_y = -2.0;

usb_w     = 9.0;    usb_h  = 3.4;    usb_y  = 6.0;

// ---- strain-relief (NEW in v3) ----
relief_bore_d = 4.5;   // internal bore the pigtail is dressed through
relief_len    = 10.0;  // length of the grip channel (along +Y, into the bail axis)
relief_rib_d  = 2.2;   // pinch-rib diameter (grips the cable when silicone sets)
relief_pocket = 5.0;   // silicone dab pocket dia at the inboard end
relief_z      = T/2;   // centered in slab thickness

lip_h     = 1.6;
cap_t     = 1.6;
$fn = 36;

// ---- helpers ----
module teardrop_2d(){
  hull(){
    translate([0, bulge_y, 0]) circle(r=bulge_r);
    translate([0, neck_y,  0]) circle(r=neck_r);
  }
}
module shell_outer(){ linear_extrude(height=T) teardrop_2d(); }
module shell_inner(){
  translate([0,0,cap_t])
    linear_extrude(height=T-cap_t-wall) offset(r=-inset) teardrop_2d();
}
module part_pocket(l,w,h,z0,cx=0,cy=0){
  translate([cx-l/2, cy-w/2, z0]) cube([l, w, h+0.4]);
}
module through_hole(d, x, y, z0=0, z1=T){
  translate([x, y, z0-1]) cylinder(d=d, h=(z1-z0)+2, $fn=24);
}
module side_hole(d, y, x_sign=1, w_box=0){
  translate([x_sign*(bulge_r-wall-0.5), y, T/2]) rotate([0,90,0]){
    if(w_box>0){
      hull(){ for(sy=[-1,1]) translate([0, sy*(w_box/2-d/2), 0]) cylinder(d=d, h=wall+3, $fn=20); }
    } else { cylinder(d=d, h=wall+3, $fn=20); }
  }
}
module torus(R, r){ rotate_extrude() translate([R,0,0]) circle(r=r, $fn=20); }

// ---- strain-relief channel (replaces v2 flat slot) ----
// A bore from the tip face inward along +Y, two pinch ribs straddling it, and
// a wider silicone pocket just inboard. Subtracted from the body. The pigtail
// routes: external -> tip bore -> through ribs -> silicone pocket -> (inside,
// dressed down to the XIAO's u.FL). Built as a single union so it's one cut.
module antenna_relief(){
  // exit bore through the tip wall (along Y)
  translate([0, tip_y-1, relief_z])
    rotate([90,0,0]) cylinder(d=relief_bore_d, h=wall+3, $fn=20);
  // internal grip channel (along Y, into the body)
  translate([0, tip_y-1-relief_len/2, relief_z])
    rotate([90,0,0]) cylinder(d=relief_bore_d, h=relief_len, $fn=20);
  // two pinch ribs straddling the channel (thin posts the cable seats between)
  for(rx=[-1,1]){
    translate([rx*(relief_bore_d/2+relief_rib_d/2), tip_y-1-relief_len*0.35, relief_z])
      rotate([90,0,0]) cylinder(d=relief_rib_d, h=relief_len*0.7, $fn=16);
  }
  // silicone dab pocket (wider, inboard end) — locks the cable after set
  translate([0, tip_y-1-relief_len+1.5, relief_z])
    rotate([90,0,0]) cylinder(d=relief_pocket, h=3, $fn=20);
}

// ---- BODY (front shell) ----
module body(){
  difference(){
    shell_outer();
    shell_inner();
    part_pocket(batt_l+1, batt_w+1, batt_h+1, cap_t+1.0, 0, -18);
    part_pocket(xiao_l+1, xiao_w+1, xiao_h+1, cap_t+4.0, 0, 1);
    part_pocket(imu_l+1,  imu_w+1,  imu_h+1,  cap_t+8.3, 0, 1);
    through_hole(enc_d, 0, wheel_y, T-enc_d/2-0.5, T+2);
    translate([0, wheel_y, T-enc_body/2-3]) cylinder(d=enc_body, h=enc_body/2+3, $fn=24);
    side_hole(btn_d, btn_y,  1);  side_hole(btn_d, btn_y, -1);
    side_hole(btn_d, btn_y2, 1);  side_hole(btn_d, btn_y2,-1);
    through_hole(led_d, led_x, led_y, T-1.0, T+2);
    translate([mic_x-mic_w/2, mic_y-mic_h/2, T-2.5]) cube([mic_w, mic_h, 3]);
    side_hole(usb_h, usb_y,  1, w_box=usb_w);
    side_hole(usb_h, usb_y, -1, w_box=usb_w);
    antenna_relief();                       // V3 strain-relief (was flat slot)
  }
  translate([0, tip_y+1, T/2]) torus(5.0, 1.6);
}

// ---- CAP (back cover, press-fit lip) ----
module cap(){
  difference(){
    union(){
      linear_extrude(height=cap_t) offset(r=-0.4) teardrop_2d();
      translate([0,0,cap_t]) linear_extrude(height=lip_h) offset(r=-inset-0.3) teardrop_2d();
    }
    for(a=[0:3]){
      ang = a*90 + 45;
      sx = 9*cos(ang); sy = 1 + 9*sin(ang);
      translate([sx, sy, cap_t]) cylinder(d=3.2, h=lip_h+6, $fn=16);
    }
  }
}

// ---- render dispatcher ----
PART = undef;
if (!is_undef(PART) && PART=="body") body();
else if (!is_undef(PART) && PART=="cap")  cap();
else { body(); translate([0,-70,0]) cap(); }

// ---- printable orientation / notes ----
// Print body front-face-DOWN (bail tip up). Cap flat. V3 change vs V2: the
// bail-tip u.FL exit is now a relief channel (bore + 2 pinch ribs + silicone
// pocket) instead of a flat slot. Route the whip: out the tip, through the
// bore, seat it between the ribs, dab silicone in the pocket, dress the other
// end to the XIAO u.FL. Tunable: relief_bore_d / relief_len / relief_rib_d /
// relief_pocket. Scale holes 1.05x if your printer runs tight.
