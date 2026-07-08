#include "ui.h"
#include <cstring>
#include <cstdio>

namespace cyclops {

void UiState::init() {
    disp.clear_all();
    note_count = 0; view_top = 0; sel = 0;
    recording = false; screen_on = true;
    render();
}

void UiState::add_note(const char* text) {
    if (note_count >= MAX_NOTES) {
        // drop oldest, shift up
        memmove(notes[0], notes[1], (MAX_NOTES - 1) * (DisplayModel::COLS + 1));
        note_count = MAX_NOTES - 1;
    }
    int n = 0;
    while (text[n] && n < DisplayModel::COLS) { notes[note_count][n] = text[n]; ++n; }
    notes[note_count][n] = '\0';
    note_count++;
    render();
}

void UiState::render() {
    disp.clear_all();
    char hdr[DisplayModel::COLS + 1];
    snprintf(hdr, sizeof(hdr), recording ? "[REC] notes:%d" : "notes:%d", note_count);
    disp.set_line(0, hdr);
    for (int i = 0; i < 3 && (view_top + i) < note_count; ++i) {
        int idx = view_top + i;
        const char* marker = (idx == sel) ? ">" : " ";
        char row[DisplayModel::COLS + 1];
        snprintf(row, sizeof(row), "%s%d %s", marker, idx + 1, notes[idx]);
        disp.set_line(i + 1, row);
    }
    if (!screen_on) disp.clear_all();
}

void UiState::on_wheel(int delta) {
    if (delta > 0) { // scroll down
        if (sel < note_count - 1) sel++;
    } else if (delta < 0) { // scroll up
        if (sel > 0) sel--;
    }
    // keep view window following selection
    if (sel < view_top) view_top = sel;
    if (sel > view_top + 2) view_top = sel - 2;
    render();
}

void UiState::on_btn_a() {
    // primary: toggle recording
    recording = !recording;
    render();
}

void UiState::on_btn_b() {
    // secondary: toggle screen (save power / privacy)
    screen_on = !screen_on;
    render();
}

void UiState::on_gesture(const char* name) {
    if (strcmp(name, "nod") == 0) {
        // nod = confirm/capture -> toggle record (same as btn_a)
        recording = !recording;
    } else if (strcmp(name, "shake") == 0) {
        // shake = dismiss/clear screen
        screen_on = false;
    }
    render();
}

const char* UiState::status_json(uint16_t batt_mv, bool charging) const {
    static char buf[80];
    snprintf(buf, sizeof(buf),
             "{\"type\":8,\"batt\":%u,\"charging\":%d,\"rec\":%d}",
             batt_mv, charging ? 1 : 0, recording ? 1 : 0);
    return buf;
}

} // namespace cyclops
