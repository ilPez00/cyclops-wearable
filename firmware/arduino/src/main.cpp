// Cyclops Arduino HUD — desktop/dev unit. 3 screens via SCREEN_*.
// proximity, joystick, buttons, scrollwheel. USB-Serial to brain.
// Build: pio run -e arduino_st7735 | arduino_128x64 | arduino_128x32
#include "cyclops_shared.h"
#include "screen.h"
#include "screens.h"
#include "hud.h"
#include <Wire.h>

#if defined(SCREEN_ST7735)
static cyclops::St7735Screen screen(10, 9, 8, 13, 11, 12);
#elif defined(SCREEN_128x64)
static cyclops::Ssd1306_128x64_Screen screen(7, 6, 5, 13, 11, 12, 5);
#elif defined(SCREEN_128x32)
static cyclops::Ssd1306_128x32_Screen screen(4, 3, 2, 13, 11, 12, 2);
#endif

#define PIN_PROX   A0
#define PIN_JOY_X  A1
#define PIN_JOY_Y  A2
#define PIN_JOY_BTN 7
#define PIN_BTN_A  5
#define PIN_BTN_B  6
#define PIN_WHEEL_A 2
#define PIN_WHEEL_B 3
#define PIN_WHEEL_BTN 4
#define PIN_VBAT  A6

static cyclops::Hud hud;
static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx);
static void send_cmd(uint8_t act, const char* arg);
static void send_frame(uint8_t type, const uint8_t* p, size_t n);
static void ui_apply_display(const char* json);

static cyclops::FrameDecoder dec(on_frame, nullptr);

volatile int wheel_ticks = 0;
static void wheel_isr() {
    static uint8_t last = 0;
    uint8_t a = digitalRead(PIN_WHEEL_A);
    uint8_t b = digitalRead(PIN_WHEEL_B);
    if (a != last) { wheel_ticks += (a == b) ? 1 : -1; last = a; }
}

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx) {
    (void)ctx;
    char tmp[256]; if (n >= sizeof(tmp)) n = sizeof(tmp)-1;
    memcpy(tmp, p, n); tmp[n] = 0;
    switch (type) {
        case cyclops::MSG_DISPLAY_CMD: ui_apply_display(tmp); break;
        case cyclops::MSG_NOTE: ui_apply_display(tmp); break;
        default: break;
    }
}

static void ui_apply_display(const char* json) {
    // DISPLAY_CMD {"kind":..,"data":text} OR NOTE {"text":..}
    const char* key = strstr(json, "\"data\"") ? "\"data\"" : "\"text\"";
    const char* t = strstr(json, key);
    if (!t) return;
    const char* s = strchr(t, ':'); if (!s) return; ++s;
    while (*s==' ') ++s;
    if (*s=='"') { ++s; char out[64]; int i=0; while (*s && *s!='"' && i<63) out[i++]=*s++; out[i]=0; hud.add_note(out); }
}

static void send_cmd(uint8_t act, const char* arg) {
    uint8_t buf[300];
    char payload[200]; int pl = snprintf(payload, sizeof(payload), "{\"a\":%u,\"arg\":\"%s\"}", act, arg ? arg : "");
    size_t k = cyclops::encode_frame(cyclops::MSG_CMD, (uint8_t*)payload, pl, buf, sizeof(buf));
    Serial.write(buf, k);
}

static void send_frame(uint8_t type, const uint8_t* p, size_t n) {
    uint8_t buf[300]; size_t k = cyclops::encode_frame(type, p, n, buf, sizeof(buf));
    Serial.write(buf, k);
}

void setup() {
    Serial.begin(115200);
    screen.begin();
    pinMode(PIN_BTN_A, INPUT_PULLUP); pinMode(PIN_BTN_B, INPUT_PULLUP);
    pinMode(PIN_JOY_BTN, INPUT_PULLUP); pinMode(PIN_WHEEL_BTN, INPUT_PULLUP);
    pinMode(PIN_WHEEL_A, INPUT_PULLUP); pinMode(PIN_WHEEL_B, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_WHEEL_A), wheel_isr, CHANGE);
    hud.send_cmd = send_cmd;
    hud.init();
    char h[128]; snprintf(h, sizeof(h), "{\"v\":2,\"peer\":\"arduino_hud\",\"caps\":[\"screen\",\"wheel\",\"btn\",\"joy\",\"prox\",\"usb\"]}");
    send_frame(cyclops::MSG_PEER_HELLO, (uint8_t*)h, strlen(h));
}

static bool last_btn_a = true, last_btn_b = true, last_joy = true, last_wb = true;
static int prox_off_count = 0;
static uint32_t last_hb = 0;

void loop() {
    while (Serial.available()) dec.push((uint8_t)Serial.read());

    static int prev = 0;
    if (wheel_ticks != prev) { hud.on_wheel(wheel_ticks - prev > 0 ? 1 : -1); prev = wheel_ticks; }

    bool a = digitalRead(PIN_BTN_A), b = digitalRead(PIN_BTN_B), jb = digitalRead(PIN_JOY_BTN), wb = digitalRead(PIN_WHEEL_BTN);
    if (!a && last_btn_a) hud.on_select();
    if (!b && last_btn_b) hud.on_back_gesture(), hud.home();
    if (!jb && last_joy) hud.on_select();
    if (!wb && last_wb) hud.on_long_back();
    last_btn_a=a; last_btn_b=b; last_joy=jb; last_wb=wb;

    int jx = analogRead(PIN_JOY_X) - 512, jy = analogRead(PIN_JOY_Y) - 512;
    if (jy > 300) hud.on_wheel(1); else if (jy < -300) hud.on_wheel(-1);
    if (jx > 300) hud.on_wheel(1);

    int prox = analogRead(PIN_PROX);
    hud.screen_on = (prox > 200) ? true : hud.screen_on;
    if (prox <= 200 && ++prox_off_count > 600) { prox_off_count = 0; if (hud.screen_on) hud.screen_on=false; }

    if (millis() - last_hb > 5000) {
        last_hb = millis();
        char s[80]; int n = hud.status_json(s, sizeof(s)); send_frame(cyclops::MSG_STATUS, (uint8_t*)s, n);
    }

    hud.render(screen);
    delay(50);
}
