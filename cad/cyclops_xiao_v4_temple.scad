// Cyclops XIAO — V4 "Temple"
// Glasses-temple clip: low-profile lozenge that hugs a glasses arm. A sprung
// clip channel on the back slips over a 4-6 mm temple; board sits flat, screen
// faces forward. Lightest, most discreet variant.
//
// Render: openscad cyclops_xiao_v4_temple.scad
// Export: openscad -D 'PART="body"' -o v4_body.stl cyclops_xiao_v4_temple.scad

xiao_l = 21.0; xiao_w = 17.5; wall = 1.8;
base_h = 5.0; body_h = 10.0;
win_w = 28.0; win_h = 28.0;
$fn = 40;

module lozenge(l,w,h,r){
  hull(){
    for(x=[-1,1], y=[-1,1])
      translate([x*(l/2-r), y*(w/2-r), h/2]) sphere(r=r,$fn=24);
  }
}

module body(){
  difference(){
    union(){
      lozenge(xiao_l+2*wall+4, xiao_w+2*wall+4, body_h, 6);
    }
    // interior pocket
    translate([0,0,base_h]) lozenge(xiao_l+2*wall, xiao_w+2*wall, body_h-base_h+2, 4);
    // screen window (forward face = +Y, so screen points away from temple)
    translate([0, xiao_w/2+wall+1, body_h/2]) cube([win_w, 6, win_h], center=true);
    // USB-C at -X end
    translate([-16,0,base_h]) cube([5,11,7], center=true);
    // buttons +X end
    translate([15,-6,body_h-2]) cylinder(d=5,h=5,$fn=18,center=true);
    translate([15, 6,body_h-2]) cylinder(d=5,h=5,$fn=18,center=true);
    // --- clip channel on back (-Y) for temple arm ---
    // a C-channel: subtract a curved slot
    translate([0, -(xiao_w/2+wall+1), body_h/2]) rotate([90,0,0])
      cylinder(d=9, h=8, center=true, $fn=24);
    // slot opening (vertical slit so arm slides in)
    translate([0, -(xiao_w/2+wall-1), body_h/2]) cube([3, 12, 30], center=true);
  }
}

module lid(){
  // front face plate (covers screen side)
  difference(){
    lozenge(xiao_l+2*wall+4, xiao_w+2*wall+4, 1.8, 6);
    translate([0, xiao_w/2+wall+1, body_h/2]) cube([win_w, 6, win_h], center=true);
  }
}

PART = undef;
if (!is_undef(PART) && PART=="body") body();
else if (!is_undef(PART) && PART=="lid") lid();
else { body(); translate([xiao_l+30,0,0]) lid(); }
