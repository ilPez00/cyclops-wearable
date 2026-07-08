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
    void begin() override { tft_.initR(INITR_MINI160x80); tft_.setRotation(0); tft_.fillScreen(ST77XX_BLACK); tft_.setTextSize(1); tft_.setTextColor(0x07E0); }
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
#else
#error "Define one of SCREEN_ST7735 / SCREEN_128x64 / SCREEN_128x32"
#endif
#endif
