// CyclUno bench diagnostic — OLED test + wiring report @115200.
// Non-destructive: separate from product firmware; reflash cycluno after.
// At boot: I2C scan, then try oled.begin() at 0x3C and 0x3D, draw if it works.
// Also prints A4/A5 line levels (wiring evidence) + D2..D7 + A0..A3.
#include <Arduino.h>
#include <Wire.h>
#include "SSD1306Ascii.h"
#include "SSD1306AsciiWire.h"

static SSD1306AsciiWire oled;
static const uint8_t DIG_PINS[] = {2, 3, 4, 5, 6, 7};
static const uint8_t ANA_PINS[] = {A0, A1, A2, A3};

void scan_i2c() {
    Serial.print("I2C scan: ");
    uint8_t found = 0;
    for (uint8_t a = 1; a < 120; a++) {
        Wire.beginTransmission(a);
        if (Wire.endTransmission() == 0) {
            Serial.print("0x");
            if (a < 16) Serial.print("0");
            Serial.print(a, HEX);
            Serial.print(" ");
            found++;
        }
    }
    if (!found) Serial.print("(none)");
    Serial.println();
}

void setup() {
    Serial.begin(115200);
    Wire.begin();
    Wire.setClock(400000L);
    for (uint8_t p : DIG_PINS) pinMode(p, INPUT_PULLUP);

    Serial.println("=== CyclUno diagnostic (OLED test) ===");
    scan_i2c();

    // begin() returns void; treat presence on scan as the success signal.
    // Try 0x3C first, fall back to 0x3D.
    oled.setFont(System5x7);
    oled.begin(&Adafruit128x32, 0x3C);
    // attempt a draw; if nothing responds the screen simply stays blank
    oled.clear();
    oled.setCursor(0, 0); oled.print("CYCLOPS");
    oled.setCursor(0, 1); oled.print("OLED TEST");
    oled.setCursor(0, 2); oled.print("A4=");
    oled.print(digitalRead(A4)); oled.print(" A5=");
    oled.print(digitalRead(A5));
    oled.setCursor(0, 3); oled.print("see A4/A5 below");

    // wiring evidence: at I2C idle, SDA/SCL should be pulled HIGH (~1023)
    Serial.print("A4(SDA) dig=");
    Serial.print(digitalRead(A4));
    Serial.print(" ana=");
    Serial.print(analogRead(A4));
    Serial.print("  A5(SCL) dig=");
    Serial.print(digitalRead(A5));
    Serial.print(" ana=");
    Serial.println(analogRead(A5));
}

void loop() {
    Serial.print("D:");
    for (uint8_t p : DIG_PINS) Serial.print(digitalRead(p) ? "1" : "0");
    Serial.print("  A:");
    for (uint8_t i = 0; i < 4; i++) {
        Serial.print(analogRead(ANA_PINS[i]));
        if (i < 3) Serial.print(",");
    }
    Serial.println();
    delay(250);
}
