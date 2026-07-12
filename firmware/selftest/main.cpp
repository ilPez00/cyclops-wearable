// XIAO ESP32-S3 Sense hardware selftest: SD card, OV2640 camera, PDM mic.
// Prints structured [sd]/[cam]/[mic] results over serial; dumps one JPEG as
// base64 between CAMB64_BEGIN/END markers so the host can decode and view it.

#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>
#include <math.h>
#include "esp_camera.h"
#include "driver/i2s.h"
#include "mbedtls/base64.h"

// ---- XIAO ESP32-S3 Sense pin maps (Seeed wiki) ----
static constexpr int SD_CS = 21;  // SPI bus 7/8/9 (framework default)

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

#define MIC_PDM_CLK 42
#define MIC_PDM_DATA 41
#define MIC_RATE 16000

// Build with -DSELFTEST_SD_FORMAT=1 to FORMAT (erase!) a card that has no
// mountable FAT volume. Off by default so the selftest never destroys data.
#ifndef SELFTEST_SD_FORMAT
#define SELFTEST_SD_FORMAT 0
#endif

static void test_sd() {
  Serial.printf("[sd] begin (format_if_mount_failed=%d)\n", SELFTEST_SD_FORMAT);
  if (!SD.begin(SD_CS, SPI, 4000000, "/sd", 5, SELFTEST_SD_FORMAT != 0)) {
    Serial.println("[sd] FAIL mount (no card, or not FAT16/FAT32 — reformat FAT32, or build with -DSELFTEST_SD_FORMAT=1)");
    return;
  }
  uint8_t t = SD.cardType();
  Serial.printf("[sd] card type=%d size=%lluMB\n", t, SD.cardSize() / (1024ULL * 1024ULL));
  const char* path = "/selftest.txt";
  File w = SD.open(path, FILE_WRITE);
  if (!w) { Serial.println("[sd] FAIL open for write"); return; }
  const char* msg = "cyclops selftest 2026-07-12";
  w.println(msg);
  w.close();
  File r = SD.open(path, FILE_READ);
  if (!r) { Serial.println("[sd] FAIL reopen for read"); return; }
  String back = r.readStringUntil('\n');
  r.close();
  bool ok = back.startsWith(msg);
  SD.remove(path);
  Serial.printf("[sd] write+readback %s ('%s')\n", ok ? "OK" : "FAIL", back.c_str());
}

static void dump_b64(const uint8_t* buf, size_t len) {
  Serial.println("CAMB64_BEGIN");
  static uint8_t line[97];  // 72 input bytes -> 96 b64 chars + NUL
  for (size_t off = 0; off < len; off += 72) {
    size_t chunk = min((size_t)72, len - off), out = 0;
    mbedtls_base64_encode(line, sizeof(line), &out, buf + off, chunk);
    line[out] = 0;
    Serial.println((const char*)line);
  }
  Serial.println("CAMB64_END");
}

static void test_camera() {
  Serial.println("[cam] begin");
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_pwdn = CAM_PWDN; c.pin_reset = CAM_RESET; c.pin_xclk = CAM_XCLK;
  c.pin_sccb_sda = CAM_SIOD; c.pin_sccb_scl = CAM_SIOC;
  c.pin_d7 = CAM_Y9; c.pin_d6 = CAM_Y8; c.pin_d5 = CAM_Y7; c.pin_d4 = CAM_Y6;
  c.pin_d3 = CAM_Y5; c.pin_d2 = CAM_Y4; c.pin_d1 = CAM_Y3; c.pin_d0 = CAM_Y2;
  c.pin_vsync = CAM_VSYNC; c.pin_href = CAM_HREF; c.pin_pclk = CAM_PCLK;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  if (psramFound()) {
    c.frame_size = FRAMESIZE_VGA;   // 640x480
    c.jpeg_quality = 12;
    c.fb_count = 2;
    c.fb_location = CAMERA_FB_IN_PSRAM;
  } else {
    c.frame_size = FRAMESIZE_QVGA;  // 320x240, DRAM fallback
    c.jpeg_quality = 15;
    c.fb_count = 1;
    c.fb_location = CAMERA_FB_IN_DRAM;
  }
  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("[cam] FAIL init err=0x%x\n", err);
    return;
  }
  Serial.printf("[cam] init OK psram=%d\n", psramFound() ? 1 : 0);
  // warm-up frames (auto exposure/white balance settle)
  for (int i = 0; i < 3; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
    delay(120);
  }
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("[cam] FAIL frame grab");
  } else {
    Serial.printf("[cam] frame OK %ux%u fmt=%d len=%u\n", fb->width, fb->height,
                  fb->format, fb->len);
    dump_b64(fb->buf, fb->len);
    esp_camera_fb_return(fb);
  }
  esp_camera_deinit();
}

static void test_mic() {
  Serial.println("[mic] begin (PDM clk=42 data=41)");
  i2s_config_t cfg = {};
  cfg.mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_PDM);
  cfg.sample_rate = MIC_RATE;
  cfg.bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT;
  cfg.channel_format = I2S_CHANNEL_FMT_ONLY_LEFT;
  cfg.communication_format = I2S_COMM_FORMAT_STAND_I2S;
  cfg.intr_alloc_flags = 0;
  cfg.dma_buf_count = 8;
  cfg.dma_buf_len = 256;
  if (i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL) != ESP_OK) {
    Serial.println("[mic] FAIL driver install");
    return;
  }
  i2s_pin_config_t pins = {};
  pins.mck_io_num = I2S_PIN_NO_CHANGE;
  pins.bck_io_num = I2S_PIN_NO_CHANGE;
  pins.ws_io_num = MIC_PDM_CLK;      // PDM clock
  pins.data_out_num = I2S_PIN_NO_CHANGE;
  pins.data_in_num = MIC_PDM_DATA;   // PDM data
  if (i2s_set_pin(I2S_NUM_0, &pins) != ESP_OK) {
    Serial.println("[mic] FAIL set pin");
    i2s_driver_uninstall(I2S_NUM_0);
    return;
  }
  // discard 300 ms (driver settle), then 2 s capture
  static int16_t buf[512];
  size_t rd = 0;
  uint32_t t0 = millis();
  while (millis() - t0 < 300) i2s_read(I2S_NUM_0, buf, sizeof(buf), &rd, pdMS_TO_TICKS(100));
  int64_t sum = 0, n = 0;
  int16_t mn = 32767, mx = -32768;
  double sq = 0;
  t0 = millis();
  while (millis() - t0 < 2000) {
    if (i2s_read(I2S_NUM_0, buf, sizeof(buf), &rd, pdMS_TO_TICKS(100)) != ESP_OK) continue;
    int cnt = rd / 2;
    for (int i = 0; i < cnt; i++) {
      int16_t s = buf[i];
      sum += s; n++;
      if (s < mn) mn = s;
      if (s > mx) mx = s;
    }
  }
  double mean = n ? (double)sum / n : 0;
  // second pass estimate of RMS around DC using min/max is rough; redo quick capture for RMS
  t0 = millis();
  int64_t n2 = 0;
  while (millis() - t0 < 1000) {
    if (i2s_read(I2S_NUM_0, buf, sizeof(buf), &rd, pdMS_TO_TICKS(100)) != ESP_OK) continue;
    int cnt = rd / 2;
    for (int i = 0; i < cnt; i++) { double d = buf[i] - mean; sq += d * d; n2++; }
  }
  double rms = n2 ? sqrt(sq / n2) : 0;
  i2s_driver_uninstall(I2S_NUM_0);
  Serial.printf("[mic] samples=%lld dc=%.1f min=%d max=%d rms=%.1f -> %s\n",
                (long long)n, mean, mn, mx, rms,
                (n > 10000 && rms > 3.0 && mx > mn) ? "OK (signal present)" : "FAIL (flat/silent)");
}

void setup() {
  Serial.begin(115200);
  delay(2500);  // give the host time to open the port
  Serial.println("[selftest] XIAO S3 Sense: sd, camera, mic");
  test_sd();
  test_camera();
  test_mic();
  Serial.println("[selftest] DONE");
}

void loop() { delay(1000); }
