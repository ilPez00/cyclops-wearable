// Cyclops XIAO — V2 "Leaf"
// Elegant teardrop/leaf pendant: wide end holds the board+screen, narrow
// end tapers to a lanyard eye. Organic, fashion-jewelry feel.
//
// Render: openscad cyclops_xiao_v2_leaf.scad
// Export: openscad -D 'PART="body"' -o v2_body.stl cyclops_xiao_v2_leaf.scad

xiao_l = 21.0; xiao_w = 17.5; wall = 2.0;
base_h = 6.0; body_h = 12.0;
win_w = 28.0; win_h = 28.0;
$fn = 48;

// leaf outline in XZ: wide at +X (board), tip at -X (lanyard)
module leaf_profile(h){
  // 2D leaf shape
  polygon(points=[
    [ 22, 0],   // tip (lanyard)
    [ 14, 11],
    [ 6,  16],
    [-6,  16],
    [-16, 12],
    [-18, 0],   // back
    [-16,-12],
    [-6, -16],
    [ 6, -16],
    [ 14,-11]
  ]);
}
module leaf_solid(h){
  linear_extrude(height=h, center=false, convexity=4, scale=1.0)
    leaf_profile();
}

module body(){
  difference(){
    union(){
      leaf_solid(body_h);
      // lanyard eye at tip
      translate([-20,0,body_h/2]) rotate([0,90,0])
        torus_eye();
    }
    translate([2,0,base_h]) scale([0.92,0.92,1])
      leaf_solid(body_h-base_h+2);
    // screen window on the wide flat area (top)
    translate([2,0,body_h-3]) cube([win_w, win_h, 6], center=true);
    // USB-C at back
    translate([-16,0,base_h+1]) cube([5,11,7], center=true);
    // buttons near wide end
    translate([14,-6,body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    translate([14, 6,body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
    translate([14, 0,body_h-2]) cylinder(d=5.5,h=5,$fn=20,center=true);
  }
}
module torus_eye(){
  rotate_extrude(convexity=4)
    translate([4,0,0]) circle(r=2.6,$fn=20);
}

module lid(){
  difference(){
    leaf_solid(2.4);
    translate([2,0,-1]) cube([win_w, win_h, 6], center=true);
  }
}

PART = undef;
if (!is_undef(PART) && PART=="body") body();
else if (!is_undef(PART) && PART=="lid") lid();
else { body(); translate([48,0,0]) lid(); }
