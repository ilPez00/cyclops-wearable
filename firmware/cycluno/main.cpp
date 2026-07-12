// CyclUno — Cyclops dev unit on an Arduino Uno.
//
// Hardware:
//   OLED SSD1306 128x32 or 128x64, I2C (A4=SDA A5=SCL, addr 0x3C)
//   rotary encoder A=D2 B=D3 (both interrupt pins), push button on D4
//   button B on D5 (menu/back)
//   REC LED on D6, link LED on D7 (lit while frames arrive)
//
// Link: USB serial @115200 speaking the shared v2 framing — the same frames
// the XIAO speaks over BLE, so the whole brain pipeline is reused unchanged.
// The brain side is device/transport.py CableTransport (or demo_cycluno.py
// feeding prerecorded fixtures).
//
// RAM: UnoHud is 160 B (host-gated < 400), FrameDecoder 262 B, SSD1306Ascii
// is text-mode (no framebuffer) — comfortably inside the ATmega328P's 2 KB.
#include <Arduino.h>
#include <Wire.h>
#include "SSD1306Ascii.h"
#include "SSD1306AsciiWire.h"
#include "cyclops_shared.h"
#include "cycluno.h"

#define PIN_WHEEL_A 2
#define PIN_WHEEL_B 3
#define PIN_BTN_A 4
#define PIN_BTN_B 5
#define PIN_LED_REC 6
#define PIN_LED_LINK 7
#define OLED_ADDR 0x3C

static SSD1306AsciiWire oled;
static cycluno::UnoHud hud;

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx);
static cyclops::FrameDecoder dec(on_frame, nullptr);

// ---- outgoing ---------------------------------------------------------
static void send_frame(uint8_t type, const uint8_t* payload, size_t n) {
    uint8_t buf[96];  // status/cmd frames only — audio never originates here
    size_t k = cyclops::encode_frame(type, payload, n, buf, sizeof(buf));
    if (k) Serial.write(buf, k);
}

static void send_cmd(uint8_t act) {
    char payload[32];
    int n = snprintf(payload, sizeof(payload), "{\"a\":%u,\"arg\":\"\"}", act);
    send_frame(cyclops::MSG_CMD, (const uint8_t*)payload, (size_t)n);
}

// ---- incoming ---------------------------------------------------------
static unsigned long last_rx_ms = 0;

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void*) {
    last_rx_ms = millis();
    char tmp[64];  // notes are <= 21 chars on this display; clamp hard
    if (n >= sizeof(tmp)) n = sizeof(tmp) - 1;
    memcpy(tmp, p, n); tmp[n] = 0;
    if (type == cyclops::MSG_DISPLAY_CMD || type == cyclops::MSG_NOTE) {
        hud.apply_display_cmd(tmp);
    }
}

// ---- input ------------------------------------------------------------
volatile int8_t wheel_delta = 0;
static void wheel_isr() {
    static uint8_t last = 0;
    uint8_t a = digitalRead(PIN_WHEEL_A);
    uint8_t b = digitalRead(PIN_WHEEL_B);
    if (a != last) { wheel_delta += (a == b) ? 1 : -1; last = a; }
}

// debounced active-low buttons
static bool pressed(uint8_t pin, uint8_t& state) {
    bool low = digitalRead(pin) == LOW;
    if (low && state == 0) { state = 1; return true; }
    if (!low) state = 0;
    return false;
}

// ---- render sink -------------------------------------------------------
struct OledSink : cycluno::RowSink {
    void row(uint8_t idx, const char* text) override {
        oled.setCursor(0, idx);   // one text row per display row
        oled.print(text);
        oled.clearToEOL();
    }
};
static OledSink sink;

static void rec_led(bool on) { digitalWrite(PIN_LED_REC, on ? HIGH : LOW); }

void setup() {
    Serial.begin(115200);
    Wire.begin();
    Wire.setClock(400000L);
    oled.begin(&Adafruit128x32, OLED_ADDR);  // 128x64 works too: rows 0..3 used
    oled.setFont(System5x7);
    oled.clear();

    pinMode(PIN_WHEEL_A, INPUT_PULLUP);
    pinMode(PIN_WHEEL_B, INPUT_PULLUP);
    pinMode(PIN_BTN_A, INPUT_PULLUP);
    pinMode(PIN_BTN_B, INPUT_PULLUP);
    pinMode(PIN_LED_REC, OUTPUT);
    pinMode(PIN_LED_LINK, OUTPUT);
    attachInterrupt(digitalPinToInterrupt(PIN_WHEEL_A), wheel_isr, CHANGE);

    hud.send_cmd = send_cmd;
    hud.on_rec_led = rec_led;
    hud.init();
    hud.render(sink);
}

void loop() {
    // serial in -> decoder -> hud
    while (Serial.available()) dec.push((uint8_t)Serial.read());

    // inputs
    if (wheel_delta != 0) {
        int8_t d; noInterrupts(); d = wheel_delta; wheel_delta = 0; interrupts();
        hud.on_wheel(d > 0 ? 1 : -1);
    }
    static uint8_t stA = 0, stB = 0;
    if (pressed(PIN_BTN_A, stA)) hud.on_btn_a();
    if (pressed(PIN_BTN_B, stB)) hud.on_btn_b();

    // link LED: lit while frames arrived within the last 2 s
    digitalWrite(PIN_LED_LINK, (millis() - last_rx_ms < 2000) ? HIGH : LOW);

    // 1 Hz: toast decay + status frame out
    static unsigned long last_tick = 0;
    bool dirty = false;
    if (millis() - last_tick >= 1000) {
        last_tick = millis();
        dirty = hud.tick();
        char st[48];
        int n = hud.status_json(st, sizeof(st));
        send_frame(cyclops::MSG_STATUS, (const uint8_t*)st, (size_t)n);
    }

    // redraw on any input or decayed toast
    static unsigned long last_draw = 0;
    if ((dirty || wheel_delta || millis() - last_draw > 250)) {
        hud.render(sink);
        last_draw = millis();
    }
    delay(10);
}
