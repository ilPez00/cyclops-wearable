// See camera_capture.h.
#include "camera_capture.h"
#include "sd_log.h"
#include <Arduino.h>

#ifndef ARDUINO
// Host (g++) build: no WiFi/camera stack here, no fake worth building --
// unlike imu.cpp's register logic or presence/posture's math, there is no
// meaningful pure-logic slice to test off-device. Safe no-op stubs so the
// host gate still links (matches ring_ble.cpp/sd_log.cpp precedent: neither
// has a host test either).
namespace cyclops {
const char* CameraCapture::request(unsigned long) { return ""; }
void CameraCapture::tick(unsigned long) {}
bool CameraCapture::ensure_camera() { return false; }
bool CameraCapture::ensure_wifi_and_server() { return false; }
void CameraCapture::teardown_wifi() {}
}
#else

#include <FS.h>
#include <SD.h>
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"

// XIAO ESP32-S3 Sense camera pins (Seeed wiki) -- identical to
// selftest/main.cpp's proven-on-metal config (2026-07-12 bring-up).
#define CAM_PWDN -1
#define CAM_RESET -1
#define CAM_XCLK 10
#define CAM_SIOD 40
#define CAM_SIOC 39
#define CAM_Y9 48
#define CAM_Y8 11
#define CAM_Y7 12
#define CAM_Y6 14
#define CAM_Y5 16
#define CAM_Y4 18
#define CAM_Y3 17
#define CAM_Y2 15
#define CAM_VSYNC 38
#define CAM_HREF 47
#define CAM_PCLK 13

namespace cyclops {

static WebServer* g_server = nullptr;
static const char* STREAM_BOUNDARY = "\r\n--frame\r\n";
static const char* STREAM_PART = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

static void handle_capture() {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) { Serial.println("[cam-cap] GET /capture -> fb_get failed"); g_server->send(503, "text/plain", "capture failed"); return; }
    Serial.printf("[cam-cap] GET /capture -> %u bytes\n", (unsigned)fb->len);
    g_server->send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
    esp_camera_fb_return(fb);
}

static void handle_snap() {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) { g_server->send(500, "text/plain", "capture failed"); return; }
    g_server->sendHeader("Content-Disposition", "inline; filename=snap.jpg");
    g_server->send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
    esp_camera_fb_return(fb);
}

static void handle_stream_root() {
    String html = "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<title>Cyclops Camera</title>"
        "<style>body{margin:0;background:#111;color:#eee;"
        "font-family:system-ui,sans-serif;text-align:center}"
        "h1{padding:1em}img{max-width:100%;height:auto}</style></head><body>"
        "<h1>Cyclops &mdash; live</h1>"
        "<img src=\"/stream\" /></body></html>";
    g_server->send(200, "text/html; charset=utf-8", html);
}

static void handle_stream() {
    Serial.println("[cam-cap] /stream requested");
    WiFiClient client = g_server->client();
    client.println("HTTP/1.1 200 OK");
    client.println("Content-Type: multipart/x-mixed-replace; boundary=frame");
    client.println("Cache-Control: no-cache");
    client.println("Connection: close");
    client.println();
    char part_buf[64];
    while (client.connected()) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) { delay(100); continue; }
        client.print(STREAM_BOUNDARY);
        size_t hlen = snprintf(part_buf, sizeof(part_buf), STREAM_PART, fb->len);
        client.write((const uint8_t*)part_buf, hlen);
        size_t sent = client.write(fb->buf, fb->len);
        esp_camera_fb_return(fb);
        if (sent != fb->len) { Serial.println("[cam-cap] /stream short write"); break; }
        delay(100);  // ~10 fps
    }
    Serial.println("[cam-cap] /stream closed");
}

// Camera init profile — tries multiple configs and falls back.
// Pattern from Complete-voice-and-vision-AI-using-XIAO-ESP32-S3-Sense.
struct CameraProfile {
    framesize_t frame_size;
    uint32_t xclk_hz;
};
static const CameraProfile CAM_PROFILES[] = {
    {FRAMESIZE_VGA,  20000000},
    {FRAMESIZE_VGA,  16000000},
    {FRAMESIZE_QVGA, 20000000},
};
static constexpr int NUM_CAM_PROFILES = sizeof(CAM_PROFILES) / sizeof(CAM_PROFILES[0]);

bool CameraCapture::ensure_camera() {
    if (cam_ready_) return true;
    bool has_psram = psramFound();
    for (int i = 0; i < NUM_CAM_PROFILES; ++i) {
        if (i > 0) {
            esp_camera_deinit();
            delay(50);
        }
        camera_config_t c = {};
        c.ledc_channel = LEDC_CHANNEL_0;
        c.ledc_timer = LEDC_TIMER_0;
        c.pin_pwdn = CAM_PWDN; c.pin_reset = CAM_RESET; c.pin_xclk = CAM_XCLK;
        c.pin_sccb_sda = CAM_SIOD; c.pin_sccb_scl = CAM_SIOC;
        c.pin_d7 = CAM_Y9; c.pin_d6 = CAM_Y8; c.pin_d5 = CAM_Y7; c.pin_d4 = CAM_Y6;
        c.pin_d3 = CAM_Y5; c.pin_d2 = CAM_Y4; c.pin_d1 = CAM_Y3; c.pin_d0 = CAM_Y2;
        c.pin_vsync = CAM_VSYNC; c.pin_href = CAM_HREF; c.pin_pclk = CAM_PCLK;
        c.xclk_freq_hz = CAM_PROFILES[i].xclk_hz;
        c.pixel_format = PIXFORMAT_JPEG;
        c.frame_size = CAM_PROFILES[i].frame_size;
        if (has_psram) {
            c.jpeg_quality = 12; c.fb_count = 2;
            c.fb_location = CAMERA_FB_IN_PSRAM;
            c.grab_mode = CAMERA_GRAB_LATEST;
        } else {
            c.jpeg_quality = 15; c.fb_count = 1;
            c.fb_location = CAMERA_FB_IN_DRAM;
            c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
        }
        esp_err_t err = esp_camera_init(&c);
        if (err == ESP_OK) {
            cam_ready_ = true;
            Serial.printf("[cam-cap] camera OK profile=%dx%d@%dHz psram=%d\n",
                          (int)c.frame_size, (int)c.frame_size, (int)c.xclk_freq_hz, has_psram);
            return true;
        }
        Serial.printf("[cam-cap] camera FAIL profile=%dx%d@%dHz err=0x%x\n",
                      (int)c.frame_size, (int)c.frame_size, (int)c.xclk_freq_hz, err);
    }
    Serial.println("[cam-cap] all camera profiles exhausted");
    return false;
}

// Reads SSID (line 1) + password (line 2) from /wifi.txt on the already-
// mounted SD card. Returns false (leaving both strings empty) if the card
// or file is absent -- this feature is then simply unavailable, not a hard
// failure (same convention as everything else that stubs without config).
static bool read_wifi_creds(char* ssid, size_t ssid_len, char* pass, size_t pass_len) {
    if (!sd_ready()) { Serial.println("[cam-cap] sd not ready"); return false; }
    File f = SD.open("/wifi.txt", FILE_READ);
    if (!f) { Serial.println("[cam-cap] /wifi.txt not found"); return false; }
    String s = f.readStringUntil('\n'); s.trim();
    String p = f.readStringUntil('\n'); p.trim();
    f.close();
    if (s.length() == 0) { Serial.println("[cam-cap] /wifi.txt empty ssid line"); return false; }
    Serial.printf("[cam-cap] read wifi.txt ssid='%s' len(pass)=%d\n", s.c_str(), p.length());
    s.toCharArray(ssid, ssid_len);
    p.toCharArray(pass, pass_len);
    return true;
}

bool CameraCapture::ensure_wifi_and_server() {
    if (server_up_) return true;
    Serial.printf("[cam-cap] sd_ready()=%d before camera init\n", sd_ready());
    if (!ensure_camera()) { Serial.println("[cam-cap] camera init failed"); return false; }
    Serial.printf("[cam-cap] sd_ready()=%d after camera init\n", sd_ready());
    char ssid[64] = "", pass[64] = "";
    if (!read_wifi_creds(ssid, sizeof(ssid), pass, sizeof(pass))) {
        Serial.println("[cam-cap] no wifi.txt / sd not ready");
        return false;
    }
    Serial.printf("[cam-cap] joining wifi ssid='%s'...\n", ssid);
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);
    // Bounded wait -- this runs on the main task (called from loop()), so a
    // long/unbounded join must not stall button/BLE handling indefinitely.
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 8000) delay(100);
    if (WiFi.status() != WL_CONNECTED) {
        Serial.printf("[cam-cap] wifi join FAILED status=%d\n", (int)WiFi.status());
        WiFi.mode(WIFI_OFF);
        return false;
    }
    g_server = new WebServer(80);
    g_server->on("/capture", handle_capture);
    g_server->on("/snap", handle_snap);
    g_server->on("/stream", handle_stream);
    g_server->on("/", handle_stream_root);
    g_server->begin();
    snprintf(url_, sizeof(url_), "http://%s/capture", WiFi.localIP().toString().c_str());
    server_up_ = true;
    Serial.printf("[cam-cap] server up at %s\n", url_);
    return true;
}

void CameraCapture::teardown_wifi() {
    if (!server_up_) return;
    Serial.println("[cam-cap] idle teardown -- wifi off, ble undisturbed");
    g_server->stop();
    delete g_server;
    g_server = nullptr;
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    server_up_ = false;
    url_[0] = 0;
}

const char* CameraCapture::request(unsigned long now) {
    last_request_ = now;
    if (!ensure_wifi_and_server()) return "";
    return url_;
}

void CameraCapture::tick(unsigned long now) {
    if (!server_up_) return;
    g_server->handleClient();
    if (now - last_request_ >= idle_ms_) teardown_wifi();
}

}  // namespace cyclops
#endif  // ARDUINO
