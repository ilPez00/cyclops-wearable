// Per-board hardware configuration — the ONE place board differences live.
//
// Cyclops targets two ESP32-S3 boards that share every byte of application
// logic (Hud, BLE link, I2C screen + HW-123, battery, 2 buttons, off-body
// gate). What differs is only which onboard peripherals exist and which pads
// they hang off:
//
//   CYCLOPS_BOARD_XIAO    Seeed XIAO ESP32-S3 *Sense* — the full sensor node:
//                         OV2640 camera + PDM mic + microSD slot, plus the
//                         4-pin I2C OLED and HW-123 on D6/D7. (docs/42 default)
//
//   CYCLOPS_BOARD_FEATHER Adafruit Feather ESP32-S3 (2 MB PSRAM) — the
//                         fallback board when no XIAO is on the bench. Same
//                         HUD/BLE/button/I2C/battery surface, but the Sense
//                         peripherals are absent: no camera, no PDM mic, no SD
//                         slot on the board (add a microSD breakout if wanted).
//                         Mic capture and photo capture compile OUT; everything
//                         else — including voice-note *commands* (fulfilled by
//                         the phone/brain) — still works.
//
// Adding a third board = one new #elif block here + one env in platformio.ini.
// selected by build_flags: -DCYCLOPS_BOARD_XIAO | -DCYCLOPS_BOARD_FEATHER
#ifndef CYCLOPS_BOARD_CONFIG_H
#define CYCLOPS_BOARD_CONFIG_H

#if !defined(CYCLOPS_BOARD_XIAO) && !defined(CYCLOPS_BOARD_FEATHER)
#error "Select a board: -DCYCLOPS_BOARD_XIAO or -DCYCLOPS_BOARD_FEATHER"
#endif

// ---------------------------------------------------------------- XIAO S3 Sense
#if defined(CYCLOPS_BOARD_XIAO)

#define BOARD_NAME "xiao-s3-sense"

// 2 buttons, both active-low with internal pull-ups.
// BTN_A on GPIO3 (strapping pin, but idle-HIGH is safe; A+B held at boot is the
// designed factory-reset combo). BTN_B on GPIO5 (was GPIO4 = the old wheel B).
#define PIN_BTN_A 3
#define PIN_BTN_B 5

// I2C: 4-pin SSD1306 128x32 OLED + HW-123 accel share this bus.
// (SPI would collide with the SD slot on 7/8/9, so I2C is required here.)
#define PIN_I2C_SDA 43
#define PIN_I2C_SCL 44
#define BOARD_I2C_ADDR_OLED 0x3C
#define BOARD_I2C_ADDR_IMU 0x68

// PDM mic (onboard MSM261D). Verified on metal 2026-07-12: standard I2S on
// 40/41/42 reads silence and GPIO40 is the camera's SCCB SDA — PDM is the only
// correct config. ws pin carries the PDM clock, data_in the bitstream.
#define BOARD_HAS_MIC 1
#define MIC_PDM_CLK 42
#define MIC_PDM_DATA 41

// OV2640 camera + WiFi JPEG server (onboard, on demand — see camera_capture.h).
#define BOARD_HAS_CAMERA 1

// microSD slot (CS=GPIO21, plus 7/8/9 which only the I2C build leaves free).
#define BOARD_HAS_SD 1
#define PIN_SD_CS 21

// Battery: BAT+ --100k--> D2(GPIO2) --100k--> GND. Divider x2.
#define BOARD_HAS_BATTERY 1
#define PIN_VBAT 2
#define BOARD_VBAT_DIVIDER 2

// ONE button on the MVP harness (docs/43): the "ear" button (GPIO5) is not
// populated, so only BTN_A exists. GPIO5 is therefore FREE on this board
// (candidates: IMU INT, a second sensor, nothing). Consequences in main.cpp:
// one GestureDetector, factory reset = hold BTN_A >= 2s at boot (was A+B),
// and Hud::use_one_button() rebinds the single button's grid to
// single=OK / double=BACK / long=AGENT so ACT_BACK stays one gesture away.
#define BOARD_HAS_BTN_B 0

// ------------------------------------------------------- Feather ESP32-S3
#elif defined(CYCLOPS_BOARD_FEATHER)

#define BOARD_NAME "feather-esp32s3"

// Feather pins are free-form on the header; these are the pads the V3-slim
// harness uses when a XIAO is swapped for a Feather. D5/D6 on a Feather are
// GPIO5/GPIO6 — both plain GPIOs on the S3, no strapping conflict, and unlike
// GPIO3 neither is a JTAG-select pin, so the boot combo is even safer.
#define PIN_BTN_A 5
#define PIN_BTN_B 6
// The Feather harness keeps both buttons (docs/43 §3): BOARD_HAS_BTN_B is what
// main.cpp and Hud::use_one_button() key off, so a board that populates two
// buttons declares 1 here and the old 2x3 grid stays valid.
#define BOARD_HAS_BTN_B 1

// Same I2C part on the Feather's SDA/SCL pads.
#define PIN_I2C_SDA 3   // Feather SDA
#define PIN_I2C_SCL 4   // Feather SCL
#define BOARD_I2C_ADDR_OLED 0x3C
#define BOARD_I2C_ADDR_IMU 0x68

// No onboard mic: capture compiles out. Voice notes still work — the gesture
// fires MSG_CMD and the phone/brain records or answers (thin-client model).
#define BOARD_HAS_MIC 0

#define BOARD_HAS_CAMERA 0

// No onboard SD slot.
#define BOARD_HAS_SD 0

// Feather ESP32-S3 has a built-in VBAT divider (100k/100k) on A13/GPIO35,
// gated by GPIO7 (HIGH = enabled). Same x2 ratio as the XIAO harness.
#define BOARD_HAS_BATTERY 1
#define PIN_VBAT 35
#define BOARD_VBAT_DIVIDER 2
#define BOARD_VBAT_ENABLE 7

#endif  // board select

// Shared audio constants (only meaningful when BOARD_HAS_MIC).
#define MIC_RATE 16000
#define MIC_BUF_SAMPLES 256

#endif  // CYCLOPS_BOARD_CONFIG_H
