// Cyclops device firmware — XIAO ESP32-S3 Sense.
// Builds under PlatformIO (see platformio.ini) and compiles on host for tests
// with CYCLOps_HOST defined (no Arduino/ESP deps).
#include "protocol.h"
#include "ui.h"
#include <cstdio>

#ifdef CYCLOps_HOST
// Host test harness: no hardware. main() is the test driver in test/main_host.cpp.
namespace cyclops { void host_run(); }
#else
#include <Arduino.h>
#include <driver/i2s.h>
#include <Wire.h>

// --- Hardware pins (XIAO ESP32-S3 Sense) ---
static const int PIN_BTN_A = 1;     // boot/user button or ext
static const int PIN_BTN_B = 2;
static const int PIN_WHEEL_A = 3;   // rotary encoder A
static const int PIN_WHEEL_B = 4;   // rotary encoder B
static const int PIN_WHEEL_BTN = 5; // encoder press
static const int I2C_SDA = 6, I2C_SCL = 7;       // oled/tft
static const int PIN_LED = 21;
static const int PIN_VBAT = A0;

static cyclops::UiState ui;
static const char* CAPS[] = {"mic","screen","gyro","wheel","btn","ble","battery","vibration"};

void send_frame(uint8_t type, const uint8_t* p, size_t n) {
    uint8_t buf[1024]; size_t k = cyclops::encode_frame(type, p, n, buf, sizeof(buf));
    Serial.write(buf, k);
}

void on_frame(uint8_t type, const uint8_t* payload, size_t plen, void* ctx) {
    (void)ctx;
    switch (type) {
        case cyclops::MSG_DISPLAY_CMD: {
            char tmp[256]; memcpy(tmp, payload, plen); tmp[plen]='\0';
            ui.apply_display_cmd(tmp); break;
        }
        case cyclops::MSG_NOTE: {
            // NOTE is JSON {"text":"..."}; minimal parse
            char tmp[256]; memcpy(tmp, payload, plen); tmp[plen]='\0';
            const char* t = strstr(tmp, "\"text\"");
            if (t) { const char* s = strchr(t, ':'); if (s) { ++s; while(*s==' ')++s; if(*s=='"'){++s; char out[64]; int i=0; while(*s && *s!='"' && i<63) out[i++]=*s++; out[i]='\0'; ui.add_note(out);} } }
            break;
        }
        default: break;
    }
}

void setup() {
    Serial.begin(115200);
    ui.init();
    pinMode(PIN_BTN_A, INPUT_PULLUP);
    pinMode(PIN_BTN_B, INPUT_PULLUP);
    // I2S mic + I2C display init omitted for brevity (board-specific).
    cyclops::FrameDecoder dec(on_frame, nullptr);
    // send HELLO
    char hello[128];
    snprintf(hello, sizeof(hello), "{\"v\":1,\"hw\":\"xiao-s3-sense\"}");
    send_frame(cyclops::MSG_HELLO, (uint8_t*)hello, strlen(hello));
}
void loop() {
    // read serial -> decoder; poll buttons/wheel; sample battery; periodically heartbeat
}
#endif
