// IMU driver for the XIAO ESP32-S3 Sense (I2C bus, shared with the OLED).
// Supports the InvenSense ITG/MPU family (MPU-6050, MPU-9250, ICM-206xx):
//   - accelerometer + gyroscope over I2C
//   - heading (yaw, from magnetometer if present, else integrated gyro)
//   - pitch/roll for tilt-aware auto-scroll
// HW-123 breakouts (ITG/MPU) wire SDA->D6, SCL->D7, INT->D1 (optional).
#ifndef IMU_H
#define IMU_H
#include <cstdint>
namespace cyclops {

struct ImuSample {
    int ax = 0, ay = 0, az = 0;   // raw accel (mg-ish, device units)
    int gx = 0, gy = 0, gz = 0;   // raw gyro (dps-ish)
    int heading = 0;              // degrees 0..359 (yaw)
    int pitch = 0, roll = 0;      // degrees, for tilt
};

class Imu {
public:
    // addr: 0x68 (AD0 low) or 0x69 (AD0 high). int_pin: optional IRQ (D1).
    Imu(uint8_t addr = 0x68, int int_pin = 1);

    // Initialize the sensor (wakes from sleep, sets ranges). Returns false if
    // no device answers at addr. Host-safe (no-op, returns false).
    bool begin();

    // Read + update. Call from loop. Returns false on bus error.
    bool update();

    const ImuSample& sample() const { return s_; }
    bool ready() const { return ready_; }

    // Tilt auto-scroll: positive = tilt down (scroll forward), negative = up.
    int scroll_tilt() const;

private:
    uint8_t addr_;
    int int_pin_;
    bool ready_ = false;
    ImuSample s_;
    int heading_ = 0;   // integrated yaw (no mag on MPU-6050)
    int last_gz_ = 0;
};

}  // namespace cyclops
#endif  // IMU_H
