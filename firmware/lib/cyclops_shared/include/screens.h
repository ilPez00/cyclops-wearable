#ifndef CYCLOPS_SCREENS_H
#define CYCLOPS_SCREENS_H
// Three panel drivers implementing cyclops::Screen via Adafruit libraries.
// Selected at compile time by -DSCREEN_ST7735 | -DSCREEN_128x64 | -DSCREEN_128x32.
#include "screen.h"

#if defined(SCREEN_ST7735)
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
namespace cyclops {
// 128x128 RGB565 TFT. Green-on-black for the "clear" look.
class St7735Screen : public Screen {
public:
    St7735Screen(int cs, int dc, int rst, int sck, int mosi, int miso)
        : tft_(cs, dc, rst) { (void)sck;(void)mosi;(void)miso; }
    int w() const override { return 128; }
    int h() const override { return 128; }
    int char_cols() const override { return 21; }
    int text_rows() const override { return 16; }
    void begin() override { tft_.initR(INITR_144GREENTAB); tft_.setRotation(0); tft_.fillScreen(ST77XX_BLACK); tft_.setTextSize(1); tft_.setTextColor(0x07E0); }
    void clear() override { tft_.fillScreen(ST77XX_BLACK); }
    void set_ink(bool on) override { tft_.setTextColor(on ? 0x07E0 : ST77XX_BLACK); }
    void draw_text(int col, int row, const char* s) override { tft_.setCursor(col*6, row*10); tft_.print(s); }
    void draw_rect(int x,int y,int w,int h,bool on) override { if(on) tft_.fillRect(x,y,w,h,0x07E0); else tft_.fillRect(x,y,w,h,ST77XX_BLACK); }
    void flush() override {}
    void text_size(int s) override { tft_.setTextSize(s>0?s:1); }
private:
    Adafruit_ST7735 tft_;
};
}
#elif defined(SCREEN_128x64)
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
namespace cyclops {
class Ssd1306_128x64_Screen : public Screen {
public:
    Ssd1306_128x64_Screen(int cs, int dc, int rst, int sck, int mosi, int miso, int rst_pin=-1)
        : disp_(128,64,&SPI,cs,dc,rst_pin) { (void)sck;(void)mosi;(void)miso; }
    int w() const override { return 128; }
    int h() const override { return 64; }
    int char_cols() const override { return 21; }
    int text_rows() const override { return 8; }
    void begin() override { disp_.begin(SSD1306_SWITCHCAPVCC); disp_.clearDisplay(); disp_.setTextSize(1); disp_.setTextColor(SSD1306_WHITE); }
    void clear() override { disp_.clearDisplay(); }
    void set_ink(bool on) override { disp_.setTextColor(on?SSD1306_WHITE:SSD1306_BLACK); }
    void draw_text(int col,int row,const char* s) override { disp_.setCursor(col*6,row*8); disp_.print(s); }
    void draw_rect(int x,int y,int w,int h,bool on) override { if(on) disp_.fillRect(x,y,w,h,SSD1306_WHITE); else disp_.fillRect(x,y,w,h,SSD1306_BLACK); }
    void flush() override { disp_.display(); }
private:
    Adafruit_SSD1306 disp_;
};
}
#elif defined(SCREEN_128x32)
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
namespace cyclops {
class Ssd1306_128x32_Screen : public Screen {
public:
    Ssd1306_128x32_Screen(int cs, int dc, int rst, int sck, int mosi, int miso, int rst_pin=-1)
        : disp_(128,32,&SPI,cs,dc,rst_pin) { (void)sck;(void)mosi;(void)miso; }
    int w() const override { return 128; }
    int h() const override { return 32; }
    int char_cols() const override { return 21; }
    int text_rows() const override { return 4; }
    void begin() override { disp_.begin(SSD1306_SWITCHCAPVCC); disp_.clearDisplay(); disp_.setTextSize(1); disp_.setTextColor(SSD1306_WHITE); }
    void clear() override { disp_.clearDisplay(); }
    void set_ink(bool on) override { disp_.setTextColor(on?SSD1306_WHITE:SSD1306_BLACK); }
    void draw_text(int col,int row,const char* s) override { disp_.setCursor(col*6,row*8); disp_.print(s); }
    void draw_rect(int x,int y,int w,int h,bool on) override { if(on) disp_.fillRect(x,y,w,h,SSD1306_WHITE); else disp_.fillRect(x,y,w,h,SSD1306_BLACK); }
    void flush() override { disp_.display(); }
private:
    Adafruit_SSD1306 disp_;
};
}
#elif defined(SCREEN_128x32_I2C)
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
namespace cyclops {
// 4-pin I2C SSD1306 128x32 (VCC/GND/SCL/SDA). Addr 0x3C (some are 0x3D).
// I2C on D6/D7 (GPIO43/44) to avoid the button/wheel pins (GPIO0/3/4/5).
class Ssd1306_128x32_I2C_Screen : public Screen {
public:
    // Signature kept 7-arg for main.cpp uniformity; SPI pins ignored.
    // sda/scl default to XIAO D6/D7; rst_pin=-1 (shared reset); addr 0x3C.
    Ssd1306_128x32_I2C_Screen(int cs, int dc, int rst, int sck, int mosi, int miso, int rst_pin=-1,
                              uint8_t addr=0x3C, int sda=43, int scl=44)
        : disp_(128,32,&Wire,rst_pin), addr_(addr), sda_(sda), scl_(scl) { (void)cs;(void)dc;(void)rst;(void)sck;(void)mosi;(void)miso; }
    int w() const override { return 128; }
    int h() const override { return 32; }
    int char_cols() const override { return 21; }
    int text_rows() const override { return 4; }
    void begin() override { Wire.begin(sda_, scl_); disp_.begin(SSD1306_SWITCHCAPVCC, addr_); disp_.clearDisplay(); disp_.setTextSize(1); disp_.setTextColor(SSD1306_WHITE); }
    void clear() override { disp_.clearDisplay(); }
    void set_ink(bool on) override { disp_.setTextColor(on?SSD1306_WHITE:SSD1306_BLACK); }
    void draw_text(int col,int row,const char* s) override { disp_.setCursor(col*6,row*8); disp_.print(s); }
    void draw_rect(int x,int y,int w,int h,bool on) override { if(on) disp_.fillRect(x,y,w,h,SSD1306_WHITE); else disp_.fillRect(x,y,w,h,SSD1306_BLACK); }
    void flush() override { disp_.display(); }
private:
    Adafruit_SSD1306 disp_;
    uint8_t addr_;
    int sda_, scl_;
};
}
#elif defined(SCREEN_TRANSPARENT_151)
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
namespace cyclops {
// Waveshare 1.51" Transparent OLED: 128x64, SSD1309 controller.
// SSD1309 is command-compatible with SSD1306, so the Adafruit_SSD1306 driver
// runs it unchanged (the charge-pump cmd is a harmless no-op on the SSD1309's
// external boost). The panel is see-through: lit pixels glow, unlit pixels are
// fully transparent (no black bg) — so we render "text only, no filled boxes"
// to keep the glass clear. Wired 4-wire SPI (module default): CS/DC/RST + SCK/MOSI.
class Transparent151Screen : public Screen {
public:
    Transparent151Screen(int cs, int dc, int rst, int sck, int mosi, int miso, int rst_pin=-1)
        : disp_(128,64,&SPI,cs,dc,(rst_pin>=0?rst_pin:rst)) { (void)sck;(void)mosi;(void)miso; }
    int w() const override { return 128; }
    int h() const override { return 64; }
    int char_cols() const override { return 21; }
    int text_rows() const override { return 8; }
    void begin() override {
        // SSD1309 uses an external VCC boost, not the on-chip charge pump.
        disp_.begin(SSD1306_EXTERNALVCC, 0x3C);
        disp_.clearDisplay(); disp_.setTextSize(1); disp_.setTextColor(SSD1306_WHITE);
        disp_.dim(false);   // max brightness — transparent panels are dim in daylight
    }
    void clear() override { disp_.clearDisplay(); }
    void set_ink(bool on) override { disp_.setTextColor(on?SSD1306_WHITE:SSD1306_BLACK); }
    void draw_text(int col,int row,const char* s) override { disp_.setCursor(col*6,row*8); disp_.print(s); }
    // On transparent glass a filled "off" rect would punch a visible black hole,
    // so only lit rects draw; clearing a rect is a no-op (leave it transparent).
    void draw_rect(int x,int y,int w,int h,bool on) override { if(on) disp_.fillRect(x,y,w,h,SSD1306_WHITE); }
    void draw_pixel(int x,int y,bool on=true) override { disp_.drawPixel(x,y,on?SSD1306_WHITE:SSD1306_BLACK); }
    void flush() override { disp_.display(); }
private:
    Adafruit_SSD1306 disp_;
};
}
#elif defined(SCREEN_TRANSPARENT_151_I2C)
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Wire.h>
namespace cyclops {
// Waveshare 1.51" Transparent OLED in I2C mode (128x64, SSD1309, addr 0x3C).
// For the 2-wire config: move the two solder resistors per the Waveshare wiki.
// I2C on XIAO D6/D7 (GPIO43/44), same as the 128x32 I2C driver, to avoid the
// button/wheel pins. Transparent-aware render (unlit rects are no-ops).
class Transparent151I2CScreen : public Screen {
public:
    Transparent151I2CScreen(int cs, int dc, int rst, int sck, int mosi, int miso, int rst_pin=-1,
                            uint8_t addr=0x3C, int sda=43, int scl=44)
        : disp_(128,64,&Wire,rst_pin), addr_(addr), sda_(sda), scl_(scl) { (void)cs;(void)dc;(void)rst;(void)sck;(void)mosi;(void)miso; }
    int w() const override { return 128; }
    int h() const override { return 64; }
    int char_cols() const override { return 21; }
    int text_rows() const override { return 8; }
    void begin() override {
        Wire.begin(sda_, scl_);
        disp_.begin(SSD1306_EXTERNALVCC, addr_);
        disp_.clearDisplay(); disp_.setTextSize(1); disp_.setTextColor(SSD1306_WHITE);
        disp_.dim(false);
    }
    void clear() override { disp_.clearDisplay(); }
    void set_ink(bool on) override { disp_.setTextColor(on?SSD1306_WHITE:SSD1306_BLACK); }
    void draw_text(int col,int row,const char* s) override { disp_.setCursor(col*6,row*8); disp_.print(s); }
    void draw_rect(int x,int y,int w,int h,bool on) override { if(on) disp_.fillRect(x,y,w,h,SSD1306_WHITE); }
    void draw_pixel(int x,int y,bool on=true) override { disp_.drawPixel(x,y,on?SSD1306_WHITE:SSD1306_BLACK); }
    void flush() override { disp_.display(); }
private:
    Adafruit_SSD1306 disp_;
    uint8_t addr_;
    int sda_, scl_;
};
}
#else
#error "Define one of SCREEN_ST7735 / SCREEN_128x64 / SCREEN_128x32 / SCREEN_128x32_I2C / SCREEN_TRANSPARENT_151 / SCREEN_TRANSPARENT_151_I2C"
#endif
#endif
