// Button gesture detector: single / double / long press. Pure logic, no HW,
// so the host gate (g++) exercises it. Feed raw pressed-state + millis each
// tick; poll() returns the gesture that just completed (NONE otherwise).
#ifndef GESTURES_H
#define GESTURES_H
#include <cstdint>
namespace cyclops {

enum Gesture : uint8_t { G_NONE=0, G_SINGLE=1, G_DOUBLE=2, G_LONG=3 };

class GestureDetector {
public:
    // long_ms: hold threshold; dbl_ms: max gap between taps for a double.
    GestureDetector(uint32_t long_ms = 600, uint32_t dbl_ms = 300)
        : long_ms_(long_ms), dbl_ms_(dbl_ms) {}

    // Call every tick with the debounced pressed state and current time.
    // Returns the completed gesture (once) or G_NONE.
    Gesture poll(bool pressed, uint32_t now) {
        Gesture out = G_NONE;
        if (pressed && !was_) {                 // edge down
            down_at_ = now; long_fired_ = false;
        }
        if (pressed && was_ && !long_fired_ && now - down_at_ >= long_ms_) {
            long_fired_ = true; pend_ = false;  // long cancels a pending single
            out = G_LONG;
        }
        if (!pressed && was_) {                 // edge up
            if (!long_fired_) {
                if (pend_ && now - last_tap_ <= dbl_ms_) { pend_ = false; out = G_DOUBLE; }
                else { pend_ = true; last_tap_ = now; }   // wait for a possible 2nd tap
            }
        }
        // pending single matures once the double window closes with no 2nd tap
        if (pend_ && !pressed && now - last_tap_ > dbl_ms_) { pend_ = false; out = G_SINGLE; }
        was_ = pressed;
        return out;
    }
private:
    uint32_t long_ms_, dbl_ms_;
    bool was_ = false, pend_ = false, long_fired_ = false;
    uint32_t down_at_ = 0, last_tap_ = 0;
};

}  // namespace cyclops
#endif  // GESTURES_H
