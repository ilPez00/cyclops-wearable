// Cyclops mini4 — the 4-part minimal wearable (docs/15-mini4.md).
//
//   screen (SSD1306 128x32 I2C) + battery (divider) + gyroscope (HW-123/MPU) + 1 button
//
// RECONSTRUCTED 2026-09-19: the original firmware/mini4/main.cpp lived on the
// /home/gio/dev/cyclops clone as an untracked file and was lost, together with
// its (never-created) platformio env, before it was ever committed. Rebuilt from
// docs/15-mini4.md's spec table against the current shared lib (Hud + Screen +
// Battery + Imu + PresenceDetector), which the full V3-slim build also uses — so
// this file inherits the shipped state machine instead of the July one.
//
// Wiring (docs/15-mini4.md):
//   OLED  SDA=D6/GPIO43  SCL=D7/GPIO44  (3V3/GND)
//   MPU   SDA=D6/GPIO43  SCL=D7/GPIO44  (0x68 with AD0->GND; shared bus)
//   BTN1  D2/GPIO3  SIG->GND, INPUT_PULLUP
//   BAT   D1/GPIO2  divider tap (BAT+ --100k--> D1 --100k--> GND)
//
// What it does NOT do: no mic, camera, SD, ring, wheel or second button.
// Audio/photo capture and agent calls are PHONE-DRIVEN — the single button
// forwards MSG_CMD and the app/brain fulfils (identical to the BOARD_HAS_MIC=0
// / BOARD_HAS_CAMERA=0 path of the V3-slim firmware).
//
// Build: pio run -e xiao_mini4 -t upload
#include "cyclops_shared.h"
#include "screen.h"
#include "screens.h"
#include "hud.h"
#include "gestures.h"
#include "battery.h"
#include "imu.h"
#include "presence.h"
#include "posture.h"
#include "soc/rtc_cntl_reg.h"
#include <Wire.h>
#include <NimBLEDevice.h>

// --- pins (docs/15-mini4.md) ---
#define PIN_I2C_SDA 43   // D6
#define PIN_I2C_SCL 44   // D7
#define PIN_IMU_ADDR 0x68
#define PIN_BTN 3        // D2
#define PIN_VBAT 2       // D1

// 4-pin I2C OLED only, addr 0x3C, no reset pin.
static cyclops::Ssd1306_128x32_I2C_Screen screen(0, 0, 0, 0, 0, 0, -1);
static cyclops::Hud hud;
static cyclops::Imu imu(PIN_IMU_ADDR, -1);
static cyclops::Battery batt(PIN_VBAT, 4200, 3300, 16, 2, -1);
static cyclops::PresenceDetector presence;
static cyclops::PostureDetector posture(30, 600000);

// BLE link (same NUS-style characteristic as the full build, so the app treats
// mini4 exactly like a V3-slim unit minus the sensors).
static NimBLEServer* srv = nullptr;
static NimBLECharacteristic* note_ch = nullptr;
static const char* SRVC = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
static const char* NOTE_CH = "beb5483e-36e1-4688-b7f5-ea07361b26a8";

static void send_frame(uint8_t type, const uint8_t* p, size_t n);
static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx);
static cyclops::FrameDecoder dec(on_frame, nullptr);

class SrvCb : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer*) override { hud.bt = true; }
    void onDisconnect(NimBLEServer*) override { hud.bt = false; }
};
class NoteCb : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* c) override {
        std::string v = c->getValue();
        for (size_t i = 0; i < v.size(); ++i) dec.push((uint8_t)v[i]);
    }
};

static void send_frame(uint8_t type, const uint8_t* p, size_t n) {
    if (!hud.bt || !note_ch) return;
    uint8_t buf[300];
    size_t k = cyclops::encode_frame(type, p, n, buf, sizeof(buf));
    if (k) { note_ch->setValue(buf, k); note_ch->notify(); }
}

static void send_cmd(uint8_t act, const char* arg) {
    // Same shape the full build sends: action id byte + optional arg text.
    uint8_t payload[96];
    payload[0] = act;
    size_t alen = arg ? strlen(arg) : 0;
    if (alen > sizeof(payload) - 1) alen = sizeof(payload) - 1;
    if (alen) memcpy(payload + 1, arg, alen);
    send_frame(cyclops::MSG_CMD, payload, 1 + alen);
}

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void*) {
    if (type == cyclops::MSG_CMD && n) hud.do_action(p[0]);
    else if (type == cyclops::MSG_DISPLAY_CMD) hud.apply_display_cmd((const char*)p);
    else if (type == cyclops::MSG_NOTE) {
        char t[96]; size_t k = n < sizeof(t) - 1 ? n : sizeof(t) - 1;
        memcpy(t, p, k); t[k] = 0;
        hud.add_note(t);
    }
}

void setup() {
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);   // high-load brownout guard
    Serial.begin(115200);
    Serial.println("[boot] Cyclops mini4 (screen+batt+gyro+1btn)");
    pinMode(PIN_BTN, INPUT_PULLUP);
    screen.begin();
    Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
    batt.begin();
    hud.send_cmd = send_cmd;
    // docs/43: one-button harness -> tap=OK, double-tap=BACK, long=AGENT, and
    // the HINT row teaches that grammar (the old default grid gave double=PHOTO
    // / long=VIDEO, which docs/15-mini4.md never claimed).
    hud.use_one_button();
    hud.init();
    // docs/43 C4: begin() refuses a part whose register map this driver cannot
    // speak (an LSM6DS3 ACKs, then reads garbage), so log what answered.
    if (imu.begin()) {
        Serial.printf("[boot] %s\n", imu.reason());
    } else {
        Serial.printf("[boot] %s\n", imu.reason());
        hud.notify(cyclops::imu_refusal_short(imu.chip()), cyclops::Hud::NOTE_WARN, 3);
    }
    NimBLEDevice::init("CyclopsMini4");
    srv = NimBLEDevice::createServer();
    srv->setCallbacks(new SrvCb());
    NimBLEService* s = srv->createService(SRVC);
    note_ch = s->createCharacteristic(NOTE_CH, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::WRITE);
    note_ch->setCallbacks(new NoteCb());
    s->start();
    NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
    adv->addServiceUUID(SRVC);
    adv->start();
    Serial.printf("[boot] batt %dmV %d%%\n", batt.read_mv(), batt.percent());
}

// One button, three chords (docs/15-mini4.md): single = select, double =
// cancel, long = ask the agent / toggle capture. Same GestureDetector the
// two-button board uses, bound through the shared remappable grid.
static cyclops::GestureDetector btn(600, 300);

void loop() {
    uint32_t now = millis();
    hud.fire_gesture(0, btn.poll(!digitalRead(PIN_BTN), now));

    if (imu.update()) {
        const auto& s = imu.sample();
        int tilt = imu.scroll_tilt();
        if (tilt != 0) hud.on_wheel(tilt);          // tilt = scroll
        hud.nav_head = s.heading;
        bool off = presence.poll(s.ax, s.ay, s.az, now);
        if (presence.changed()) {
            hud.set_consent(!off);
            hud.set_presence(!off);   // C5: "wearer present" claim boundary
            hud.notify(off ? "off-body: sensors off" : "on-body: sensors on",
                       cyclops::Hud::NOTE_WARN, 2);
            if (!off) posture.calibrate(s.pitch);
        }
        if (!posture.calibrated() && !off) posture.calibrate(s.pitch);
        if (!off) hud.set_posture(posture.poll(s.pitch, now));  // C5: posture cue
    }

    static uint32_t last_hb = 0;
    if (now - last_hb > 5000) {
        last_hb = now;
        int pct = batt.percent();
        if (pct >= 0) hud.set_health(0, 0, 0, pct);
        int mv = batt.read_mv();
        if (mv > 0) hud.bead_batt_mv = (uint16_t)mv;
        if (batt.low()) hud.notify("battery low", cyclops::Hud::NOTE_WARN, 3);
        char st[200];
        int n = hud.status_json(st, sizeof(st));
        send_frame(cyclops::MSG_STATUS, (const uint8_t*)st, n);
    }

    hud.render(screen);
    // Low-power idle: <20% battery or screen off -> long sleep (spec table).
    bool low = batt.low(20);
    delay((hud.screen_on && !low) ? 50 : 250);
}
