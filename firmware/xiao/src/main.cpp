// Cyclops XIAO ESP32-S3 Sense — wearable HUD + audio capture.
// scrollwheel + 2 buttons + screen (ST7735 / 128x64 / 128x32 via SCREEN_*).
// I2S mic (onboard pads 40/41/42) -> BLE audio chunks -> phone transcribes.
// BLE (NimBLE) to phone. Shares Hud + Screen.
// Build: pio run -e xiao_st7735 | xiao_128x64 | xiao_128x32
#include "cyclops_shared.h"
#include "screen.h"
#include "screens.h"
#include "hud.h"
#include <Wire.h>
#include <NimBLEDevice.h>
#include <driver/i2s.h>

#if defined(SCREEN_ST7735)
static cyclops::St7735Screen screen(7, 2, 1, 8, 10, 9);
#elif defined(SCREEN_128x64)
static cyclops::Ssd1306_128x64_Screen screen(6, 2, 1, 8, 10, 9, 1);
#elif defined(SCREEN_128x32)
static cyclops::Ssd1306_128x32_Screen screen(5, 2, 1, 8, 10, 9, 1);
#endif

#define PIN_WHEEL_A 0
#define PIN_WHEEL_B 4
#define PIN_BTN_A  3
#define PIN_BTN_B  4

// I2S mic pins (XIAO S3 onboard mic pads; free, no screen conflict)
#ifndef MIC_BCLK
#define MIC_BCLK 40
#endif
#ifndef MIC_WS
#define MIC_WS 41
#endif
#ifndef MIC_DIN
#define MIC_DIN 42
#endif
#define MIC_RATE 16000
#define MIC_BUF_SAMPLES 256

static cyclops::Hud hud;
static NimBLEServer* srv;
static NimBLECharacteristic* note_ch;
static NimBLECharacteristicCallbacks* note_cb = nullptr;
static const char* SRVC = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
static const char* NOTE_CH = "beb5483e-36e1-4688-b7f5-ea07361b26a8";

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx);
static void send_cmd(uint8_t act, const char* arg);
static void send_frame(uint8_t type, const uint8_t* p, size_t n);
static void ui_apply_display(const char* json);
static void start_capture();
static void stop_capture();
static void audio_task(void*);

static cyclops::FrameDecoder dec(on_frame, nullptr);
static bool capturing = false;
static TaskHandle_t cap_task = nullptr;

class NoteCb : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* c) override {
        std::string v = c->getValue();
        for (size_t i = 0; i < v.size(); ++i) dec.push((uint8_t)v[i]);
    }
};

volatile int wheel_ticks = 0;
static void IRAM_ATTR wheel_isr() {
    static uint8_t last = 0;
    uint8_t a = digitalRead(PIN_WHEEL_A);
    uint8_t b = digitalRead(PIN_WHEEL_B);
    if (a != last) { wheel_ticks += (a == b) ? 1 : -1; last = a; }
}

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx) {
    (void)ctx;
    char tmp[256]; if (n >= sizeof(tmp)) n = sizeof(tmp)-1;
    memcpy(tmp, p, n); tmp[n] = 0;
    if (type == cyclops::MSG_DISPLAY_CMD || type == cyclops::MSG_NOTE) ui_apply_display(tmp);
}

static void ui_apply_display(const char* json) {
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
    if (note_ch) { note_ch->setValue(buf, k); note_ch->notify(); }
}

static void send_frame(uint8_t type, const uint8_t* p, size_t n) {
    uint8_t buf[400]; size_t k = cyclops::encode_frame(type, p, n, buf, sizeof(buf));
    if (note_ch) { note_ch->setValue(buf, k); note_ch->notify(); }
}

class SrvCb : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer*) override { hud.bt = true; }
    void onDisconnect(NimBLEServer*) override { hud.bt = false; }
};

static void audio_task(void*) {
    int16_t samples[MIC_BUF_SAMPLES];
    size_t rd;
    while (capturing) {
        i2s_read((i2s_port_t)0, samples, sizeof(samples), &rd, pdMS_TO_TICKS(100));
        if (rd > 0) send_frame(cyclops::MSG_AUDIO_CHUNK, (uint8_t*)samples, rd);
    }
    vTaskDelete(NULL);
}

static void start_capture() {
    if (capturing) return;
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX);
    cfg.sample_rate = MIC_RATE;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.intr_alloc_flags = 0;
    cfg.dma_buf_count = 4; cfg.dma_buf_len = MIC_BUF_SAMPLES;
    i2s_pin_config_t pins = {};
    pins.bck_io_num = MIC_BCLK; pins.ws_io_num = MIC_WS;
    pins.data_in_num = MIC_DIN; pins.data_out_num = I2S_PIN_NO_CHANGE;
    i2s_driver_install((i2s_port_t)0, &cfg, 0, NULL);
    i2s_set_pin((i2s_port_t)0, &pins);
    capturing = true;
    // announce format once
    uint8_t meta[8]; meta[0]=16; meta[1]=0; meta[2]=MIC_RATE&0xFF; meta[3]=(MIC_RATE>>8)&0xFF;
    meta[4]=1; meta[5]=0; meta[6]=0; meta[7]=0;
    send_frame(cyclops::MSG_AUDIO_META, meta, 8);
    xTaskCreatePinnedToCore(audio_task, "cap", 4096, NULL, 5, &cap_task, 0);
    hud.recording = true;
}

static void stop_capture() {
    if (!capturing) return;
    capturing = false;
    delay(120);
    i2s_driver_uninstall((i2s_port_t)0);
    send_frame(cyclops::MSG_AUDIO_STOP, NULL, 0);
    hud.recording = false;
}

void setup() {
    Serial.begin(115200);
    screen.begin();
    pinMode(PIN_BTN_A, INPUT_PULLUP); pinMode(PIN_BTN_B, INPUT_PULLUP);
    pinMode(PIN_WHEEL_A, INPUT_PULLUP); pinMode(PIN_WHEEL_B, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_WHEEL_A), wheel_isr, CHANGE);
    hud.send_cmd = send_cmd;
    hud.on_transcribe_toggle = []() { if (capturing) stop_capture(); else start_capture(); };
    hud.init();
    NimBLEDevice::init("CyclopsXIAO");
    srv = NimBLEDevice::createServer();
    srv->setCallbacks(new SrvCb());
    NimBLEService* s = srv->createService(SRVC);
    note_ch = s->createCharacteristic(NOTE_CH, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY | NIMBLE_PROPERTY::WRITE);
    note_cb = new NoteCb();
    note_ch->setCallbacks(note_cb);
    s->start();
    NimBLEAdvertising* adv = NimBLEDevice::getAdvertising();
    adv->addServiceUUID(SRVC);
    adv->start();
}

static bool last_a=true, last_b=true;
static uint32_t last_hb=0;

void loop() {
    static int prev = 0;
    if (wheel_ticks != prev) { hud.on_wheel(wheel_ticks - prev > 0 ? 1 : -1); prev = wheel_ticks; }
    bool a = digitalRead(PIN_BTN_A), b = digitalRead(PIN_BTN_B);
    if (!a && last_a) hud.on_select();
    if (!b && last_b) hud.on_long_back();   // long-press back also stops capture
    last_a=a; last_b=b;
    if (millis()-last_hb > 5000) {
        last_hb = millis();
        char s[80]; int n = hud.status_json(s, sizeof(s)); send_frame(cyclops::MSG_STATUS, (uint8_t*)s, n);
    }
    hud.render(screen);
    delay(50);
}
