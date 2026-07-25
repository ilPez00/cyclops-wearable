// Xiao ESP32 S3 Sense Case v2
// Wider, thicker, with battery/IMU/button
// Style: Bryła1 (base) + Bryła2 (sliding lid with camera notch)

/* [Dimensions] */
W = 88;         // overall X (was 65)
H = 26;         // overall Y (was 22)
D = 20;         // overall Z (was 13.4) — thicker for battery
t = 2.2;        // wall thickness
floor = 2.0;    // bottom floor thickness
lid_t = 1.6;    // lid thickness
gap = 0.25;     // lid sliding clearance

/* [Camera Notch] */
cam_w = 9.5;
cam_h = 9.0;

/* [I/O opening on right wall] */
io_w = 15;      // wide enough for USB-C + SD
io_h = 10;
io_z = 7;

/* [Battery 301230] */
bat_w = 32;
bat_h = 14;
bat_d = 6.5;

/* [IMU GY-521] */
imu_w = 22;
imu_h = 17;
imu_d = 5;

/* [Button] */
btn_r = 6.5;    // panel-mount button radius
btn_z = 10;     // Z center of button

/* [Render] */
PART = "both"; // "base" "lid" "both"

// --- Derived ---
iw = W - 2*t;           // interior width
ih = H - 2*t;           // interior height
lid_z = D - lid_t;      // lid Z position
cam_y = H/2 - cam_h/2;  // camera notch Y

// I/O opening Z range
io_z0 = io_z - io_h/2;
io_z1 = io_z + io_h/2;

// Battery position (left side)
bat_x = t + 2;
bat_y = H/2 - bat_h/2;

// IMU position (between battery and Xiao area)
imu_x = bat_x + bat_w + 3;
imu_y = H/2 - imu_h/2;

// ============================================================
// BASE
// ============================================================
module base() {
    difference() {
        // Outer shell
        cube([W, H, D]);

        // Interior cavity
        translate([t, t, floor])
            cube([iw, ih, lid_z - floor + 0.01]);

        // Lid recess on top
        translate([gap, gap, lid_z - 0.01])
            cube([W - 2*gap, H - 2*gap, lid_t + 0.02]);

        // I/O opening — right wall (USB-C + SD)
        translate([W - 0.01, H/2 - io_w/2, io_z0])
            cube([t + 0.02, io_w, io_h]);

        // Button hole — front wall (Y+)
        translate([W/2, H - 0.01, btn_z])
            rotate([90, 0, 0])
            cylinder(r=btn_r, h=t + 0.02, $fn=36);

        // Battery positioning pocket (1mm deep depression in floor)
        translate([bat_x, bat_y, floor - 1.0])
            cube([bat_w, bat_h, 1.0]);

        // IMU positioning pocket (1mm deep depression in floor)
        translate([imu_x, imu_y, floor - 1.0])
            cube([imu_w, imu_h, 1.0]);

        // Camera pass-through (space for camera module under lid notch)
        // Stops short of the exterior wall
        translate([W - cam_w - 3, cam_y - 1, lid_z - 4.5])
            cube([cam_w + 1, cam_h + 2, 4.5 + 0.01]);
    }
}

// ============================================================
// LID  (slides into top recess of base)
// ============================================================
module lid() {
    difference() {
        // Lid body
        translate([gap, gap, lid_z])
            cube([W - 2*gap, H - 2*gap, lid_t]);

        // Camera notch on right edge
        translate([W - gap - cam_w, cam_y, lid_z - 0.01])
            cube([cam_w + gap + 0.01, cam_h, lid_t + 0.02]);
    }
}

// ============================================================
// RENDER
// ============================================================
if (PART == "base" || PART == "both")
    base();

if (PART == "lid" || PART == "both")
    translate([W + 5, 0, 0])
        lid();
