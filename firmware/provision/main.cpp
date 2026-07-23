// SD-card provisioning tool: writes /wifi.txt (SSID line 1, password line
// 2 -- see xiao/src/camera_capture.cpp's read_wifi_creds()) from two lines
// sent over serial at runtime. No credential is ever compiled into this
// binary or committed to git -- it only ever exists in the sender's
// process memory and on the wire over the same USB-serial link any other
// flashing/monitoring already uses. Generic: reusable for any future
// SD-config file, not wifi.txt-specific beyond the default path.
//
// Usage: flash this env, then send exactly two newline-terminated lines
// over serial (115200): SSID, then password. Prints [provision] OK/FAIL.
#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>

static constexpr int SD_CS = 21;  // XIAO S3 Sense onboard slot (Seeed wiki)

void setup() {
  Serial.begin(115200);
  while (!Serial) { delay(10); }
  Serial.setTimeout(20000);  // readStringUntil's default ~1s is way too
                             // tight for a human/script on the other end
                             // of a just-reset USB-CDC link to respond.
  Serial.println("[provision] begin");
  if (!SD.begin(SD_CS, SPI, 4000000, "/sd")) {
    Serial.println("[provision] FAIL sd mount");
    return;
  }
  Serial.println("[provision] sd mounted, waiting for SSID line...");
  String ssid = Serial.readStringUntil('\n');
  ssid.trim();
  Serial.println("[provision] waiting for password line...");
  String pass = Serial.readStringUntil('\n');
  pass.trim();
  if (ssid.length() == 0) {
    Serial.println("[provision] FAIL empty ssid");
    return;
  }
  File f = SD.open("/wifi.txt", FILE_WRITE);
  if (!f) {
    Serial.println("[provision] FAIL open for write");
    return;
  }
  f.println(ssid);
  f.println(pass);
  f.close();
  // read back to confirm, without ever echoing the password to serial
  File r = SD.open("/wifi.txt", FILE_READ);
  String back_ssid = r.readStringUntil('\n');
  back_ssid.trim();
  String back_pass = r.readStringUntil('\n');
  back_pass.trim();
  r.close();
  bool ok = (back_ssid == ssid) && (back_pass == pass);
  Serial.printf("[provision] %s wifi.txt written, ssid='%s' len(pass)=%d\n",
                ok ? "OK" : "FAIL", back_ssid.c_str(), back_pass.length());
}

void loop() { delay(1000); }
