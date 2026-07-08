#ifndef CYCLOPS_HUD_H
#define CYCLOPS_HUD_H
// HUD + menu system (resolution-agnostic). Thin client: sends MSG_CMD, renders
// results streamed back as DISPLAY_CMD / HUD_FRAME. Host-testable, no display dep.
#include "cyclops_shared.h"
#include <stdint.h>

namespace cyclops {

enum Mode : uint8_t {
    HOME=0, MENU, NOTES, NOTE_DETAIL, TRANSCRIBE, TRANSLATE,
    HEALTH, TELEPROMPTER, NAV, CAMERA, IMAGE_ANALYSIS, SSH, SETTINGS, CONFIRM
};

// Action ids sent to the brain via MSG_CMD
enum Action : uint8_t {
    ACT_NOTES=1, ACT_TRANSCRIBE_START=2, ACT_TRANSLATE=3, ACT_HEALTH=4,
    ACT_NAV=5, ACT_TELEPROMPTER=6, ACT_CAMERA=7, ACT_IMAGE_ANALYSIS=8,
    ACT_SSH=9, ACT_SETTINGS=10, ACT_CONFIRM_YES=11, ACT_CONFIRM_NO=12,
    ACT_SELECT=13
};

struct Hud {
    static const int MAX_NOTES = 12;
    static const int NCOLS = 23;
    static const int DETAIL = 256;
    static const int STACK = 5;

    char notes[MAX_NOTES][NCOLS+1];
    int note_count = 0;
    int note_sel = 0;

    Mode stack[STACK];
    int sp = 0;                  // top = stack[sp-1]
    int menu_sel = 0;
    const char* menu_items[11] = {
        "Notes","Transcribe","Translate","Health","Navigate",
        "Teleprompter","Camera","ImageAnalyze","SSH","Settings","Back"
    };
    int menu_n = 11;

    char detail[DETAIL];
    int detail_len = 0;
    int scroll_off = 0;

    int hr = 0, spo2 = 0, ring_batt = 0, bead_batt = 0;
    int nav_dist = 0, nav_head = 0; char nav_label[24] = "";
    int tele_page = 0;
    char confirm_prompt[32] = ""; uint8_t confirm_action = 0;
    int rec_secs = 0;
    uint32_t clock = 0;
    bool recording = false, screen_on = true, bt = false;

    // callbacks: send a command byte to the brain (BLE/USB). Set by main.
    void (*send_cmd)(uint8_t act, const char* arg) = nullptr;
    int status_json(char* out, size_t cap) const {
        return snprintf(out, cap, "{\"t\":8,\"batt\":%u,\"chg\":%d,\"rec\":%d,\"bt\":%d,\"hr\":%d}",
                        (unsigned)bead_batt, 0, recording?1:0, bt?1:0, hr);
    }

    void init() { sp = 0; push(HOME); note_count = 0; menu_sel = 0; }
    void push(Mode m) { if (sp < STACK) stack[sp++] = m; }
    Mode top() const { return sp > 0 ? stack[sp-1] : HOME; }
    void pop() { if (sp > 1) --sp; }
    void home() { sp = 0; push(HOME); }

    void add_note(const char* t) {
        if (note_count >= MAX_NOTES) { memmove(notes[0], notes[1], (MAX_NOTES-1)*(NCOLS+1)); note_count = MAX_NOTES-1; }
        int n = 0; while (t[n] && n < NCOLS) { notes[note_count][n] = t[n]; ++n; }
        notes[note_count][n] = 0; note_count++;
        if (top() == NOTES || top() == HOME) {} // list reflects automatically
    }
    void set_detail(const char* t) {
        detail_len = 0; while (t && t[detail_len] && detail_len < DETAIL-1) { detail[detail_len] = t[detail_len]; ++detail_len; }
        detail[detail_len] = 0; scroll_off = 0;
    }
    void request_confirm(const char* prompt, uint8_t action) {
        strncpy(confirm_prompt, prompt ? prompt : "", 31); confirm_prompt[31] = 0;
        confirm_action = action; push(CONFIRM);
    }

    // ---- input handlers ----
    void on_wheel(int d) {
        Mode m = top();
        if (m == MENU) menu_sel = clamp(menu_sel + d, 0, menu_n-1);
        else if (m == NOTES) note_sel = clamp(note_sel + d, 0, note_count-1);
        else if (m == NOTE_DETAIL || m == TRANSLATE || m == IMAGE_ANALYSIS || m == SSH || m == CAMERA)
            scroll_off = clamp(scroll_off + d*16, 0, detail_len);
        else if (m == TELEPROMPTER) tele_page = clamp(tele_page + d, 0, 999);
    }
    void on_select() {
        Mode m = top();
        if (m == MENU) {
            const char* act = menu_items[menu_sel];
            if (!strcmp(act, "Back")) pop();
            else if (!strcmp(act, "Notes")) push(NOTES);
            else if (!strcmp(act, "Transcribe")) { recording = true; rec_secs = 0; push(TRANSCRIBE); cmd(ACT_TRANSCRIBE_START); }
            else if (!strcmp(act, "Translate")) { set_detail(note_count ? notes[note_sel] : ""); push(TRANSLATE); cmd(ACT_TRANSLATE, note_count ? notes[note_sel] : ""); }
            else if (!strcmp(act, "Health")) push(HEALTH);
            else if (!strcmp(act, "Navigate")) push(NAV);
            else if (!strcmp(act, "Teleprompter")) { tele_page = 0; push(TELEPROMPTER); cmd(ACT_TELEPROMPTER); }
            else if (!strcmp(act, "Camera")) { push(CAMERA); cmd(ACT_CAMERA); }
            else if (!strcmp(act, "ImageAnalyze")) { push(IMAGE_ANALYSIS); cmd(ACT_IMAGE_ANALYSIS); }
            else if (!strcmp(act, "SSH")) { push(SSH); cmd(ACT_SSH); }
            else if (!strcmp(act, "Settings")) push(SETTINGS);
        } else if (m == NOTES) {
            if (note_count) { set_detail(notes[note_sel]); push(NOTE_DETAIL); }
        } else if (m == CONFIRM) {
            cmd(ACT_CONFIRM_YES); pop();
        } else if (m == HOME) {
            push(MENU);
        }
    }
    void on_long_back() { pop(); }
    void on_back_gesture() { pop(); }
    void on_nod() { recording = !recording; }   // quick capture toggle

    void set_health(int h, int s, int rb, int bb) { hr = h; spo2 = s; ring_batt = rb; bead_batt = bb; }
    void set_nav(int dist_m, int head, const char* label) { nav_dist = dist_m; nav_head = head; strncpy(nav_label, label?label:"",23); nav_label[23]=0; }
    void set_tele(const char* /*full*/, int page) { tele_page = page; }
    void tick_sec() { if (recording) ++rec_secs; }

    // ---- render to a Screen ----
    template<typename S>
    void render(S& scr) {
        scr.clear();
        if (!screen_on) { scr.flush(); return; }
        int rows = scr.text_rows();
        int cols = scr.char_cols();
        // status bar row 0
        char sb[32];
        snprintf(sb, sizeof(sb), "%02u:%02u %s %s %dmV",
                 (clock/3600)%24, (clock/60)%60,
                 recording ? "REC" : "   ", bt ? "BT" : "  ", bead_batt/1000);
        scr.set_ink(true); scr.draw_text(0, 0, sb);

        Mode m = top();
        if (m == HOME) {
            scr.draw_text(0, 1, "Cyclops");
            scr.draw_text(0, 2, "wheel:menu  A:open");
        } else if (m == MENU) {
            for (int i = 0; i < rows-1 && i < menu_n; ++i) {
                const char* mk = (i == menu_sel) ? ">" : " ";
                char ln[32]; snprintf(ln, sizeof(ln), "%s%s", mk, menu_items[i]);
                trim(ln, cols); scr.draw_text(0, 1+i, ln);
            }
        } else if (m == NOTES) {
            for (int i = 0; i < rows-1 && i < note_count; ++i) {
                const char* mk = (i == note_sel) ? ">" : " ";
                char ln[32]; snprintf(ln, sizeof(ln), "%s%d %s", mk, i+1, notes[i]);
                trim(ln, cols); scr.draw_text(0, 1+i, ln);
            }
        } else if (m == NOTE_DETAIL || m == TRANSLATE || m == IMAGE_ANALYSIS || m == SSH || m == CAMERA) {
            draw_detail(scr, rows, cols);
        } else if (m == TRANSCRIBE) {
            char ln[32]; snprintf(ln, sizeof(ln), "REC %d:%02d", rec_secs/60, rec_secs%60);
            scr.draw_text(0, 1, ln);
            draw_detail(scr, rows, cols);
        } else if (m == HEALTH) {
            char ln[32];
            snprintf(ln, sizeof(ln), "HR %d  SpO2 %d%%", hr, spo2); scr.draw_text(0,1,ln);
            snprintf(ln, sizeof(ln), "ring %dmV bead %dmV", ring_batt, bead_batt); scr.draw_text(0,2,ln);
        } else if (m == NAV) {
            char ln[32]; snprintf(ln, sizeof(ln), "%dm %ddeg", nav_dist, nav_head); scr.draw_text(0,1,ln);
            scr.draw_text(0,2,nav_label);
        } else if (m == TELEPROMPTER) {
            char ln[32]; snprintf(ln, sizeof(ln), "TELE %d", tele_page); scr.draw_text(0,1,ln);
            draw_detail(scr, rows, cols);
        } else if (m == SETTINGS) {
            scr.draw_text(0,1,"Settings");
            scr.draw_text(0,2,"A:back");
        } else if (m == CONFIRM) {
            scr.draw_text(0,1,confirm_prompt);
            scr.draw_text(0,2,"A:yes  B:no");
        }
        scr.flush();
    }

private:
    static int clamp(int v, int lo, int hi) { if (v<lo) v=lo; if (v>hi) v=hi; return v; }
    static void trim(char* s, int cols) { if ((int)strlen(s) > cols) s[cols]=0; }
    template<typename S>
    void draw_detail(S& scr, int rows, int cols) {
        int p = scroll_off;
        for (int r = 1; r < rows; ++r) {
            if (p >= detail_len) break;
            char ln[64];
            int i = 0;
            while (p < detail_len && i < cols && detail[p] != '\n') ln[i++] = detail[p++];
            if (p < detail_len && detail[p] == '\n') ++p;
            ln[i] = 0;
            scr.draw_text(0, r, ln);
        }
    }
    void cmd(uint8_t a, const char* arg = nullptr) { if (send_cmd) send_cmd(a, arg ? arg : ""); }
};

} // namespace cyclops
#endif
