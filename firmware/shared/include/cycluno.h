// CyclUno — lean HUD state machine for the Arduino Uno dev unit.
//
// The full cyclops::Hud is ~1.9 KB of state; an ATmega328P has 2 KB of SRAM
// total, which is why the original Arduino target was retired. CyclUno is the
// same product idea at Uno scale: a handful of glanceable notes, a banner, a
// toast, wheel+two-button navigation, REC state — and nothing else.
//
//   sizeof(UnoHud) is gated < 400 bytes by test_cycluno.cpp.
//
// Rendering is abstracted as "N text rows" (RowSink) so the logic is
// host-testable; the Uno maps rows onto a text-mode SSD1306 (no framebuffer),
// the host test captures strings. Wire protocol is the shared v2 framing
// (cyclops_shared.h) over USB serial — same frames the XIAO speaks over BLE.
#pragma once
#include <stdint.h>
#include <string.h>
#include <stdio.h>

namespace cycluno {

static const uint8_t ROWS = 4;        // SSD1306 128x32-equivalent text rows
static const uint8_t COLS = 21;       // 128 px / 6 px font
static const uint8_t MAX_NOTES = 4;
static const uint8_t NOTE_LEN = COLS; // one row per note

// Actions emitted to the brain (mirror of the hud.h ACT ids used remotely).
static const uint8_t ACT_NOTES = 1;
static const uint8_t ACT_TRANSCRIBE_START = 2;
static const uint8_t ACT_AGENT = 14;

// Row renderer: firmware prints to the OLED, tests capture the strings.
struct RowSink {
    virtual void row(uint8_t idx, const char* text) = 0;
    virtual ~RowSink() {}
};

class UnoHud {
public:
    enum Mode : uint8_t { HOME = 0, NOTES = 1, MENU = 2 };

    // callbacks (all optional): command out, REC led, activity led
    void (*send_cmd)(uint8_t act) = nullptr;
    void (*on_rec_led)(bool on) = nullptr;

    void init() {
        mode_ = HOME; note_count_ = 0; note_sel_ = 0; menu_sel_ = 0;
        banner_[0] = 0; toast_[0] = 0; toast_ttl_ = 0; recording_ = false;
        dirty_ = true;
    }

    // ---- input ----------------------------------------------------------
    void on_wheel(int8_t dir) {
        if (mode_ == NOTES && note_count_) {
            note_sel_ = (uint8_t)((note_sel_ + note_count_ + dir) % note_count_);
        } else if (mode_ == MENU) {
            menu_sel_ = (uint8_t)((menu_sel_ + MENU_N + dir) % MENU_N);
        }
        dirty_ = true;
    }

    // A = select / act. HOME: toggle REC. MENU: run item. NOTES: back home.
    void on_btn_a() {
        if (mode_ == HOME) {
            recording_ = !recording_;
            if (on_rec_led) on_rec_led(recording_);
            if (send_cmd) send_cmd(ACT_TRANSCRIBE_START);
            toast(recording_ ? "REC on" : "REC off");
        } else if (mode_ == MENU) {
            switch (menu_sel_) {
                case 0: mode_ = NOTES; break;
                case 1: if (send_cmd) send_cmd(ACT_AGENT); toast("agent…"); break;
                case 2: mode_ = HOME; break;
            }
        } else {
            mode_ = HOME;
        }
        dirty_ = true;
    }

    // B = menu / back.
    void on_btn_b() {
        mode_ = (mode_ == HOME) ? MENU : HOME;
        dirty_ = true;
    }

    // ---- data in --------------------------------------------------------
    void add_note(const char* text) {
        // ring buffer: newest first, oldest dropped
        for (uint8_t i = MAX_NOTES - 1; i > 0; --i)
            memcpy(notes_[i], notes_[i - 1], NOTE_LEN + 1);
        copy_(notes_[0], text, NOTE_LEN);
        if (note_count_ < MAX_NOTES) ++note_count_;
        note_sel_ = 0;
        copy_(banner_, text, COLS);
        dirty_ = true;
    }

    void toast(const char* t) { copy_(toast_, t, COLS); toast_ttl_ = 4; dirty_ = true; }

    // Minimal DISPLAY_CMD / NOTE JSON: pull "data" or "text" string value.
    void apply_display_cmd(const char* json) {
        const char* key = strstr(json, "\"data\"");
        if (!key) key = strstr(json, "\"text\"");
        if (!key) return;
        const char* s = strchr(key + 6, ':');
        if (!s) return;
        ++s;
        while (*s == ' ') ++s;
        if (*s != '"') return;
        ++s;
        char out[NOTE_LEN + 1]; uint8_t i = 0;
        while (*s && *s != '"' && i < NOTE_LEN) out[i++] = *s++;
        out[i] = 0;
        if (i) add_note(out);
    }

    // 1 Hz housekeeping (toast decay). Returns true if a redraw is needed.
    bool tick() {
        if (toast_ttl_ > 0 && --toast_ttl_ == 0) { toast_[0] = 0; dirty_ = true; }
        bool d = dirty_; dirty_ = false; return d;
    }

    // ---- status out (MSG_STATUS payload) ---------------------------------
    int status_json(char* out, uint8_t cap) const {
        int n = snprintf(out, cap, "{\"t\":8,\"rec\":%d,\"mode\":\"%s\",\"notes\":%d}",
                         recording_ ? 1 : 0, mode_name(), note_count_);
        if (n < 0) return 0;
        return n >= cap ? cap - 1 : n;
    }

    // ---- render ----------------------------------------------------------
    void render(RowSink& sink) const {
        char line[COLS + 2];  // marker char + full-width text + NUL
        // row 0: mode + rec dot (+ toast overlay wins)
        if (toast_ttl_ > 0) {
            sink.row(0, toast_);
        } else {
            snprintf(line, sizeof(line), "%s%s", mode_name(), recording_ ? " \x07REC" : "");
            sink.row(0, line);
        }
        switch (mode_) {
            case HOME:
                sink.row(1, banner_[0] ? banner_ : "CyclUno ready");
                sink.row(2, note_count_ ? notes_[0] : "");
                sink.row(3, "A:rec  B:menu");
                break;
            case NOTES:
                for (uint8_t r = 0; r < 3; ++r) {
                    uint8_t idx = (uint8_t)(note_sel_ + r);
                    if (idx < note_count_) {
                        snprintf(line, sizeof(line), "%c%s", r == 0 ? '>' : ' ', notes_[idx]);
                        sink.row(1 + r, line);
                    } else {
                        sink.row(1 + r, r == 0 && !note_count_ ? "(no notes)" : "");
                    }
                }
                break;
            case MENU:
                for (uint8_t r = 0; r < MENU_N; ++r) {
                    snprintf(line, sizeof(line), "%c%s", r == menu_sel_ ? '>' : ' ', MENU_ITEMS[r]);
                    sink.row(1 + r, line);
                }
                break;
        }
    }

    Mode mode() const { return mode_; }
    bool recording() const { return recording_; }
    uint8_t note_count() const { return note_count_; }
    uint8_t note_sel() const { return note_sel_; }

private:
    static const uint8_t MENU_N = 3;
    static const char* const MENU_ITEMS[MENU_N];

    const char* mode_name() const {
        return mode_ == HOME ? "HOME" : (mode_ == NOTES ? "NOTES" : "MENU");
    }

    static void copy_(char* dst, const char* src, uint8_t cap) {
        uint8_t i = 0;
        while (src[i] && i < cap) { dst[i] = src[i]; ++i; }
        dst[i] = 0;
    }

    Mode mode_ = HOME;
    char notes_[MAX_NOTES][NOTE_LEN + 1];
    uint8_t note_count_ = 0, note_sel_ = 0, menu_sel_ = 0;
    char banner_[COLS + 1];
    char toast_[COLS + 1];
    uint8_t toast_ttl_ = 0;
    bool recording_ = false;
    bool dirty_ = true;
};

inline const char* const UnoHud::MENU_ITEMS[UnoHud::MENU_N] = {
    "Notes", "Ask agent", "Home"
};

}  // namespace cycluno
