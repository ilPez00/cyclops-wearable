# Cyclops Zero — Implementation Plan

Screenless-gesture-aware pendant. XIAO S3 Sense + onboard IMU + I2C OLED + 1 button + Li-Po.
No wheel, no external IMU, no external mic. Phone is the full display; pendant HUD is glanceable.

## Wiring

| Part | Pin | XIAO | Notes |
|------|-----|------|-------|
| OLED I2C 128×32 | VCC | **3V3** | |
| | GND | **GND** | |
| | SDA | **D6** (GPIO43) | Wire1 bus |
| | SCL | **D7** (GPIO44) | Wire1 bus |
| Button (fallback) | SIG | **D3** (GPIO3) | INPUT_PULLUP, other leg → GND |
| | GND | **GND** | |
| Li-Po 302030 | + | **BAT** | through charge/protect |
| | - | **GND** | |
| Onboard LSM6DS3 | SDA | GPIO5 (internal) | Wire bus — no external wire |
| | SCL | GPIO6 (internal) | Wire bus — no external wire |

**Total external wires: 8** (OLED 4 + button 2 + battery 2).

### Pin allocation

| GPIO | Function | Bus |
|------|----------|-----|
| GPIO5 (SDA) | Onboard LSM6DS3 | Wire (I2C0) |
| GPIO6 (SCL) | Onboard LSM6DS3 | Wire (I2C0) |
| GPIO43 (D6) | OLED SDA | Wire1 (I2C1) |
| GPIO44 (D7) | OLED SCL | Wire1 (I2C1) |
| GPIO3 (D3) | BTN_A (fallback) | — |
| GPIO42 | PDM mic CLK | onboard |
| GPIO41 | PDM mic DATA | onboard |
| GPIO21/7/8/9 | microSD | onboard (optional) |
| BAT | Li-Po + | power |

**GPIO0,1,2,4,10–20,38,39,45–48 free** for expansion.

### Onboard IMU note
The LSM6DS3 sits on the **default** I2C bus (GPIO5/6 = `Wire`), address **0x6A**.
This is a **different bus** from the OLED (GPIO43/44 = `Wire1`). No conflict.
GPIO5 was BTN_B in the old firmware — Zero drops BTN_B, frees the pin.

## Build env: `xiao_zero`

New section in `firmware/platformio.ini`:

```ini
[env:xiao_zero]
platform = espressif32
board = seeed_xiao_esp32s3
framework = arduino
build_flags = -DCYCLOPS_XIAO -DSCREEN_128x32_I2C -DENABLE_ZERO=1 -DENABLE_IMU=1
  -Ilib/cyclops_shared/include
lib_deps = adafruit/Adafruit GFX Library@^1.11,
  adafruit/Adafruit SSD1306@^2.5,
  h2zero/NimBLE-Arduino@^1.4
build_src_filter = +<main.cpp> +<../xiao/src/zero_gestures.cpp>
  +<../xiao/src/sd_log.cpp> +<../xiao/src/ring_ble.cpp>
  +<../xiao/src/camera_capture.cpp>
```

Derived from `xiao_128x32_i2c` but:
- Replaces wheel/button input with gesture engine
- Uses onboard LSM6DS3 (Wire, addr 0x6A) instead of external MPU (Wire1, addr 0x68)
- No wheel, no BTN_B — single fallback button on D3

## Firmware changes

### 1. New file: `firmware/xiao/src/zero_gestures.h`

Gesture state machine that reads the onboard LSM6DS3 and emits gesture events:

```cpp
namespace cyclops {

enum ZeroGesture : uint8_t {
    ZG_NONE = 0,
    ZG_TILT_RIGHT,       // accel X > +thresh sustained
    ZG_TILT_LEFT,        // accel X < -thresh sustained
    ZG_FLIP,             // accel Z sign flips (face-up ↔ face-down)
    ZG_NOD,              // accel Y spike up then return
    ZG_SHAKE,            // accel X oscillation
    ZG_DOUBLE_TAP,       // accel Z double impulse
    ZG_FACE_DOWN,        // accel Z ≈ -1g sustained >4s
    ZG_FLICK_UP,         // accel Y sharp positive
    ZG_TWIST,            // gyro Z rotation
};

class ZeroGestureDetector {
public:
    ZeroGestureDetector();

    // Feed raw IMU sample + timestamp. Returns completed gesture (once).
    ZeroGesture poll(int ax, int ay, int az, int gz, uint32_t now);

    bool off_body() const;     // from presence detector
    bool changed() const;      // presence edge

private:
    // Thresholds, timers, state machine
    PresenceDetector presence_;
    // ... tilt accumulators, debounce timers, etc
};

}
```

Detection logic:
- **Tilt right**: `ax > TILT_THRESH` for `TILT_HOLD_MS` consecutive samples
- **Tilt left**: `ax < -TILT_THRESH` for `TILT_HOLD_MS` consecutive samples
- **Flip**: `az` changes sign from positive to negative (or vice versa) in one sample window
- **Nod**: `ay` crosses `NOD_PEAK` then returns below `NOD_RETURN` within `NOD_WINDOW_MS`
- **Shake**: `ax` oscillates across zero >= `SHAKE_CYCLES` in `SHAKE_WINDOW_MS`
- **Double-tap**: two `az` impulses of `TAP_PEAK` within `TAP_WINDOW_MS`
- **Face down**: `az < -0.8g` for `FACE_DOWN_MS` (reuse `PresenceDetector` or separate timer)
- **Flick up**: `ay` crosses `FLICK_PEAK` in positive direction, single impulse
- **Twist**: `gz` (gyro Z) exceeds `TWIST_THRESH` for `TWIST_HOLD_MS`

### 2. Modify `firmware/xiao/src/main.cpp`

Under `#ifdef ENABLE_ZERO`:

```cpp
// --- Cyclops Zero gesture input ---
#ifdef ENABLE_ZERO
#include "zero_gestures.h"
static cyclops::ZeroGestureDetector zero_g;
static cyclops::Imu onboard_imu(0x6A, -1);  // LSM6DS3 on Wire, addr 0x6A, no INT pin
// Onboard IMU init uses Wire (GPIO5/6), not Wire1 (D6/D7).
// The OLED stays on Wire1 — both buses coexist.
#endif
```

In `setup()`:
```cpp
#ifdef ENABLE_ZERO
    Wire.begin(5, 6);    // onboard LSM6DS3
    onboard_imu.begin();
    // Override the external IMU — use onboard only
#endif
```

In `loop()`:
```cpp
#ifdef ENABLE_ZERO
    onboard_imu.update();
    const auto& s = onboard_imu.sample();
    ZeroGesture g = zero_g.poll(s.ax, s.ay, s.az, s.gz, millis());
    if (g != ZG_NONE) {
        handle_zero_gesture(g);
    }
    // Presence detection for privacy lock
    if (zero_g.changed() && zero_g.off_body()) {
        hud.set_consent(false);
        hud.notify("off body", Hud::NOTE_WARN, 3);
    } else if (zero_g.changed() && !zero_g.off_body()) {
        hud.set_consent(true);
        hud.notify("re-worn", Hud::NOTE_OK, 2);
    }
#endif
```

Gesture dispatch:
```cpp
static void handle_zero_gesture(ZeroGesture g) {
    switch (g) {
        case ZG_TILT_RIGHT:
            hud.toast("photo", 1);
            if (hud.consent) {
                send_cmd(ACT_PHOTO, camera_capture.capture());
            }
            break;
        case ZG_TILT_LEFT:
            // toggle recording
            if (!hud.consent) { hud.toast("consent off", 2); return; }
            if (capturing) { stop_capture(); hud.toast("recording saved", 2); }
            else { start_capture(); hud.toast("recording", 2); }
            break;
        case ZG_FLIP:
            // voice command mode
            hud.toast("listening", 2);
            hud.set_detail(""); hud.push(Hud::AGENT);
            send_cmd(ACT_VOICE_CMD);
            if (on_transcribe_toggle) on_transcribe_toggle();
            break;
        case ZG_NOD:
            hud.on_select();
            break;
        case ZG_SHAKE:
            hud.on_cancel();
            break;
        case ZG_DOUBLE_TAP:
            hud.on_select();  // quick confirm / wake
            break;
        case ZG_FACE_DOWN:
            hud.set_consent(false);
            hud.toast("privacy lock", 2);
            break;
        case ZG_FLICK_UP:
            hud.home();
            break;
        case ZG_TWIST:
            hud.on_wheel(1);  // next
            break;
        default:
            break;
    }
}
```

### 3. Modify `firmware/xiao/src/imu.h`

Add a constructor that takes a `TwoWire*` reference to support both the external IMU (Wire1/D6D7) and the onboard IMU (Wire/GPIO56):

```cpp
class Imu {
public:
    Imu(uint8_t addr = 0x68, int int_pin = 1, TwoWire* bus = &Wire1);
    // ...
};
```

The LSM6DS3 registers differ slightly from MPU-6050, so add a probe path:
- Try MPU-6050 WHO_AM_I (0x68 → 0x71) first
- Fall back to LSM6DS3 WHO_AM_I (0x6A → 0x6C) if no match
- Set the correct register map based on which chip answers

### 4. Wire coexistence: Wire (GPIO5/6) + Wire1 (GPIO43/44)

In `main.cpp`, both buses must be initialized:

```cpp
Wire.begin(5, 6);       // GPIO5=SDA, GPIO6=SCL — onboard LSM6DS3
Wire1.begin(43, 44);    // GPIO43=SDA, GPIO44=SCL — I2C OLED
```

The `Ssd1306_128x32_I2C_Screen` already uses `Wire1` (default in its `begin()` calls `Wire.begin(sda_, scl_)` which maps to the constructor params sda=43, scl=44 → but the `Adafruit_SSD1306` constructor takes a `TwoWire*` parameter. Looking at the current code:

In `screens.h` line 86-88:
```cpp
Ssd1306_128x32_I2C_Screen(int cs, int dc, int rst, int sck, int mosi, int miso, int rst_pin=-1,
                          uint8_t addr=0x3C, int sda=43, int scl=44)
    : disp_(128,32,&Wire,rst_pin), addr_(addr), sda_(sda), scl_(scl) { ... }
```

Wait — it passes `&Wire` not `&Wire1`. That's a **bug** if using D6/D7 with Wire. Let me check:

On ESP32, `Wire` usually defaults to GPIO21/22, but `Wire1` defaults to... actually on ESP32-S3, `Wire` uses the default pins from the variant. For the XIAO S3 Sense variant, `Wire` might be configured differently.

Looking more carefully at the screen's `begin()`:
```cpp
void begin() override { Wire.begin(sda_, scl_); disp_.begin(SSD1306_SWITCHCAPVCC, addr_); ... }
```

It calls `Wire.begin(sda_, scl_)` which overrides Wire's pins to 43/44. So it's using the `Wire` instance but with custom pins. That means the OLED and the onboard IMU would **both** be on the same Wire instance with different pins.

Actually on ESP32, you can't have two I2C buses on the same Wire instance with different pins — each instance has one set of pins. So we need to use separate instances.

For Zero:
- `Wire` (default) with pins 5/6 → onboard LSM6DS3
- Need a different Wire instance for the OLED on D6/D7 (GPIO43/44) → either `Wire1` or keep using `Wire` with a `setPins()` call before each transaction (bad idea)

Best approach: Use `Wire1` for the OLED. Modify the screen class to accept a `TwoWire*` parameter.

In `screens.h`, the `Ssd1306_128x32_I2C_Screen` already takes a `TwoWire*` in the Adafruit constructor (`&Wire`), but then calls `Wire.begin(sda_, scl_)` in `begin()`. Need to pass `&Wire1` instead.

So the fix:
1. Pass `&Wire1` in the constructor: `disp_(128,32,&Wire1,rst_pin)`
2. In `begin()`: `Wire1.begin(sda_, scl_)` instead of `Wire.begin(sda_, scl_)`

### 5. Wakeword support (phase 2)

The `audio_trigger.h` already has `AudioTrigger` for loud-sound detection. Wakeword needs a bigger lift:

**Short-term**: BLE-based. Stream audio to phone, phone detects wakeword, sends parsed command back as `MSG_CMD` frame (already supported).

**Long-term**: ESP-SR / WakeNet on-device. ESP32-S3 has the matrix multiply hardware for it. Add as a build flag `-DENABLE_WAKEWORD` when the model is ready.

### 6. Existing features that carry over

| Feature | Status | Notes |
|---------|--------|-------|
| PDM mic capture | onboard, no change | GPIO42/41 |
| BLE (NimBLE) | unchanged | `CyclopsXIAO` server |
| SD logging | optional | onboard slot, no wires |
| OTA | unchanged | BLE reflash |
| Camera capture | unchanged | OV2640, `ACT_PHOTO` |
| HUD state machine | unchanged | gesture replaces wheel/btn input |
| I2C OLED | D6/D7 → Wire1 | needs Wire1 fix |

## BOM

| Qty | Part | Cost |
|-----|------|------|
| 1 | XIAO ESP32-S3 Sense | ~$15 |
| 1 | SSD1306 128×32 I2C OLED | ~$3 |
| 1 | Li-Po 302030 3.7V | ~$4 |
| 1 | Tactile button | ~$0.10 |
| 1 | Pendant case (3D print) | ~$1 |
| — | **Total** | **~$23** |

Wires needed: 8 (OLED 4 + button 2 + battery 2). Everything else is onboard.

## Build & flash

```bash
cd firmware
pio run -e xiao_zero -t upload
```

## Schematic (text)

```
                    XIAO ESP32-S3 SENSE
   ┌──────────────────────────────────────────────┐
   │                                               │
   │  OLED 128×32 (I2C, Wire1)  SDA→D6  SCL→D7    │
   │  BTN (fallback)            SIG→D3  GND→GND   │
   │  Li-Po 302030              +→BAT   -→GND    │
   │                                               │
   │  Onboard: LSM6DS3 (Wire, GPIO5/6, addr 0x6A) │
   │           PDM mic (GPIO42/41)                 │
   │           OV2640 camera (SCCB + DVP)          │
   │           microSD (GPIO21/7/8/9, optional)    │
   │           BLE antenna (onboard)               │
   └──────────────────────────────────────────────┘
```