// Sustained-slouch posture cue from imu.cpp's pitch reading. Pure logic,
// host-testable, mirrors presence.h/gestures.h's shape.
//
// Deviation-from-baseline rather than an absolute degree+sign: chest/lapel
// mounting orientation varies enough (and hasn't been verified on real
// hardware yet) that a hardcoded "positive pitch = slouch" assumption would
// be guessing. calibrate() captures "neutral, sitting upright" once (e.g. on
// boot, or a menu action); poll() measures drift from that baseline.
#ifndef POSTURE_H
#define POSTURE_H
#include <cstdint>
#include <cstdlib>
namespace cyclops {

class PostureDetector {
public:
    // slouch_deg: |pitch - baseline| beyond this counts as slouching.
    // sustained_ms: how long it must hold before firing (default 10 min).
    PostureDetector(int slouch_deg = 30, uint32_t sustained_ms = 600000)
        : slouch_deg_(slouch_deg), sustained_ms_(sustained_ms) {}

    void calibrate(int neutral_pitch) { baseline_ = neutral_pitch; calibrated_ = true; }
    bool calibrated() const { return calibrated_; }

    // Call with the current pitch (degrees) + now (millis()). Returns true
    // once the slouch has been sustained for sustained_ms_ straight. Any
    // return to neutral resets the timer immediately (no fatigue-testing
    // the wearer with a stale flag).
    bool poll(int pitch, uint32_t now) {
        if (!calibrated_) return false;
        bool slouching_now = std::abs(pitch - baseline_) >= slouch_deg_;
        bool was = flagged_;
        if (!slouching_now) {
            slouch_since_ = 0;
            flagged_ = false;
        } else {
            if (slouch_since_ == 0) slouch_since_ = now;
            flagged_ = (now - slouch_since_) >= sustained_ms_;
        }
        changed_ = (flagged_ != was);
        return flagged_;
    }

    bool changed() const { return changed_; }

private:
    int slouch_deg_;
    uint32_t sustained_ms_;
    int baseline_ = 0;
    bool calibrated_ = false, flagged_ = false, changed_ = false;
    uint32_t slouch_since_ = 0;
};

}  // namespace cyclops
#endif  // POSTURE_H
