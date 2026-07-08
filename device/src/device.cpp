// Cyclops device firmware — XIAO ESP32-S3 Sense.
// Builds under PlatformIO (see platformio.ini). Hardware-specific code is
// guarded by #ifndef CYCLOps_HOST so the same protocol/ui can be unit-tested
// on a host machine (test/main_host.cpp provides main()).
#include "protocol.h"
#include "ui.h"
#include <cstring>

#ifndef CYCLOps_HOST
#include <Arduino.h>
#include <Wire.h>

static const int PIN_BTN_A = 1;
static const int PIN_BTN_B = 2;
static const int PIN_WHEEL_A = 3;
static const int PIN_WHEEL_B = 4;
static const int PIN_WHEEL_BTN = 5;
static const int I2C_SDA = 6, I2C_SCL = 7;
static const int PIN_LED = 21;
static const int PIN_VBAT = A0;

static cyclops::UiState ui;

void send_frame(uint8_t type, const uint8_t* p, size_t n) {
    uint8_t buf[1024]; size_t k = cyclops::encode_frame(type, p, n, buf, sizeof(buf));
    Serial.write(buf, k);
}

void on_frame(uint8_t type, const uint8_t* payload, size_t plen, void* ctx) {
    (void)ctx;
    char tmp[256]; if (plen >= sizeof(tmp)) plen = sizeof(tmp) - 1;
    memcpy(tmp, payload, plen); tmp[plen] = '\0';
    switch (type) {
        case cyclops::MSG_DISPLAY_CMD: ui.apply_display_cmd(tmp); break;
        case cyclops::MSG_NOTE: {
            const char* t = strstr(tmp, "\"text\"");
            if (t) { const char* s = strchr(t, ':'); if (s) { ++s; while (*s==' ') ++s;
                if (*s=='"') { ++s; char out[64]; int i=0; while (*s && *s!='"' && i<63) out[i++]=*s++; out[i]='\0'; ui.add_note(out); } } }
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
    cyclops::FrameDecoder dec(on_frame, nullptr);
    char hello[128]; snprintf(hello, sizeof(hello), "{\"v\":1,\"hw\":\"xiao-s3-sense\"}");
    send_frame(cyclops::MSG_HELLO, (uint8_t*)hello, strlen(hello));
}
void loop() {}
#endif
