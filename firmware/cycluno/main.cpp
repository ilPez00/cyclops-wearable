// CyclUno — Cyclops dev unit on an Arduino Uno (controller half).
//
// Hardware (minimal build — 2 joysticks, 2 buttons, no encoder/LEDs):
//   OLED SSD1306 128x32, I2C (A4=SDA A5=SCL, addr 0x3C) — local glance HUD
//   2 joysticks (analog, active-low push — the pushes ARE the two buttons):
//       J1  VRx=A0  VRy=A1  SW=D2   A: select / REC toggle
//       J2  VRx=A2  VRy=A3  SW=D3   B: menu / back
//   No physical LEDs — REC / link state is shown on the OLED.
//
// Companion display board: the same 4 HUD rows are forwarded over
// SoftwareSerial (D4 TX @19200) to a second Arduino driving a big 128x128
// ST7735 (env:cyclobig, cyclobig/main.cpp). D4->that board's RX, GND<->GND.
// One-way link: the controller owns all state; the display just renders rows.
//
// Link to the brain: USB serial @115200 speaking the shared v2 framing — the
// same frames the XIAO speaks over BLE, so the whole brain pipeline is reused
// unchanged. The brain side is device/transport.py CableTransport (or
// demo_cycluno.py feeding prerecorded fixtures).
//
// RAM: UnoHud is ~160 B (host-gated < 400), FrameDecoder 262 B, SSD1306Ascii
// is text-mode (no framebuffer) — comfortably inside the ATmega328P's 2 KB.
#include <Arduino.h>
#include <Wire.h>
#include <SoftwareSerial.h>
#include "SSD1306Ascii.h"
#include "SSD1306AsciiWire.h"
#include "cyclops_shared.h"
#include "cycluno.h"

// ---- pin map (2 joysticks, 2 buttons = the joystick pushes) ----
#define PIN_J1_X  A0
#define PIN_J1_Y  A1
#define PIN_J1_SW 2     // button A: select / REC
#define PIN_J2_X  A2
#define PIN_J2_Y  A3
#define PIN_J2_SW 3     // button B: menu / back
#define PIN_DISP_TX 4   // -> big-display board RX (SoftwareSerial, one-way)
#define PIN_DISP_RX 5   // unused (SoftwareSerial needs a pin; nothing wired)
#define DISP_BAUD 19200
#define OLED_ADDR 0x3C

static SSD1306AsciiWire oled;
static SoftwareSerial disp(PIN_DISP_RX, PIN_DISP_TX);  // RX, TX
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
// Joystick axis -> single step with a center-lock (no auto-repeat while held).
static int8_t joy_step(uint8_t pin, int8_t& state, int lo = 324, int hi = 700) {
    int v = analogRead(pin);
    if (state == 0) {
        if (v > hi) { state = 1;  return 1; }
        if (v < lo) { state = -1; return -1; }
    } else if (v >= lo && v <= hi) {
        state = 0;  // returned to center -> unlock
    }
    return 0;
}

// debounced active-low buttons (edge = one press)
static bool pressed(uint8_t pin, uint8_t& state) {
    bool low = digitalRead(pin) == LOW;
    if (low && state == 0) { state = 1; return true; }
    if (!low) state = 0;
    return false;
}

// ---- render sink ------------------------------------------------------
// Draws locally on the 128x32 OLED and mirrors every row to the big-display
// board. Wire frame per row: [idx byte 0..3][text ASCII]['\n']. idx (<=3) and
// the REC bell (0x07) can never be '\n', so the newline is an unambiguous
// delimiter.
struct OledSink : cycluno::RowSink {
    void row(uint8_t idx, const char* text) override {
        oled.setCursor(0, idx);   // one text row per display row
        oled.print(text);
        oled.clearToEOL();
        disp.write(idx);
        disp.print(text);
        disp.write('\n');
    }
};
static OledSink sink;

void setup() {
    Serial.begin(115200);
    Wire.begin();
    Wire.setClock(400000L);
    oled.begin(&Adafruit128x32, OLED_ADDR);  // 128x64 works too: rows 0..3 used
    oled.setFont(System5x7);
    oled.clear();

    disp.begin(DISP_BAUD);   // one-way link to the big-display board

    // joystick pushes are the two buttons: active-low, internal pullup
    pinMode(PIN_J1_SW, INPUT_PULLUP);
    pinMode(PIN_J2_SW, INPUT_PULLUP);
    // analog joystick axes need no pinMode (ADC)

    hud.send_cmd = send_cmd;
    hud.on_rec_led = nullptr;   // no physical REC LED on this build
    hud.init();
    hud.render(sink);
}

void loop() {
    // serial in -> decoder -> hud
    while (Serial.available()) dec.push((uint8_t)Serial.read());

    // joystick Y axes -> scroll (center-locked single steps)
    static int8_t j1y = 0, j2y = 0;
    int8_t d = 0;
    d += joy_step(PIN_J1_Y, j1y);
    d += joy_step(PIN_J2_Y, j2y);
    if (d) hud.on_wheel(d > 0 ? 1 : -1);

    // joystick pushes = the two buttons (A = select/REC, B = menu/back).
    // Agent + Home moved into the MENU (reachable via B then A).
    static uint8_t sj1 = 0, sj2 = 0;
    if (pressed(PIN_J1_SW, sj1)) hud.on_btn_a();   // select / REC
    if (pressed(PIN_J2_SW, sj2)) hud.on_btn_b();   // menu / back

    // 1 Hz: toast decay + status frame out (link state implied by OLED updates)
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
    if ((dirty || d || millis() - last_draw > 250)) {
        hud.render(sink);
        last_draw = millis();
    }
    delay(10);
}
