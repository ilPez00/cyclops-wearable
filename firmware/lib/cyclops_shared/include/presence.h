// On/off-body detection from raw accelerometer stability. Pure logic, no HW,
// so the host gate (g++) exercises it — mirrors gestures.h's shape.
//
// A worn device picks up continuous micro-jitter (pulse, breathing, subtle
// movement); a device resting on a desk (in any orientation) reads a
// near-constant gravity vector. off_body() latches true only after the
// accel magnitude stays within `band` of its own running average for
// `stable_ms` straight — holding deliberately still for a moment must not
// trip it; only a genuinely undisturbed device does.
//
// Deliberately magnitude-*stability*-based, not a fixed "~1g" threshold:
// the raw units depend on the accelerometer's full-scale range register
// (e.g. imu.cpp sets +/-4g), which this class has no business knowing.
#ifndef PRESENCE_H
#define PRESENCE_H
#include <cstdint>
#include <cmath>
namespace cyclops {

class PresenceDetector {
public:
    // stable_ms: how long the magnitude must stay flat before declaring
    // off-body. band: max allowed drift from the running average, as a
    // fraction of that average (0.02 = 2%).
    PresenceDetector(uint32_t stable_ms = 4000, float band = 0.02f)
        : stable_ms_(stable_ms), band_(band) {}

    // Call every tick with raw accel + current time (millis()). Returns the
    // current off-body state (use changed() to detect the edge).
    bool poll(int ax, int ay, int az, uint32_t now) {
        float mag = std::sqrt((float)ax * ax + (float)ay * ay + (float)az * az);
        bool prev = off_body_;
        if (!have_avg_) {
            avg_ = mag; have_avg_ = true; still_since_ = now;
        }
        float ref = avg_ > 1.0f ? avg_ : 1.0f;
        float drift = std::fabs(mag - avg_) / ref;
        if (drift > band_) {
            // real motion: reset the stillness window and re-anchor
            avg_ = mag; still_since_ = now; off_body_ = false;
        } else {
            avg_ = avg_ * 0.9f + mag * 0.1f;  // slow-track small drift (e.g. thermal)
            if (now - still_since_ >= stable_ms_) off_body_ = true;
        }
        changed_ = (off_body_ != prev);
        return off_body_;
    }

    bool off_body() const { return off_body_; }
    // True only on the tick where the state actually flipped.
    bool changed() const { return changed_; }

private:
    uint32_t stable_ms_;
    float band_;
    bool have_avg_ = false, off_body_ = false, changed_ = false;
    float avg_ = 0;
    uint32_t still_since_ = 0;
};

}  // namespace cyclops
#endif  // PRESENCE_H
