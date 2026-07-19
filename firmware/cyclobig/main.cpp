// CyclUno big-display board — the "128x128" half of the two-Arduino split.
//
// A second Arduino Uno whose only job is to render the CyclUno HUD on a large
// 1.44" ST7735 128x128 TFT. It holds no state: the controller board
// (cycluno/main.cpp) owns the HUD and streams the 4 rendered rows here over a
// one-way SoftwareSerial link.
//
// Wire frame per row (from the controller's OledSink):
//   [idx byte 0..3][text ASCII (no newline)]['\n']
// idx and the REC bell (0x07) can never be '\n', so the newline delimits.
//
// Wiring:
//   controller D4 (TX) -> this board D2 (RX)      GND <-> GND
//   ST7735: D11=MOSI D13=SCK  CS=D10 DC=D9 RST=D8 (RES may be a real pin here,
//   unlike the controller build which had none to spare).
//
// Build: pio run -e cyclobig  (see platformio.ini)
#include <Arduino.h>
#include <SoftwareSerial.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include "rowlink.h"

#define PIN_RX   2     // <- controller D4
#define PIN_TX   3     // unused (SoftwareSerial needs a TX pin)
#define LINK_BAUD 19200

#define PIN_TFT_CS  10
#define PIN_TFT_DC  9
#define PIN_TFT_RST 8

static SoftwareSerial link(PIN_RX, PIN_TX);           // RX, TX
static Adafruit_ST7735 tft(PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);

// The HUD is 4 rows (cycluno::ROWS). Render each big and full-width:
// setTextSize(1, 2) keeps all 21 columns (6 px wide -> 126 px) while doubling
// the height for legibility. 4 rows are spread down the 128 px panel.
static const uint8_t ROWS = 4;
static const uint8_t COLS = 21;
static const uint8_t ROW_H = 28;     // vertical pitch between rows
static const uint8_t ROW_Y0 = 12;    // top margin

static void draw_row(uint8_t idx, const char* text) {
    if (idx >= ROWS) return;
    int16_t y = ROW_Y0 + idx * ROW_H;
    tft.fillRect(0, y, 128, 18, ST77XX_BLACK);   // clear this row's band
    tft.setCursor(0, y);
    // The controller sends the REC bell (0x07) as a dot marker; GFX has no
    // glyph for it, so substitute a '*'.
    for (const char* p = text; *p && (p - text) < COLS; ++p)
        tft.write(*p == 0x07 ? '*' : *p);
}

void setup() {
    link.begin(LINK_BAUD);
    tft.initR(INITR_144GREENTAB);
    tft.setRotation(0);
    tft.fillScreen(ST77XX_BLACK);
    tft.setTextWrap(false);
    tft.setTextSize(1, 2);
    tft.setTextColor(ST77XX_WHITE, ST77XX_BLACK);
    tft.setCursor(0, ROW_Y0);
    tft.print("CyclUno display");
}

static void on_row(uint8_t idx, const char* text, void*) { draw_row(idx, text); }
static cycluno::RowLinkDecoder decoder(on_row);

void loop() {
    while (link.available()) {
        int b = link.read();
        if (b < 0) break;
        decoder.push((uint8_t)b);
    }
}
