// Host-gate tests for VadGate (RMS energy voice activity detector).
// Compile: g++ -std=c++17 -I shared/include -I lib/cyclops_shared/include \
//                 -I xiao/src shared/test_vad.cpp -o /tmp/cyclops_test_vad
#include "audio_trigger.h"
#include <cstdio>
#include <cstring>
#include <cmath>

static int failures = 0;
#define TEST(name) do { printf("  %-44s ", name); } while(0)
#define PASS() do { printf("PASS\n"); } while(0)
#define FAIL(msg) do { printf("FAIL: %s\n", msg); ++failures; } while(0)
#define ASSERT(cond, msg) do { if (!(cond)) { FAIL(msg); return; } } while(0)

static void test_silence_below_threshold() {
    TEST("silence does not trigger");
    cyclops::VadGate vad(500.0f, 0);  // skip calibration, use static threshold
    int16_t silence[256] = {0};
    ASSERT(!vad.feed(silence, 256), "silence should not trigger");
    ASSERT(vad.last_rms() < 1.0f, "RMS of silence should be near zero");
    PASS();
}

static void test_loud_above_threshold() {
    TEST("loud speech triggers");
    cyclops::VadGate vad(500.0f, 0);
    int16_t loud[256];
    for (int i = 0; i < 256; ++i) loud[i] = 8000;
    ASSERT(vad.feed(loud, 256), "loud signal should trigger");
    ASSERT(vad.last_rms() > 500.0f, "RMS should exceed threshold");
    PASS();
}

static void test_boundary() {
    TEST("signal exactly at threshold");
    cyclops::VadGate vad(500.0f, 0);
    // RMS of constant 707 gives exactly 707 (sqrt(707^2) = 707)
    int16_t at_thresh[128];
    for (int i = 0; i < 128; ++i) at_thresh[i] = 500;
    ASSERT(vad.feed(at_thresh, 128), "signal at threshold should trigger (RMS >= threshold)");
    PASS();
}

static void test_just_below_threshold() {
    TEST("signal just below threshold does not trigger");
    cyclops::VadGate vad(500.0f, 0);
    int16_t quiet[128];
    for (int i = 0; i < 128; ++i) quiet[i] = 499;
    ASSERT(!vad.feed(quiet, 128), "signal below threshold should not trigger");
    PASS();
}

static void test_calibration_raises_threshold() {
    TEST("calibration raises threshold in noisy environment");
    cyclops::VadGate vad(100.0f, 10, 3.0f);  // 10 calibration chunks, 3x multiplier
    int16_t noisy[64];
    for (int i = 0; i < 64; ++i) noisy[i] = 2000;  // high ambient noise
    // Feed calibration chunks (they return false during calibration)
    for (int c = 0; c < 10; ++c) ASSERT(!vad.feed(noisy, 64), "calibration chunk should return false");
    ASSERT(vad.calibrated(), "should be calibrated after 10 chunks");
    ASSERT(vad.ambient_floor() > 100.0f, "ambient floor should be high");
    // Now threshold should be ~3x the ambient floor
    float t = vad.threshold();
    ASSERT(t > 1000.0f, "adaptive threshold should be much higher than default");
    PASS();
}

static void test_mixed_speech_and_silence() {
    TEST("speech frames pass, silence frames block");
    cyclops::VadGate vad(500.0f, 0);
    int16_t silence[128] = {0};
    int16_t speech[128];
    for (int i = 0; i < 128; ++i) speech[i] = 10000;

    ASSERT(!vad.feed(silence, 128), "silence before speech blocked");
    ASSERT(vad.feed(speech, 128), "speech passes");
    ASSERT(!vad.feed(silence, 128), "silence after speech blocked");
    PASS();
}

static void test_reset() {
    TEST("reset clears calibration state");
    cyclops::VadGate vad(500.0f, 5, 3.0f);
    int16_t buf[64];
    for (int i = 0; i < 64; ++i) buf[i] = 3000;
    for (int c = 0; c < 5; ++c) vad.feed(buf, 64);
    ASSERT(vad.calibrated(), "calibrated before reset");
    vad.reset();
    ASSERT(!vad.calibrated(), "not calibrated after reset");
    ASSERT(vad.last_rms() == 0.0f, "RMS reset to zero");
    PASS();
}

int main() {
    printf("VadGate host-gate tests\n");
    test_silence_below_threshold();
    test_loud_above_threshold();
    test_boundary();
    test_just_below_threshold();
    test_calibration_raises_threshold();
    test_mixed_speech_and_silence();
    test_reset();
    printf("\n%d failures\n", failures);
    return failures;
}
