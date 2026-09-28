// Li-Po battery sense via ADC divider (see docs/wiring.md V3):
//   BAT+ --100k--> D2(GPIO2) --100k--> GND  (divide by 2, 4.2V -> 2.1V ADC).
// ESP32-S3 ADC 12-bit, 11dB attenuation: ~0..3.3V. bead_batt slot in Hud
// is percent (0..100); hud.status_json() emits it as "batt". Charging pin
// optional (-1 = estimate only). Host build: stubs so g++ gate links.
#ifndef BATTERY_H
#define BATTERY_H
#include <cstdint>
namespace cyclops {

class Battery {
public:
    // batt_pin: ADC pin (default 2 = XIAO D2). full_mv/empty_mv: Li-Po curve.
    // num_samples: ADC averaging depth. divider: R ratio (2 = 100k/100k).
    // enable_pin: optional divider-enable GPIO pulled HIGH in begin()
    //             (Feather ESP32-S3 gates VBAT sense on GPIO7); -1 = none.
    Battery(int batt_pin = 2, int full_mv = 4200, int empty_mv = 3300,
            int num_samples = 16, int divider = 2, int enable_pin = -1);
    void begin();
    // Raw pack voltage in mV (divider compensated). 0 = unreadable.
    int read_mv();
    // 0..100 percent from the Li-Po curve. -1 = no reading yet.
    int percent();
    // True when pack is at/below low_pct (default 15%).
    bool low(int low_pct = 15);
private:
    int pin_, full_mv_, empty_mv_, num_samples_, divider_, enable_pin_;
    int last_mv_ = 0;
};

}  // namespace cyclops
#endif  // BATTERY_H