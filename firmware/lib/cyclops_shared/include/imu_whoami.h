#ifndef CYCLOPS_IMU_WHOAMI_H
#define CYCLOPS_IMU_WHOAMI_H
// WHO_AM_I identification for the MVP accelerometer (docs/43 §2, open item C4).
//
// Why this exists: imu.cpp speaks MPU-family registers (PWR_MGMT_1 0x6B,
// ACCEL_XOUT 0x3B) and used to accept *any* WHO_AM_I ack. An LSM6DS3 has a
// different register map -- its WHO_AM_I lives at 0x0F, not 0x75 -- so reading
// 0x75 on one returns whatever that address holds, the driver then writes MPU
// registers into an LSM6DS3, and the sensor reports nonsense. That presents as
// "tilt scroll does random things", never as an error. So: identify what
// actually answered, drive only what this driver can speak, and refuse the rest
// with a one-line reason the serial log / HUD can show.
//
// Header-only, host-safe: firmware/shared/test_imu_whoami.cpp runs it under the
// native gate (`cd firmware && make proto`), no board required.
#include <stdint.h>
#include <stdio.h>

namespace cyclops {

enum ImuChip : uint8_t {
    IMU_NONE = 0,     // nothing answered at the address (bus NAK)
    IMU_MPU6050,      // 0x68 (MPU-6000 / most clones report this too)
    IMU_MPU6500,      // 0x70
    IMU_MPU9250,      // 0x71 (0x73 on the 9255 / some clones)
    IMU_ICM206,       // 0x98 / 0x9C (ICM-206xx family)
    IMU_UNSUPPORTED,  // something answered, but not a part this driver speaks
};

inline ImuChip imu_identify(uint8_t who) {
    switch (who) {
        case 0xFF: return IMU_NONE;   // imu.cpp's read_reg sentinel
        case 0x68: return IMU_MPU6050;
        case 0x70: return IMU_MPU6500;
        case 0x71: return IMU_MPU9250;
        case 0x73: return IMU_MPU9250;
        case 0x98: return IMU_ICM206;
        case 0x9C: return IMU_ICM206;
        default:   return IMU_UNSUPPORTED;
    }
}

// Only these are driven -- they share the register map imu.cpp writes.
inline bool imu_supported(ImuChip c) {
    return c == IMU_MPU6050 || c == IMU_MPU6500 || c == IMU_MPU9250 ||
           c == IMU_ICM206;
}

inline const char* imu_chip_name(ImuChip c) {
    switch (c) {
        case IMU_MPU6050:     return "MPU-6050";
        case IMU_MPU6500:     return "MPU-6500";
        case IMU_MPU9250:     return "MPU-9250";
        case IMU_ICM206:      return "ICM-206xx";
        case IMU_UNSUPPORTED: return "unsupported";
        default:              return "no device";
    }
}

// One line for the serial log. `who` is the raw WHO_AM_I byte, reported by
// value for an unrecognised part so the bench session can see what answered.
inline void imu_status_line(uint8_t who, unsigned addr, char* out, unsigned cap) {
    if (!out || cap == 0) return;
    ImuChip c = imu_identify(who);
    if (imu_supported(c)) {
        snprintf(out, cap, "imu: %s ok (whoami 0x%02X at 0x%02X)",
                 imu_chip_name(c), who, addr);
    } else if (c == IMU_NONE) {
        snprintf(out, cap, "imu: no device at 0x%02X (check SDA/SCL + power)",
                 addr);
    } else {
        snprintf(out, cap,
                 "imu: whoami 0x%02X unsupported -- LSM6DS3? its WHO_AM_I is "
                 "0x0F, use an MPU-6050-class part", who);
    }
}

// Short form that fits the 21-char HINT row / a toast. Empty when fine.
inline const char* imu_refusal_short(ImuChip c) {
    if (imu_supported(c)) return "";
    if (c == IMU_NONE) return "imu: not found";
    return "imu: unsupported chip";
}

}  // namespace cyclops
#endif  // CYCLOPS_IMU_WHOAMI_H
