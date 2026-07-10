// See sd_log.h. Uses the Arduino SD library on the Sense onboard slot.
// Slot pins (Seeed wiki): CS=GPIO21, SCK=GPIO7, MISO=GPIO8, MOSI=GPIO9.
// These are the framework default SPI bus on the ESP32-S3, so SD.begin(21)
// binds them automatically. They collide with the SPI *displays*, so SD
// logging is only meaningful on the I2C OLED build (which leaves them free).
#include "sd_log.h"
#include <Arduino.h>
#include <FS.h>
#include <SD.h>
#include <SPI.h>

namespace cyclops {

static bool sd_mounted = false;
static constexpr int SD_CS = 21;  // GPIO21 on the Sense expansion slot

bool sd_begin() {
  sd_mounted = SD.begin(SD_CS);  // default SPI bus (7/8/9)
  return sd_mounted;
}

bool sd_ready() { return sd_mounted; }

void sd_log_line(const char* tag, const char* text) {
  if (!sd_mounted) return;
  File f = SD.open("/cyclops.log", FILE_APPEND);
  if (!f) return;
  unsigned long sec = millis() / 1000;
  f.print('['); f.print(sec); f.print("s] ");
  if (tag && *tag) { f.print(tag); f.print(": "); }
  f.println(text);
  f.close();
}

}  // namespace cyclops
