// Cyclops XIAO S3 Sense — aesthetic case variants
// Three looks over the same functional core (board pocket, screen window,
// USB-C cutout, button/wheel holes, strap slots).
//   VARIANT = "pebble" | "tech" | "skeleton"   (default pebble)
// Render: openscad -D 'VARIANT="tech"' -o out.png cyclops_xiao_variants.scad
//
// Core dims (shared)
xiao_l = 21.0; xiao_w = 17.5; wall = 2.0;
base_h = 6.0;  lid_h = 10.0;
screen_w = 35.0; win_w = 28.0; win_h = 28.0;
body_l = xiao_l + 2*wall + 4;       // 29
body_w = max(xiao_w, screen_w) + 2*wall;  // 39
body_h = lid_h + 2;                 // 12
$fn = 48;

// ---------- shared helpers ----------
module rbox(l,w,h,r){ minkowski(){ cube([l-2*r,w-2*r,h-2*r]); sphere(r); } }

module btn_hole(x,y,d=6.0){ translate([x,y,body_h-2]) cylinder(d=d,h=4,$fn=24); }
module strap_slot(y){ translate([-1,y,body_h/2-4]) cube([4,8,3]); }

// functional interior cutouts applied to any shell
module cutouts(){
  // hollow pocket
  translate([wall,wall,base_h]) cube([body_l-2*wall,body_w-2*wall,body_h-base_h+1]);
  // screen window
  translate([body_l/2-win_w/2, body_w/2-win_h/2, body_h-3]) cube([win_w,win_h,4]);
  // USB-C
  translate([-1, body_w/2-5, base_h+1]) cube([4,10,5]);
  // buttons
  btn_hole(body_l-wall-4, body_w/2-7);
  btn_hole(body_l-wall-4, body_w/2+7);
  btn_hole(body_l-wall-4, body_w/2);
  // strap slots
  strap_slot(body_w/2-7); strap_slot(body_w/2+7);
}

// thin lid with screen opening
module lid(style="pebble"){
  if (style=="tech"){
    difference(){
      minkowski(){ cube([body_l-3,body_w-3,2]); rotate([0,0,45]) cube([1.5,1.5,2]); }
      translate([body_l/2-win_w/2, body_w/2-win_h/2, -1]) cube([win_w,win_h,4]);
    }
  } else {
    difference(){
      rbox(body_l, body_w, 2.0, 3);
      translate([body_l/2-win_w/2, body_w/2-win_h/2, -1]) cube([win_w,win_h,4]);
    }
  }
}

// ---------- VARIANT A: pebble (smooth, organic) ----------
module pebble(){
  difference(){
    rbox(body_l, body_w, body_h, 5);   // very round
    cutouts();
  }
}

// ---------- VARIANT B: tech (chamfered + side vents) ----------
module tech(){
  difference(){
    minkowski(){ cube([body_l-4, body_w-4, body_h-3]); rotate([0,0,45]) cube([2.5,2.5,body_h-3]); }
    cutouts();
    // decorative vent slits on -X face (non-structural)
    for (i=[0:3]) translate([1, body_w/2-10+i*5, base_h+2]) cube([2,2,4]);
  }
}

// ---------- VARIANT C: skeleton (ultralight, glasses-mount) ----------
module skeleton(){
  difference(){
    rbox(body_l, body_w, body_h, 4);
    cutouts();
    // large weight-reduction windows on side walls
    translate([body_l/2-9, -1, base_h+1]) cube([18,3,6]);
    translate([body_l/2-9, body_w-2, base_h+1]) cube([18,3,6]);
    // top lattice around screen
    for (i=[0:5]) translate([4+i*3.5, 4, body_h-2]) cube([2,body_w-8,3]);
  }
}

// ---------- dispatch ----------
VARIANT = undef;
v = is_undef(VARIANT) ? "pebble" : VARIANT;
if (v == "pebble")      { pebble(); translate([body_l+6,0,0]) lid("pebble"); }
else if (v == "tech")   { tech();   translate([body_l+6,0,0]) lid("tech"); }
else if (v == "skeleton"){ skeleton(); translate([body_l+6,0,0]) lid("pebble"); }
else { pebble(); translate([body_l+6,0,0]) lid("pebble"); }
