// See imu.h. MPU/ITG over the Arduino Wire bus (shared D6/D7 with the OLED).
#include "imu.h"
#include <Arduino.h>
#include <Wire.h>

#ifndef ARDUINO
// Host (g++) build: no Wire, no sensor. Safe stubs so the unit/host gate links.
namespace cyclops {
Imu::Imu(uint8_t, int) {}
bool Imu::begin() { return false; }
bool Imu::update() { return false; }
int Imu::scroll_tilt() const { return 0; }
}
#else

namespace cyclops {

static constexpr int REG_SMPLRT_DIV = 0x19;
static constexpr int REG_GYRO_CFG    = 0x1B;
static constexpr int REG_ACCEL_CFG   = 0x1C;
static constexpr int REG_PWR_MGMT_1  = 0x6B;
static constexpr int REG_PWR_MGMT_2  = 0x6C;
static constexpr int REG_ACCEL_XOUT = 0x3B;
static constexpr int REG_GYRO_XOUT  = 0x43;
static constexpr int REG_WHOAMI     = 0x75;

static uint8_t read_reg(TwoWire& w, uint8_t addr, uint8_t reg) {
    w.beginTransmission(addr);
    w.write(reg);
    if (w.endTransmission(false) != 0) return 0xFF;
    w.requestFrom((int)addr, 1);
    return w.available() ? (uint8_t)w.read() : 0xFF;
}
static void write_reg(TwoWire& w, uint8_t addr, uint8_t reg, uint8_t v) {
    w.beginTransmission(addr);
    w.write(reg); w.write(v);
    w.endTransmission();
}
static int read_word(TwoWire& w, uint8_t addr, uint8_t reg) {
    w.beginTransmission(addr); w.write(reg);
    if (w.endTransmission(false) != 0) return 0;
    w.requestFrom((int)addr, 2);
    if (w.available() < 2) return 0;
    int hi = w.read(), lo = w.read();
    return (int16_t)((hi << 8) | lo);
}

Imu::Imu(uint8_t addr, int int_pin) : addr_(addr), int_pin_(int_pin) {}

bool Imu::begin() {
    Wire.begin();  // already begun by screen; harmless repeat
    uint8_t who = read_reg(Wire, addr_, REG_WHOAMI);
    // MPU-6050=0x68, MPU-9250=0x71/0x73, ICM-206xx=0x98/0x9C. Accept any ack.
    if (who == 0xFF) { ready_ = false; return false; }
    write_reg(Wire, addr_, REG_PWR_MGMT_1, 0x00);  // wake
    write_reg(Wire, addr_, REG_PWR_MGMT_2, 0x00);  // all axes on
    write_reg(Wire, addr_, REG_SMPLRT_DIV, 0x07);  // ~1kHz/8
    write_reg(Wire, addr_, REG_GYRO_CFG,  0x08);   // +/-500 dps
    write_reg(Wire, addr_, REG_ACCEL_CFG, 0x08);   // +/-4g
    if (int_pin_ >= 0) pinMode(int_pin_, INPUT);
    ready_ = true;
    return true;
}

bool Imu::update() {
    if (!ready_) return false;
    s_.ax = read_word(Wire, addr_, REG_ACCEL_XOUT);
    s_.ay = read_word(Wire, addr_, REG_ACCEL_XOUT + 2);
    s_.az = read_word(Wire, addr_, REG_ACCEL_XOUT + 4);
    s_.gx = read_word(Wire, addr_, REG_GYRO_XOUT);
    s_.gy = read_word(Wire, addr_, REG_GYRO_XOUT + 2);
    s_.gz = read_word(Wire, addr_, REG_GYRO_XOUT + 4);
    // heading: integrate yaw rate (no magnetometer on MPU-6050)
    heading_ += s_.gz / 32;        // dps->deg-ish per ~50ms sample
    if (heading_ < 0) heading_ += 360;
    if (heading_ >= 360) heading_ -= 360;
    s_.heading = heading_;
    // tilt from accel (gravity axis). pitch/roll in degrees.
    s_.pitch = (int)(57.3 * atan2((double)s_.ax, sqrt((double)s_.ay*s_.ay + (double)s_.az*s_.az)));
    s_.roll  = (int)(57.3 * atan2((double)s_.ay, (double)s_.az));
    return true;
}

int Imu::scroll_tilt() const {
    if (!ready_) return 0;
    // tilt forward (pitch down) -> +1, back -> -1; deadzone 15 deg
    if (s_.pitch > 15) return 1;
    if (s_.pitch < -15) return -1;
    return 0;
}

}  // namespace cyclops
#endif  // ARDUINO
