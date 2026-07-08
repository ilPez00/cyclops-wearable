#ifndef CYCLOPS_UI_H
#define CYCLOPS_UI_H
#include "protocol.h"
#include <cstdint>

namespace cyclops {

// UI state machine for the HUD: manages what's on screen and reacts to inputs.
// Hardware-agnostic: inputs are fed as events, output is the DisplayModel.
struct UiState {
    DisplayModel disp;
    static const int MAX_NOTES = 8;
    char notes[MAX_NOTES][DisplayModel::COLS + 1];
    int note_count = 0;
    int view_top = 0;     // first note row shown
    int sel = 0;          // selected note index
    bool recording = false;
    bool screen_on = true;

    void init();
    // Input events
    void on_wheel(int delta);            // -1 / +1 ticks
    void on_btn_a();                     // primary: toggle record / select
    void on_btn_b();                     // secondary: screen toggle / back
    void on_gesture(const char* name);   // "nod", "shake"
    // Brain -> device
    void add_note(const char* text);
    void apply_display_cmd(const char* json); // parse minimal DISPLAY_CMD
    // Render current frame into disp (call each tick)
    void render();
    const char* status_json(uint16_t batt_mv, bool charging) const;
};

} // namespace cyclops
#endif
