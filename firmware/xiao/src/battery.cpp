// See battery.h. ADC divider math + host stubs.
#include "battery.h"

#ifndef ARDUINO
// Host (g++) build: no ADC. Predictable fake pack for the host gate.
namespace cyclops {
Battery::Battery(int pin, int full, int empty, int n, int divider, int enable_pin)
    : pin_(pin), full_mv_(full), empty_mv_(empty), num_samples_(n),
      divider_(divider), enable_pin_(enable_pin) {}
void Battery::begin() { last_mv_ = 3950; }
int Battery::read_mv() { return last_mv_; }
int Battery::percent() {
    int pct = (last_mv_ - empty_mv_) * 100 / (full_mv_ - empty_mv_);
    if (pct < 0) pct = 0; if (pct > 100) pct = 100; return pct;
}
bool Battery::low(int p) { return percent() <= p; }
}  // namespace cyclops
#else

#include <Arduino.h>

namespace cyclops {

Battery::Battery(int pin, int full, int empty, int n, int divider, int enable_pin)
    : pin_(pin), full_mv_(full), empty_mv_(empty), num_samples_(n),
      divider_(divider), enable_pin_(enable_pin) {}

void Battery::begin() {
    analogReadResolution(12);
    if (enable_pin_ >= 0) {
        // Some boards gate the VBAT divider behind a MOSFET (Feather ESP32-S3:
        // GPIO7 HIGH enables it) so the divider doesn't drain the pack.
        pinMode(enable_pin_, OUTPUT);
        digitalWrite(enable_pin_, HIGH);
        delay(10);  // let the divider settle before the first read
    }
    if (pin_ >= 0) {
        pinMode(pin_, INPUT);
#if defined(ESP32)
        analogSetPinAttenuation(pin_, ADC_11db);
#endif
    }
}

int Battery::read_mv() {
    if (pin_ < 0) return 0;
    long acc = 0;
    for (int i = 0; i < num_samples_; ++i) acc += analogRead(pin_);
    int raw = (int)(acc / num_samples_);          // 0..4095
    // 11dB ~ 0..3.3V at the pin; divider (default x2) -> pack voltage.
    int pin_mv = (raw * 3300) / 4095;
    last_mv_ = pin_mv * (divider_ > 0 ? divider_ : 1);
    return last_mv_;
}

int Battery::percent() {
    if (last_mv_ <= 0) read_mv();
    if (last_mv_ <= 0) return -1;
    int pct = (last_mv_ - empty_mv_) * 100 / (full_mv_ - empty_mv_);
    if (pct < 0) pct = 0; if (pct > 100) pct = 100; return pct;
}

bool Battery::low(int p) {
    int v = percent();
    return v >= 0 && v <= p;
}

}  // namespace cyclops
#endif  // ARDUINO