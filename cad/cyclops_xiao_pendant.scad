// Cyclops — XIAO ESP32-S3 Sense PENDANT case  ·  teardrop / wearable amulet
// Parametric OpenSCAD.  Screenless capture puck (notes/display via phone/G2 +
// TTS, already wired in the brain). Geometry pulled from researched component
// dims (see footer URLs).
//
// Render both:    openscad cyclops_xiao_pendant.scad
// Export parts:   openscad -D 'PART="body"' -o pendant_body.stl cyclops_xiao_pendant.scad
//                 openscad -D 'PART="cap"'  -o pendant_cap.stl  cyclops_xiao_pendant.scad
//
// Component dims used (researched, mm):
//   XIAO ESP32-S3 Sense .... 21.0 x 17.5, Sense piggyback stack ~6 tall
//   External IMU GY-521 .... 20 x 15 x 2.5  (on D6/D7 I2C, avoids GPIO5/6 colln)
//   LiPo 302030 ............ 30 x 20 x 3
//   EC11 encoder ........... shaft Ø6, body ~11.5 sq, used as side "crown"
//   2x SMD side tact ....... ~4x4x1.6 (modelled Ø4 holes)
//   u.FL whip antenna ...... pigtail exits at bail tip slot
//
// Layer stack inside the pendant (Z = front->back, front face = +Z = top):
//   cap plate ........... z 0..1.6   (back cover, press-fit lip)
//   battery 302030 ...... z 2.5..5.5 (lies flat on cap)
//   XIAO board ......... z 6.0..12.0 (stack height ~6)
//   IMU breakout ....... z 12.3..14.8 (sits on the I2C bus above XIAO)
//   front shell ........ z 14.8..T    (T = total thickness)

// ---- parameters ----
wall      = 2.0;     // shell wall thickness
T         = 16.0;    // total pendant thickness (front face at +Z)
inset     = wall;    // interior pocket inset

// board / part dims
xiao_l = 21.0;  xiao_w = 17.5;  xiao_h = 6.0;
imu_l  = 20.0;  imu_w  = 15.0;  imu_h  = 2.5;
batt_l = 30.0;  batt_w = 20.0;  batt_h = 3.0;

// teardrop outline (2D, broad face in XY)
bulge_r   = 22.0;   // bottom bulge radius
bulge_y   = -22.0;  // bottom bulge center
neck_r    = 7.0;    // top neck radius (tapers to tip)
neck_y    = 30.0;   // neck center
tip_y     = 37.0;   // lanyard bail tip

// wheel / crown
enc_d     = 7.2;    // shaft+collar hole (EC11 shaft Ø6 + clearance)
enc_body  = 12.0;   // encoder body pocket dia
wheel_y   = 22.0;   // crown position on the upper chest (front-proud)

// buttons (2x side tact)
btn_d     = 4.2;    // side button hole dia
btn_y     = -4.0;   // vertical positions (mirror L/R)
btn_y2    = -16.0;

// status LED window (front face, diffuser insert)
led_d     = 6.0;
led_x     = 0.0;
led_y     = 16.0;

// acoustic mic vent (front, over XIAO MEMS mic)
mic_w     = 3.0;  mic_h = 5.0;
mic_x     = -7.0; mic_y = -2.0;

// u.FL antenna exit slot (bail tip)
ufl_w     = 4.0;  ufl_h = 2.0;

// USB-C cutout (side, field-serviceable power/program — XIAO edge connector)
usb_w     = 9.0;  usb_h = 3.4;
usb_y     = 6.0;   // near the top neck, clear of buttons/mic

// closure
lip_h     = 1.6;   // cap seating lip
cap_t     = 1.6;   // cap plate thickness

$fn = 36;

// ---- helpers ----
module teardrop_2d(){
  // hull of a wide bottom circle + small top neck circle => teardrop
  hull(){
    translate([0, bulge_y, 0]) circle(r=bulge_r);
    translate([0, neck_y,  0]) circle(r=neck_r);
  }
}

module shell_outer(){           // full solid teardrop slab
  linear_extrude(height=T) teardrop_2d();
}

module shell_inner(){           // hollowed interior (pocket)
  // inset pocket from the broad outline
  translate([0,0,cap_t])
    linear_extrude(height=T-cap_t-wall)
      offset(r=-inset) teardrop_2d();
}

// round-rect pocket for a flat part lying in XY at height z0
module part_pocket(l,w,h,z0,cx=0,cy=0){
  translate([cx-l/2, cy-w/2, z0]) cube([l, w, h+0.4]);
}

// through-hole (cylinder spanning the slab)
module through_hole(d, x, y, z0=0, z1=T){
  translate([x, y, z0-1]) cylinder(d=d, h=(z1-z0)+2, $fn=24);
}

module side_hole(d, y, x_sign=1, w_box=0){   // hole through curved side wall (X axis)
  // d = throat dia (round) OR slot height if w_box>0 (rounded-rect slot)
  translate([x_sign*(bulge_r-wall-0.5), y, T/2])
    rotate([0,90,0]){
      if(w_box>0){
        hull(){
          for(sy=[-1,1])
            translate([0, sy*(w_box/2-d/2), 0]) cylinder(d=d, h=wall+3, $fn=20);
        }
      } else {
        cylinder(d=d, h=wall+3, $fn=20);
      }
    }
}

// ---- BODY (front shell) ----
module body(){
  difference(){
    shell_outer();
    shell_inner();                                   // hollow
    // part pockets (clearance for battery / xiao / imu)
    part_pocket(batt_l+1, batt_w+1, batt_h+1, cap_t+1.0, 0, -18);
    part_pocket(xiao_l+1, xiao_w+1, xiao_h+1, cap_t+4.0, 0, 1);
    part_pocket(imu_l+1,  imu_w+1,  imu_h+1,  cap_t+8.3, 0, 1);
    // wheel / crown: shaft hole through the front (upper chest) + body recess
    through_hole(enc_d, 0, wheel_y, T-enc_d/2-0.5, T+2);
    translate([0, wheel_y, T-enc_body/2-3])
      cylinder(d=enc_body, h=enc_body/2+3, $fn=24);   // encoder body pocket
    // 2x side buttons
    side_hole(btn_d, btn_y,  1);
    side_hole(btn_d, btn_y, -1);
    side_hole(btn_d, btn_y2, 1);
    side_hole(btn_d, btn_y2,-1);
    // status LED window (front, thin remaining shell => diffuser insert)
    through_hole(led_d, led_x, led_y, T-1.0, T+2);
    // mic acoustic vent (front, shallow)
    translate([mic_x-mic_w/2, mic_y-mic_h/2, T-2.5])
      cube([mic_w, mic_h, 3]);
    // u.FL antenna exit slot at the bail tip
    translate([-ufl_w/2, tip_y-1, T/2-1]) cube([ufl_w, ufl_h+2, 3]);
    // USB-C cutout (side, XIAO edge connector) — field-serviceable
    side_hole(usb_h, usb_y,  1, w_box=usb_w);
    side_hole(usb_h, usb_y, -1, w_box=usb_w);
  }
  // lanyard bail (ring) at the tip — torus axis along Z
  translate([0, tip_y+1, T/2]) rotate([0,0,0])
    torus(5.0, 1.6);
}

module torus(R, r){
  rotate_extrude() translate([R,0,0]) circle(r=r, $fn=20);
}

// ---- CAP (back cover, press-fit lip) ----
module cap(){
  difference(){
    union(){
      // back plate
      linear_extrude(height=cap_t)
        offset(r=-0.4) teardrop_2d();
      // seating lip (sits inside the body pocket)
      translate([0,0,cap_t])
        linear_extrude(height=lip_h)
          offset(r=-inset-0.3) teardrop_2d();
    }
    // 4 M2 standoffs for the XIAO (optional screw mounting)
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
// Print body front-face-DOWN (bail tip up) so the teardrop lies flat. Cap flat.
// Scale all holes 1.05x if your printer runs tight. LED window: drop in a
// Ø6 translucent diffuser disc. Wheel crown: trim EC11 shaft to ~8 mm proud.
// Antenna: feed u.FL pigtail out the tip slot, dress along the bail, strain-relief
// with a dab of silicone. Battery: flat 302030 LiPo, swap via the cap.
//
// Refs:
//  XIAO ESP32-S3 Sense — https://www.seeedstudio.com/Seeed-XIAO-ESP32S3-Sense-p-5639.html
//  GY-521 MPU-6050 breakout dims — https://ifuturetech.org/product/gy-521-mpu-6050-3-axis-accelerometer-and-gyroscope-sensor/
//  EC11 encoder datasheet — https://www.mouser.com/datasheet/2/15/EC11-1370808.pdf
