// Sudden loud-sound detector (fire alarm, shout, name called across a room)
// from PCM16 peak amplitude. Pure logic, host-testable, same shape as
// presence.h/posture.h. DSP-threshold tier only — a real wake-word (e.g.
// "hey Cyclops") needs ESP-SR/WakeNet, a bigger lift, deferred.
#ifndef AUDIO_TRIGGER_H
#define AUDIO_TRIGGER_H
#include <cstdint>
#include <cstdlib>
namespace cyclops {

class AudioTrigger {
public:
    // peak_thresh: PCM16 absolute sample value above which a chunk counts as
    // "loud" (16-bit range +/-32767; a shout/alarm clips well above half
    // scale). refractory_ms: minimum gap between two fires, so one sustained
    // loud event (the alarm keeps ringing) doesn't spam.
    AudioTrigger(int peak_thresh = 20000, uint32_t refractory_ms = 3000)
        : peak_thresh_(peak_thresh), refractory_ms_(refractory_ms) {}

    // Feed one chunk's samples + now (millis()). Returns true (once per
    // refractory window) when the chunk's peak crosses peak_thresh_.
    bool feed(const int16_t* samples, size_t n, uint32_t now) {
        int peak = 0;
        for (size_t i = 0; i < n; ++i) {
            int v = std::abs((int)samples[i]);
            if (v > peak) peak = v;
        }
        last_peak_ = peak;
        if (peak <= peak_thresh_) return false;
        if (fired_once_ && now - last_fire_ < refractory_ms_) return false;
        last_fire_ = now;
        fired_once_ = true;
        return true;
    }

    int last_peak() const { return last_peak_; }

private:
    int peak_thresh_;
    uint32_t refractory_ms_;
    int last_peak_ = 0;
    uint32_t last_fire_ = 0;
    bool fired_once_ = false;
};

}  // namespace cyclops
#endif  // AUDIO_TRIGGER_H
