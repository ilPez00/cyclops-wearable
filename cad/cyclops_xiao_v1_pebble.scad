// Cyclops XIAO — V1 "Pebble"
// Smooth squircle pendant with an integrated organic carry-loop.
// Pretty + printable: rounded everywhere, no sharp edges.
//
// Board: XIAO ESP32-S3 Sense (21 x 17.5 mm). Screen: ST7735 1.8" (window 28x28).
// Render both parts:  openscad cyclops_xiao_v1_pebble.scad
// Export: openscad -D 'PART="body"' -o v1_body.stl cyclops_xiao_v1_pebble.scad

xiao_l = 21.0; xiao_w = 17.5; wall = 2.0;
base_h = 6.0; body_h = 12.0;
win_w = 28.0; win_h = 28.0;
$fn = 48;

// rounded superellipse-ish plate via hull of spheres -> truly smooth
module blob(l,w,h,r){
  hull(){
    for(x=[-1,1], y=[-1,1])
      translate([x*(l/2-r), y*(w/2-r), h/2])
        sphere(r=r, $fn=32);
  }
}

module carry_loop(){
  // torus-ish loop on top, organic
  rotate([90,0,0])
    translate([0, body_h+6, 0])
      difference(){
        torus(r_maj=7, r_min=3.2);
        translate([0,-20,0]) cube([40,40,40],center=true);
      }
}
module torus(r_maj, r_min){
  rotate_extrude(convexity=4)
    translate([r_maj,0,0]) circle(r=r_min, $fn=24);
}

module body(){
  difference(){
    union(){
      blob(xiao_l+2*wall+6, xiao_w+2*wall+6, body_h, 7);
      carry_loop();
    }
    // interior pocket
    translate([0,0,base_h])
      blob(xiao_l+2*wall, xiao_w+2*wall, body_h-base_h+2, 5);
    // screen window (top)
    translate([0,0,body_h-3]) cube([win_w, win_h, 6], center=true);
    // USB-C slot (-X)
    translate([-16,0,base_h+1]) cube([5,11,7], center=true);
    // button wells (+X) BTN_A(3)/BTN_B(5)
    translate([15, -6, body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    translate([15,  6, body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    // wheel B(4) mid
    translate([15, 0, body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
  }
}

module lid(){
  difference(){
    blob(xiao_l+2*wall+6, xiao_w+2*wall+6, 2.4, 7);
    translate([0,0,-1]) cube([win_w, win_h, 6], center=true);
  }
}

PART = undef;
if (!is_undef(PART) && PART=="body") body();
else if (!is_undef(PART) && PART=="lid") lid();
else { body(); translate([xiao_l+34,0,0]) lid(); }
