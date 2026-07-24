// Audio gating primitives for Cyclops.
//
// AudioTrigger: Sudden loud-sound detector from PCM16 peak amplitude (fire
// alarm, shout). Fires once per refractory window.
//
// VadGate: RMS-based voice activity detector. Returns true when a PCM16
// chunk's RMS exceeds threshold. Tracks a running ambient RMS floor for
// adaptive tuning. Used as a pre-encode gate so silence doesn't consume
// BLE bandwidth or transcription budget.
//
// Both are pure logic — no Arduino/hardware deps, host-testable with g++.
#ifndef AUDIO_TRIGGER_H
#define AUDIO_TRIGGER_H
#include <cstdint>
#include <cstdlib>
#include <cmath>
namespace cyclops {

class AudioTrigger {
public:
    AudioTrigger(int peak_thresh = 20000, uint32_t refractory_ms = 3000)
        : peak_thresh_(peak_thresh), refractory_ms_(refractory_ms) {}

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

// RMS-based voice activity detector. Returns true when a chunk's RMS
// exceeds the energy threshold. Tracks ambient RMS floor; threshold
// floats at max(floor * MULTIPLIER, MIN_RMS) after a calibration period.
class VadGate {
public:
    // rms_threshold: static fallback when not enough samples for adaptive.
    // calibration_samples: how many chunks to measure before adaptive kicks in.
    // ambient_multiplier: threshold = ambient_rms * this.
    explicit VadGate(float rms_threshold = 500.0f,
                     int calibration_samples = 20,
                     float ambient_multiplier = 3.0f)
        : rms_threshold_(rms_threshold)
        , cal_samples_(calibration_samples)
        , ambient_mult_(ambient_multiplier) {}

    // Feed one PCM16 chunk. Returns true if RMS >= threshold (speech likely).
    bool feed(const int16_t* samples, size_t n) {
        float rms = calc_rms(samples, n);
        last_rms_ = rms;

        if (cal_count_ < cal_samples_) {
            // Calibration: accumulate RMS floor
            ambient_sum_ += rms;
            cal_count_++;
            if (cal_count_ >= cal_samples_) {
                ambient_floor_ = ambient_sum_ / (float)cal_samples_;
                adaptive_threshold_ = ambient_floor_ * ambient_mult_;
                if (adaptive_threshold_ < rms_threshold_)
                    adaptive_threshold_ = rms_threshold_;
            }
            return false;  // during calibration, don't gate
        }

        // Track ambient floor with slow decay when below threshold
        if (rms < adaptive_threshold_) {
            ambient_floor_ = ambient_floor_ * 0.99f + rms * 0.01f;
            adaptive_threshold_ = ambient_floor_ * ambient_mult_;
            if (adaptive_threshold_ < rms_threshold_)
                adaptive_threshold_ = rms_threshold_;
        }

        return rms >= adaptive_threshold_;
    }

    float last_rms() const { return last_rms_; }
    float threshold() const { return adaptive_threshold_; }
    float ambient_floor() const { return ambient_floor_; }
    bool calibrated() const { return cal_count_ >= cal_samples_; }
    void reset() {
        cal_count_ = 0; ambient_sum_ = 0.0f; ambient_floor_ = 0.0f;
        adaptive_threshold_ = rms_threshold_; last_rms_ = 0.0f;
    }

private:
    static float calc_rms(const int16_t* samples, size_t n) {
        if (n == 0) return 0.0f;
        double sum_sq = 0.0;
        for (size_t i = 0; i < n; ++i) {
            double s = (double)samples[i];
            sum_sq += s * s;
        }
        return (float)std::sqrt(sum_sq / (double)n);
    }

    float rms_threshold_;
    int cal_samples_;
    float ambient_mult_;
    int cal_count_ = 0;
    float ambient_sum_ = 0.0f;
    float ambient_floor_ = 0.0f;
    float adaptive_threshold_ = 500.0f;
    float last_rms_ = 0.0f;
};

}  // namespace cyclops
#endif  // AUDIO_TRIGGER_H
