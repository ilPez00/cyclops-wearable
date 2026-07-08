#ifndef CYCLOPS_SCREEN_H
#define CYCLOPS_SCREEN_H
// Resolution-agnostic screen abstraction. Drivers implement these.
#include "cyclops_shared.h"
#include <stdint.h>

namespace cyclops {

// Abstract screen. The default render() lays out the UI using the panel's
// own geometry (computed from w()/h()) so the same UiState renders on a
// 128x32 OLED, a 128x64 OLED, or a 128x128 TFT.
class Screen {
public:
    virtual ~Screen() {}
    virtual int w() const = 0;
    virtual int h() const = 0;
    virtual int char_cols() const = 0;   // visible columns at default font
    virtual int text_rows() const = 0;   // visible text rows at default font
    virtual void begin() = 0;
    virtual void clear() = 0;
    virtual void set_ink(bool on) = 0;    // true=fg (text), false=bg
    virtual void draw_text(int col, int row, const char* s) = 0;
    virtual void draw_rect(int x, int y, int w, int h, bool on) = 0;
    virtual void flush() = 0;

    // default layout: status bar (row 0) + note list
    void render_ui(const UiState& ui) {
        clear();
        int rows = text_rows();
        int cols = char_cols();
        // status bar
        char sb[32];
        snprintf(sb, sizeof(sb), "%s %s %dmV",
                 ui.recording ? "[REC]" : "    ",
                 ui.bt ? "BT" : "--",
                 ui.batt_mv / 1000);
        set_ink(true); draw_text(0, 0, sb);
        // note list starting at row 1
        int list_rows = rows - 1;
        for (int i = 0; i < list_rows && ui.top() + i < ui.count(); ++i) {
            int idx = ui.top() + i;
            const char* mark = (idx == ui.selected()) ? "#" : " ";
            char line[64];
            snprintf(line, sizeof(line), "%s%d %s", mark, idx + 1, ui.note(idx));
            // trim to cols
            if ((int)strlen(line) > cols) line[cols] = 0;
            draw_text(0, 1 + i, line);
        }
        flush();
    }
};

} // namespace cyclops
#endif
