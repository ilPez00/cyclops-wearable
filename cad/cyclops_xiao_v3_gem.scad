// Cyclops XIAO — V3 "Gem"
// Faceted jewel pendant: soft hexagonal prism with chamfered edges and a
// faceted bezel around the screen. Premium, angular-but-smooth.
//
// Render: openscad cyclops_xiao_v3_gem.scad
// Export: openscad -D 'PART="body"' -o v3_body.stl cyclops_xiao_v3_gem.scad

xiao_l = 21.0; xiao_w = 17.5; wall = 2.0;
base_h = 6.0; body_h = 12.0;
win_w = 28.0; win_h = 28.0;
$fn = 6;   // hexagonal facet feel

module hex_plate(l,w,h,r=3){
  // rounded hexagon prism
  hull(){
    for(a=[0:60:300])
      rotate([0,0,a]) translate([l/2-r,0,h/2]) sphere(r=r,$fn=20);
    for(a=[0:60:300])
      rotate([0,0,a+30]) translate([0,w/2-r,h/2]) sphere(r=r,$fn=20);
  }
}

module body(){
  difference(){
    union(){
      hex_plate(xiao_l+2*wall+8, xiao_w+2*wall+10, body_h, 4);
      // crown facets on top rim
      translate([0,0,body_h-1])
        cylinder(d=34, h=2, $fn=6);
    }
    translate([0,0,base_h]) hex_plate(xiao_l+2*wall, xiao_w+2*wall, body_h-base_h+2, 3);
    // screen window (top) with faceted bezel
    translate([0,0,body_h-3]) cube([win_w, win_h, 6], center=true);
    // bezel ring (raised lip around window)
    // USB-C at one hex flat
    translate([-19,0,base_h+1]) cube([5,11,7], center=true);
    // buttons on adjacent flats
    translate([16,-7,body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    translate([16, 7,body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    translate([0, 18,body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    // pendant bail (top loop)
    translate([0,-20,body_h/2]) rotate([90,0,0]) torus_bail();
  }
}
module torus_bail(){
  rotate_extrude(convexity=4)
    translate([5,0,0]) circle(r=2.8,$fn=20);
}

module lid(){
  difference(){
    hex_plate(xiao_l+2*wall+8, xiao_w+2*wall+10, 2.6, 4);
    translate([0,0,-1]) cube([win_w, win_h, 6], center=true);
  }
}

PART = undef;
if (!is_undef(PART) && PART=="body") body();
else if (!is_undef(PART) && PART=="lid") lid();
else { body(); translate([42,0,0]) lid(); }
