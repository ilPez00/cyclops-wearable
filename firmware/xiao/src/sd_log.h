// MicroSD logging for the XIAO ESP32-S3 Sense onboard slot.
// Slot pins: CS=GPIO21, SCK=GPIO7, MISO=GPIO8, MOSI=GPIO9 (Seeed wiki).
// NOTE: those SPI pins collide with the SPI displays (ST7735/SSD1306-SPI),
// so SD logging is only meaningful on the I2C OLED build (which leaves them free).
#ifndef SD_LOG_H
#define SD_LOG_H
#include <stdint.h>
namespace cyclops {
// Mount /sdcard. Returns true if a FAT32 card is present.
bool sd_begin();
bool sd_ready();
// Append one timestamped line to /sdcard/cyclops.log. No-op if no card.
void sd_log_line(const char* tag, const char* text);
}
#endif  // SD_LOG_H
