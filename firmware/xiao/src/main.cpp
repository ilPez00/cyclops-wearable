// Cyclops XIAO ESP32-S3 Sense — wearable HUD + audio capture.
// scrollwheel + 2 buttons + screen (ST7735 / 128x64 / 128x32 via SCREEN_*).
// PDM mic (clk 42, data 41) -> ADPCM -> BLE audio chunks -> phone decodes+transcribes.
// BLE (NimBLE) to phone. Shares Hud + Screen.
// Build: pio run -e xiao_st7735 | xiao_128x64 | xiao_128x32
#include "cyclops_shared.h"
#include "screen.h"
#include "screens.h"
#include "hud.h"
#include "gestures.h"
#include "adpcm.h"
#include "ota.h"
#include <esp_ota_ops.h>
#include "ring_ble.h"
#include "sd_log.h"
#include "imu.h"
#include <Wire.h>
#include <NimBLEDevice.h>
#include <driver/i2s.h>

#if defined(SCREEN_ST7735)
// XIAO S3: HW-SPI SCK=GPIO7(D8) MOSI=GPIO9(D10) MISO=GPIO8(D9).
// CS=GPIO6(D5) DC=GPIO2(D1) RST=GPIO1(D0). CS must NOT be GPIO7 (that's SCK).
static cyclops::St7735Screen screen(6, 2, 1, 8, 10, 9);
#elif defined(SCREEN_128x64)
static cyclops::Ssd1306_128x64_Screen screen(6, 2, 1, 8, 10, 9, 1);
#elif defined(SCREEN_128x32)
static cyclops::Ssd1306_128x32_Screen screen(5, 2, 1, 8, 10, 9, 1);
#elif defined(SCREEN_128x32_I2C)
// 4-pin I2C OLED: only SDA/SCL/VCC/GND wired. SPI args ignored, rst_pin=-1.
static cyclops::Ssd1306_128x32_I2C_Screen screen(0, 0, 0, 0, 0, 0, -1);
#elif defined(SCREEN_TRANSPARENT_151)
// Waveshare 1.51" transparent OLED (128x64, SSD1309), 4-wire SPI.
// CS=GPIO6(D5) DC=GPIO2(D1) RST=GPIO1(D0). SCK=GPIO7 MOSI=GPIO9 MISO=GPIO8.
static cyclops::Transparent151Screen screen(6, 2, 1, 8, 10, 9, 1);
#elif defined(SCREEN_TRANSPARENT_151_I2C)
// Waveshare 1.51" transparent OLED in I2C mode: only SDA/SCL/VCC/GND wired.
static cyclops::Transparent151I2CScreen screen(0, 0, 0, 0, 0, 0, -1);
#endif

#define PIN_WHEEL_A 0
#define PIN_WHEEL_B 4
#define PIN_BTN_A  3
#define PIN_BTN_B  5   // was 4 (aliased WHEEL_B); GPIO5 is free on XIAO S3

// Onboard mic (XIAO S3 Sense MSM261D) is a PDM mic: clock GPIO42, data GPIO41.
// Verified on metal 2026-07-12 — standard I2S on 40/41/42 reads silence, and
// GPIO40 is the camera's SCCB SDA. PDM mode is the only correct config here.
#ifndef MIC_PDM_CLK
#define MIC_PDM_CLK 42
#endif
#ifndef MIC_PDM_DATA
#define MIC_PDM_DATA 41
#endif
#define MIC_RATE 16000
#define MIC_BUF_SAMPLES 256

static cyclops::Hud hud;
#ifdef ENABLE_RING
static cyclops::RingBle ring;          // COLMI R02 BLE central (opt-in)
#endif
#ifdef ENABLE_IMU
static cyclops::Imu imu(0x68, 1);      // HW-123 ITG/MPU on I2C (D6/D7), INT->D1
#endif
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

// ---- OTA-over-BLE receive path (shared OtaReceiver + esp_ota_* sinks) ----
// Rationale: the USB-C connector is the board's weakest part (one died
// 2026-07-12 with a live chip behind a dead port). BLE reflash means a broken
// connector no longer strands the firmware. Trust model matches the rest of
// the link (unauthenticated, ~1 m body range — see docs/07 §4).
static esp_ota_handle_t ota_handle = 0;
static const esp_partition_t* ota_part = nullptr;

static bool ota_sink_begin(uint32_t size, void*) {
    ota_part = esp_ota_get_next_update_partition(NULL);
    if (!ota_part) return false;  // no OTA partition in the table
    return esp_ota_begin(ota_part, size, &ota_handle) == ESP_OK;
}
static bool ota_sink_write(const uint8_t* d, size_t len, void*) {
    return esp_ota_write(ota_handle, d, len) == ESP_OK;
}
static bool ota_sink_finish(bool commit, void*) {
    if (!commit) { esp_ota_abort(ota_handle); return true; }
    if (esp_ota_end(ota_handle) != ESP_OK) return false;
    return esp_ota_set_boot_partition(ota_part) == ESP_OK;
}
static cyclops::OtaSink make_ota_sink() {
    cyclops::OtaSink s;
    s.begin = ota_sink_begin;
    s.write = ota_sink_write;
    s.finish = ota_sink_finish;
    s.ctx = nullptr;
    return s;
}
static cyclops::OtaReceiver& ota_rx() {
    static cyclops::OtaReceiver rx(make_ota_sink());
    return rx;
}

// Handle one MSG_OTA_* frame: drive the receiver, ACK every message, show
// progress on the HUD, reboot after a committed END.
static void on_ota_frame(uint8_t type, const uint8_t* p, size_t n) {
    uint32_t seq = 0;
    cyclops::OtaStatus st;
    if (type == cyclops::MSG_OTA_BEGIN) {
        st = ota_rx().on_begin(p, n, &seq);
        if (st == cyclops::OTA_OK) { hud.toast("OTA start", 3); hud.progress = 0; }
    } else if (type == cyclops::MSG_OTA_CHUNK) {
        st = ota_rx().on_chunk(p, n, &seq);
        uint32_t exp = ota_rx().expected();
        if (st == cyclops::OTA_OK && exp) hud.progress = (int)(100ull * ota_rx().received() / exp);
    } else {  // MSG_OTA_END
        st = ota_rx().on_end(&seq);
    }
    char ack[48]; int m = cyclops::OtaReceiver::ack_json(ack, sizeof(ack), seq, st);
    send_frame(cyclops::MSG_OTA_ACK, (const uint8_t*)ack, (size_t)m);
    if (type == cyclops::MSG_OTA_END && st == cyclops::OTA_OK) {
        hud.toast("OTA ok, reboot", 2);
        cyclops::sd_log_line("ota", "commit + reboot");
        delay(400);  // let the ACK notify flush before the link drops
        esp_restart();
    } else if (st != cyclops::OTA_OK) {
        hud.progress = 0;
        hud.toast("OTA fail", 3);
    }
}

static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx) {
    (void)ctx;
    if (type == cyclops::MSG_OTA_BEGIN || type == cyclops::MSG_OTA_CHUNK ||
        type == cyclops::MSG_OTA_END) {
        on_ota_frame(type, p, n);  // binary payload — must not go through tmp
        return;
    }
    char tmp[256]; if (n >= sizeof(tmp)) n = sizeof(tmp)-1;
    memcpy(tmp, p, n); tmp[n] = 0;
    if (type == cyclops::MSG_DISPLAY_CMD || type == cyclops::MSG_NOTE) {
        ui_apply_display(tmp);
        if (type == cyclops::MSG_NOTE) cyclops::sd_log_line("note", tmp);
    }
    else if (type == cyclops::MSG_HEALTH_SAMPLE) {
        hud.on_health_sample(tmp);  // P2-C relay
        cyclops::sd_log_line("health", tmp);
    }
    else if (type == cyclops::MSG_CMD) {
        // Phone -> wearable action, same {"a":<ACT_*>,"arg":...} shape the
        // wearable emits. Lets the brain drive capture/menu remotely instead
        // of only reacting to on-device input.
        const char* av = strstr(tmp, "\"a\":");
        if (av) {
            int a = atoi(av + 4);
            if (a == cyclops::ACT_TRANSCRIBE_START) {
                // Same consent gate as on-device capture (on_nod/do_action):
                // remote start must not bypass Consent Mode.
                if (!capturing && !hud.consent) { hud.toast("consent off", 2); }
                else if (capturing) stop_capture();
                else start_capture();
            } else {
                hud.do_action((uint8_t)a);
            }
        }
    }
}

static void ui_apply_display(const char* json) {
    hud.apply_display_cmd(json);
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

// Raw PCM16 at 16 kHz is 32 KB/s; the BLE notify link measures ~2-8 KB/s
// (docs/13 premortem #2), so raw streaming can never keep up. Compress each
// read with IMA ADPCM (4:1, shared/include/adpcm.h): a 256-sample read
// becomes 4+128 = 132 B — one notify-sized frame, no slicing. The step index
// is carried across chunks (warm adaption); each chunk stays self-contained
// so a lost notify costs only its own ~16 ms window.
static void audio_task(void*) {
    int16_t samples[MIC_BUF_SAMPLES];
    uint8_t enc[4 + (MIC_BUF_SAMPLES + 1) / 2];
    int adpcm_index = 0;
    size_t rd;
    while (capturing) {
        i2s_read((i2s_port_t)0, samples, sizeof(samples), &rd, pdMS_TO_TICKS(100));
        if (rd > 0) {
            // Backpressure: only stream audio when a phone is actually
            // connected to receive it. Sending into the void wastes the BLE
            // queue and battery; drop the chunk instead. (D)
            if (hud.bt) {
                size_t k = cyclops::adpcm_encode_chunk(samples, rd / 2, enc,
                                                       sizeof(enc),
                                                       adpcm_index, &adpcm_index);
                if (k > 0) send_frame(cyclops::MSG_AUDIO_CHUNK, enc, k);
            } else {
                cyclops::audio_dropped++;  // no consumer -> drop
            }
        }
    }
    vTaskDelete(NULL);
}

static void start_capture() {
    if (capturing) return;
    i2s_config_t cfg = {};
    cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM);
    cfg.sample_rate = MIC_RATE;
    cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
    cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
    cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
    cfg.intr_alloc_flags = 0;
    cfg.dma_buf_count = 4; cfg.dma_buf_len = MIC_BUF_SAMPLES;
    i2s_pin_config_t pins = {};
    // PDM RX: ws pin carries the PDM clock, data_in the PDM bitstream.
    pins.mck_io_num = I2S_PIN_NO_CHANGE;
    pins.bck_io_num = I2S_PIN_NO_CHANGE; pins.ws_io_num = MIC_PDM_CLK;
    pins.data_in_num = MIC_PDM_DATA; pins.data_out_num = I2S_PIN_NO_CHANGE;
    i2s_driver_install((i2s_port_t)0, &cfg, 0, NULL);
    i2s_set_pin((i2s_port_t)0, &pins);
    capturing = true;
    // announce format once: bits, rate, channels, codec (meta[5])
    uint8_t meta[8]; meta[0]=16; meta[1]=0; meta[2]=MIC_RATE&0xFF; meta[3]=(MIC_RATE>>8)&0xFF;
    meta[4]=1; meta[5]=cyclops::AUDIO_CODEC_ADPCM; meta[6]=0; meta[7]=0;
    send_frame(cyclops::MSG_AUDIO_META, meta, 8);
    xTaskCreatePinnedToCore(audio_task, "cap", 4096, NULL, 5, &cap_task, 0);
    hud.recording = true;
    cyclops::sd_log_line("rec", "start");
}

static void stop_capture() {
    if (!capturing) return;
    capturing = false;
    delay(120);
    i2s_driver_uninstall((i2s_port_t)0);
    send_frame(cyclops::MSG_AUDIO_STOP, NULL, 0);
    hud.recording = false;
    cyclops::sd_log_line("rec", "stop");
}

void setup() {
    Serial.begin(115200);
    Serial.println("[boot] Cyclops XIAO S3 Sense");
#ifdef SCREEN_ST7735
    Serial.println("[boot] screen=ST7735 128x128");
#elif defined(SCREEN_128x64)
    Serial.println("[boot] screen=SSD1306 128x64");
#elif defined(SCREEN_128x32)
    Serial.println("[boot] screen=SSD1306 128x32");
#elif defined(SCREEN_TRANSPARENT_151)
    Serial.println("[boot] screen=Transparent 1.51in SSD1309 128x64");
#elif defined(SCREEN_TRANSPARENT_151_I2C)
    Serial.println("[boot] screen=Transparent 1.51in SSD1309 128x64 (I2C)");
#endif
    screen.begin();
    Serial.println("[boot] screen.begin ok");
    pinMode(PIN_BTN_A, INPUT_PULLUP); pinMode(PIN_BTN_B, INPUT_PULLUP);
    pinMode(PIN_WHEEL_A, INPUT_PULLUP); pinMode(PIN_WHEEL_B, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(PIN_WHEEL_A), wheel_isr, CHANGE);
    hud.send_cmd = send_cmd;
    hud.on_transcribe_toggle = []() { if (capturing) stop_capture(); else start_capture(); };
    hud.on_note = [](const char* t) { cyclops::sd_log_line("hud", t); };
    hud.init();
    Serial.println("[boot] hud.init ok");
    if (cyclops::sd_begin()) Serial.println("[boot] sd card mounted /sdcard");
    else Serial.println("[boot] sd card NOT present (logging disabled)");
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
#ifdef ENABLE_RING
    ring.begin("R02_");   // scan for + connect to the COLMI R02 (see docs/30)
#endif
#ifdef ENABLE_IMU
    if (imu.begin()) Serial.println("[boot] imu ok");
    else Serial.println("[boot] imu NOT found (0x68)");
#endif
}

static uint32_t last_hb=0;
static cyclops::GestureDetector gest_a, gest_b;   // A="eye", B="ear"

void loop() {
    static int prev = 0;
    if (wheel_ticks != prev) { hud.on_wheel(wheel_ticks - prev > 0 ? 1 : -1); prev = wheel_ticks; }
    uint32_t now = millis();
    // buttons are active-low; detector wants pressed=true
    cyclops::Gesture ga = gest_a.poll(!digitalRead(PIN_BTN_A), now);
    cyclops::Gesture gb = gest_b.poll(!digitalRead(PIN_BTN_B), now);
    if (ga) hud.fire_gesture(0, ga);   // A: single=OK double=photo long=video
    if (gb) hud.fire_gesture(1, gb);   // B: single=back double=voice-note long=voice-cmd
#ifdef ENABLE_RING
    ring.update();
    if (ring.connected()) {
        const auto& s = ring.sample();
        hud.set_health(s.hr, s.spo2, s.battery, s.battery);  // ring_batt == bead_batt slot
    }
#endif
#ifdef ENABLE_IMU
    if (imu.update()) {
        hud.nav_head = imu.sample().heading;           // tilt/nav heading
        int tilt = imu.scroll_tilt();
        if (tilt != 0) hud.on_wheel(tilt);             // tilt = scroll
    }
#endif
    if (millis()-last_hb > 5000) {
        last_hb = millis();
        char s[160]; int n = hud.status_json(s, sizeof(s)); send_frame(cyclops::MSG_STATUS, (uint8_t*)s, n);
        Serial.printf("[hb] %s rec=%d bt=%d mode=%s drop=%lu\n", s, hud.recording,
                      hud.bt, hud.mode_name(hud.top()), cyclops::audio_dropped);
    }
    hud.render(screen);
    // Power: when the screen is off and we're not recording, the wearable is
    // idle — skip the per-frame render and sleep longer to save juice. (C)
    if (!hud.screen_on && !capturing) {
        delay(250);
    } else {
        delay(50);
    }
}
