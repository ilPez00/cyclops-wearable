// Host gate for firmware/lib/cyclops_shared/include/imu_whoami.h (docs/43 C4).
//
// The bug this pins: imu.cpp accepted ANY WHO_AM_I ack, so a part with a
// different register map (on an LSM6DS3, reading 0x75 returns junk) passed as
// "ok", the driver wrote MPU registers into it, and the sensor produced
// nonsense accel values -- silent garbage instead of an error. Identification
// must name the MPU family, refuse everything else, and say why.
#include <cassert>
#include <cstdio>
#include <cstring>

#include "imu_whoami.h"

int main() {
    using namespace cyclops;

    // ---- table: what each WHO_AM_I byte means ----
    assert(imu_identify(0xFF) == IMU_NONE);        // bus NAK sentinel
    assert(imu_identify(0x68) == IMU_MPU6050);
    assert(imu_identify(0x70) == IMU_MPU6500);
    assert(imu_identify(0x71) == IMU_MPU9250);
    assert(imu_identify(0x73) == IMU_MPU9250);
    assert(imu_identify(0x98) == IMU_ICM206);
    assert(imu_identify(0x9C) == IMU_ICM206);

    assert(imu_supported(IMU_MPU6050));
    assert(imu_supported(IMU_MPU6500));
    assert(imu_supported(IMU_MPU9250));
    assert(imu_supported(IMU_ICM206));
    assert(!imu_supported(IMU_NONE));
    assert(!imu_supported(IMU_UNSUPPORTED));

    // ---- the failure this ticket exists for: unknown parts are REFUSED ----
    // 0x6A/0x6B are LSM6DS3-family WHO_AM_I values; 0x00/0x0F/0xAA are junk a
    // wrong or half-dead part can answer with. None may classify as drivable.
    const uint8_t refuse[] = {0x6A, 0x6B, 0x00, 0x0F, 0xAA};
    for (unsigned i = 0; i < sizeof(refuse); ++i) {
        ImuChip c = imu_identify(refuse[i]);
        assert(!imu_supported(c));
        assert(c == IMU_UNSUPPORTED);
        assert(std::strlen(imu_refusal_short(c)) > 0);   // never silent
    }

    // ---- the status line names the part, for the serial log ----
    char line[96];
    imu_status_line(0x68, 0x68, line, sizeof(line));
    assert(std::strstr(line, "MPU-6050") != nullptr);
    assert(std::strstr(line, "0x68") != nullptr);

    imu_status_line(0xFF, 0x68, line, sizeof(line));
    assert(std::strstr(line, "no device") != nullptr);

    imu_status_line(0x6A, 0x68, line, sizeof(line));
    assert(std::strstr(line, "unsupported") != nullptr);
    assert(std::strstr(line, "0x6A") != nullptr);   // raw byte is reported
    assert(std::strstr(line, "0x0F") != nullptr);   // and the actual reason

    // truncation safety: a tiny buffer stays NUL-terminated, no overrun
    char tiny[8];
    imu_status_line(0x6A, 0x68, tiny, sizeof(tiny));
    assert(std::strlen(tiny) == sizeof(tiny) - 1);

    // short refusal fits the 21-char HINT row / a toast, and is empty when fine
    assert(std::strlen(imu_refusal_short(IMU_NONE)) <= 21);
    assert(std::strlen(imu_refusal_short(IMU_UNSUPPORTED)) <= 21);
    assert(imu_refusal_short(IMU_MPU6050)[0] == '\0');

    std::printf("ALL IMU WHO_AM_I TESTS PASSED\n");
    return 0;
}
