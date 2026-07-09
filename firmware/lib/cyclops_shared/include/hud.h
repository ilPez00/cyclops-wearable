#ifndef CYCLOPS_HUD_H
#define CYCLOPS_HUD_H
// HUD + menu system (resolution-agnostic). Thin client: sends MSG_CMD, renders
// results streamed back as DISPLAY_CMD / HUD_FRAME. Host-testable, no display dep.
//
// UX model (XIAO ESP32-S3 Sense + round/e-ink screen + scrollwheel + buttons):
//   HOME  -> glanceable banner (the AI's last line) + status. wheel opens MENU.
//   AGENT -> ask the brain/agent; streams the answer into DETAIL (the "answer" view).
//   Every view shows a 1-line mode breadcrumb in the status bar and transient toasts.
#include "cyclops_shared.h"
#include <stdint.h>
#include <stdlib.h>  // AVR/Arduino-safe; declares atoi

namespace cyclops {

enum Mode : uint8_t {
    HOME=0, MENU, NOTES, NOTE_DETAIL, TRANSCRIBE, TRANSLATE,
    HEALTH, TELEPROMPTER, NAV, CAMERA, IMAGE_ANALYSIS, SSH, SETTINGS, CONFIRM,
    AGENT
};

// Action ids sent to the brain via MSG_CMD
enum Action : uint8_t {
    ACT_NOTES=1, ACT_TRANSCRIBE_START=2, ACT_TRANSLATE=3, ACT_HEALTH=4,
    ACT_NAV=5, ACT_TELEPROMPTER=6, ACT_CAMERA=7, ACT_IMAGE_ANALYSIS=8,
    ACT_SSH=9, ACT_SETTINGS=10, ACT_CONFIRM_YES=11, ACT_CONFIRM_NO=12,
    ACT_SELECT=13, ACT_AGENT=14, ACT_AGENT_ABORT=15
};

struct Hud {
    static const int MAX_NOTES = 12;
    static const int NCOLS = 23;
    static const int DETAIL = 1024;     // agent answers need room
    static const int HUD_LINE = 96;     // glanceable banner (Omi/G2 style)
    static const int TOAST = 48;
    static const int STACK = 6;

    char notes[MAX_NOTES][NCOLS+1];
    int note_count = 0;
    int note_sel = 0;

    Mode stack[STACK];
    int sp = 0;                  // top = stack[sp-1]
    int menu_sel = 0;
    const char* menu_items[12] = {
        "Notes","Agent","Transcribe","Translate","Health","Navigate",
        "Teleprompter","Camera","ImageAnalyze","SSH","Settings","Back"
    };
    int menu_n = 12;

    char detail[DETAIL];
    int detail_len = 0;
    int scroll_off = 0;

    char hud_line[HUD_LINE];     // glanceable banner, rendered on HOME + footer
    int hud_len = 0;

    char toast_msg[TOAST];       // transient status ("sent", "thinking…")
    int toast_ttl = 0;       // seconds remaining

    int progress = 0;            // agent/tool progress 0..100 (bar)
    char steps[8][12];       // tool-step ticks (·device ·web …)
    int step_n = 0;

    int sleep_after = 8;     // idle seconds before auto-sleep (OLED burn-in)
    int idle = 0;            // idle counter since last input

    int hr = 0, spo2 = 0, ring_batt = 0, bead_batt = 0;
    int nav_dist = 0, nav_head = 0; char nav_label[24] = "";
    int tele_page = 0;
    char confirm_prompt[32] = ""; uint8_t confirm_action = 0;
    int rec_secs = 0;
    uint32_t clock = 0;
    bool recording = false, screen_on = true, bt = false, consent = true;

    // callbacks: send a command byte to the brain (BLE/USB). Set by main.
    void (*send_cmd)(uint8_t act, const char* arg) = nullptr;
    void (*on_transcribe_toggle)() = nullptr;  // device starts/stops mic capture
    void (*on_agent_request)(const char* prompt) = nullptr;  // host streams answer via set_agent()
    int status_json(char* out, size_t cap) const {
        return snprintf(out, cap, "{\"t\":8,\"batt\":%u,\"chg\":%d,\"rec\":%d,\"bt\":%d,\"hr\":%d}",
                        (unsigned)bead_batt, 0, recording?1:0, bt?1:0, hr);
    }

    void init() { sp = 0; push(HOME); note_count = 0; menu_sel = 0; hud_len = 0; toast_ttl = 0; }
    void push(Mode m) { if (sp < STACK) stack[sp++] = m; }
    Mode top() const { return sp > 0 ? stack[sp-1] : HOME; }
    void pop() { if (sp > 1) --sp; }
    void home() { sp = 0; push(HOME); }

    void add_note(const char* t) {
        if (note_count >= MAX_NOTES) { memmove(notes[0], notes[1], (MAX_NOTES-1)*(NCOLS+1)); note_count = MAX_NOTES-1; }
        int n = 0; while (t[n] && n < NCOLS) { notes[note_count][n] = t[n]; ++n; }
        notes[note_count][n] = 0; note_count++;
    }
    void set_detail(const char* t) {
        detail_len = 0; while (t && t[detail_len] && detail_len < DETAIL-1) { detail[detail_len] = t[detail_len]; ++detail_len; }
        detail[detail_len] = 0; scroll_off = 0;
    }
    // Push a glanceable banner line (the AI's last words). Shown on HOME + footer.
    void set_hud(const char* t) {
        hud_len = 0; while (t && t[hud_len] && hud_len < HUD_LINE-1) { hud_line[hud_len] = t[hud_len]; ++hud_len; }
        hud_line[hud_len] = 0;
    }
    // Stream an agent answer (keeps appending, capped at DETAIL).
    void append_agent(const char* chunk) {
        while (chunk && *chunk && detail_len < DETAIL-1) { detail[detail_len++] = *chunk++; }
        detail[detail_len] = 0;
    }
    void toast(const char* msg, int ttl = 2) {
        int n = 0; while (msg && msg[n] && n < TOAST-1) { toast_msg[n] = msg[n]; ++n; }
        toast_msg[n] = 0; toast_ttl = ttl;
    }
    void wake() { idle = 0; screen_on = true; }
    void add_step(const char* tool) {
        if (step_n >= 8) return;
        int n = 0; while (tool && tool[n] && n < 11) { steps[step_n][n] = tool[n]; ++n; }
        steps[step_n][n] = 0; step_n++;
    }
    void set_progress(int p) { progress = clamp(p, 0, 100); }
    void set_consent(bool c) { consent = c; }
    // Parse a DISPLAY_CMD JSON from the brain and update Hud state.
    // Handles {"kind":"progress","p":NN}, {"kind":"step","tool":"x"},
    // and default {"kind":"text"/"data"/"text":...} -> add_note.
    void apply_display_cmd(const char* json) {
        const char* k = strstr(json, "\"kind\"");
        if (k) {
            if (strstr(k, "\"progress\"")) {
                const char* p = strstr(k, "\"p\":");
                if (p) set_progress(atoi(p + 4));
                return;
            }
            if (strstr(k, "\"step\"")) {
                const char* t = strstr(k, "\"tool\"");
                if (t) { const char* s = strchr(t, ':'); if (s) { ++s; while (*s==' '||*s=='\"') ++s;
                    char buf[12]; int i=0; while (*s && *s!='\"' && *s!=',' && i<11) buf[i++]=*s++; buf[i]=0; if (buf[0]) add_step(buf); } }
                return;
            }
            if (strstr(k, "\"consent\"")) {
                const char* v = strstr(k, "\"on\"");
                set_consent(v ? atoi(v + 5) != 0 : true);
                return;
            }
        }
        // default: treat as a text line -> note
        const char* key = strstr(json, "\"data\"") ? "\"data\"" : "\"text\"";
        const char* t = strstr(json, key);
        if (!t) return;
        const char* s = strchr(t, ':'); if (!s) return; ++s;
        while (*s==' ') ++s;
        if (*s=='"') { ++s; char out[64]; int i=0; while (*s && *s!='"' && i<63) out[i++]=*s++; out[i]=0; add_note(out); }
    }
    // Advance 1s of wall clock (REC timer + toast + idle sleep).
    void tick_sec() {
        if (recording) ++rec_secs;
        if (toast_ttl > 0) --toast_ttl;
        if (screen_on) { if (++idle >= sleep_after) screen_on = false; }
    }

    void request_confirm(const char* prompt, uint8_t action) {
        strncpy(confirm_prompt, prompt ? prompt : "", 31); confirm_prompt[31] = 0;
        confirm_action = action; push(CONFIRM);
    }

    // ---- input handlers ----
    void on_wheel(int d) {
        wake();
        Mode m = top();
        if (m == MENU) menu_sel = clamp(menu_sel + d, 0, menu_n-1);
        else if (m == NOTES) note_sel = clamp(note_sel + d, 0, note_count-1);
        else if (m == NOTE_DETAIL || m == TRANSLATE || m == IMAGE_ANALYSIS || m == SSH || m == CAMERA || m == AGENT)
            scroll_off = clamp(scroll_off + d*16, 0, detail_len);
        else if (m == TELEPROMPTER) tele_page = clamp(tele_page + d, 0, 999);
    }
    void on_select() {
        wake();
        Mode m = top();
        if (m == MENU) {
            const char* act = menu_items[menu_sel];
            if (!strcmp(act, "Back")) pop();
            else if (!strcmp(act, "Notes")) push(NOTES);
            else if (!strcmp(act, "Agent")) { set_detail(""); scroll_off = 0; push(AGENT);
                                               toast("ask via app/voice", 2); }
            else if (!strcmp(act, "Transcribe")) { if (!consent) { toast("consent off", 2); return; } recording = true; rec_secs = 0; push(TRANSCRIBE); cmd(ACT_TRANSCRIBE_START); if (on_transcribe_toggle) on_transcribe_toggle(); }
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
        } else if (m == AGENT) {
            // Entering AGENT from the menu opens a fresh query; a real prompt is
            // delivered by the host via on_agent_request() / set_hud().
            toast("agent ready", 2);
        } else if (m == CONFIRM) {
            cmd(ACT_CONFIRM_YES); pop();
        } else if (m == HOME) {
            push(MENU);
        }
    }
    void on_long_back() {
        wake();
        // stop any capture/agent before leaving
        if (top() == TRANSCRIBE && recording) { recording = false; if (on_transcribe_toggle) on_transcribe_toggle(); cmd(ACT_TRANSCRIBE_START); }
        if (top() == AGENT) cmd(ACT_AGENT_ABORT);
        pop();
    }
    // Short cancel (BTN_B / second button). Declines a confirm, else backs out one level.
    void on_cancel() {
        wake();
        Mode m = top();
        if (m == CONFIRM) { cmd(ACT_CONFIRM_NO); pop(); }
        else if (m != HOME) { pop(); }
        else { /* on HOME, cancel is a no-op */ }
    }
    void on_back_gesture() { on_long_back(); }
    // Ring/glasses gesture dispatch (codes mirror protocol_v2.GEST):
    // 1 up, 2 down, 3 select, 4 back, 5 nod, 6 home.
    void on_gesture(int code) {
        wake();
        switch (code) {
            case 1: on_wheel(-1); break;   // up
            case 2: on_wheel(1);  break;   // down
            case 3: on_select();  break;
            case 4: on_long_back(); break;
            case 5: on_nod();     break;
            case 6: home();       break;
            default: break;
        }
    }
    void on_nod() { wake(); if (!recording && !consent) { toast("consent off", 2); return; } recording = !recording; if (recording) { rec_secs = 0; cmd(ACT_TRANSCRIBE_START); if (on_transcribe_toggle) on_transcribe_toggle(); } }   // quick capture toggle

    void set_health(int h, int s, int rb, int bb) { hr = h; spo2 = s; ring_batt = rb; bead_batt = bb; }
    // Incoming MSG_HEALTH_SAMPLE (phone->wearable relay, P2-C): parse
    // "t=,hr=,spo2=,sl=,batt=" and apply. We only take hr/spo2/ring_batt.
    void on_health_sample(const char* p) {
        auto atoi_k = [&](const char* k) -> int {
            const char* v = strstr(p, k); if (!v) return -1;
            return atoi(v + strlen(k));
        };
        int h = atoi_k("hr="); if (h > 0) hr = h;
        int s = atoi_k("spo2="); if (s > 0) spo2 = s;
        int b = atoi_k("batt="); if (b > 0) ring_batt = b;
    }
    void set_nav(int dist_m, int head, const char* label) { nav_dist = dist_m; nav_head = head; strncpy(nav_label, label?label:"",23); nav_label[23]=0; }
    void set_tele(const char* /*full*/, int page) { tele_page = page; }

    // Ask the agent (from app/voice). Host callback streams the answer back.
    void agent_ask(const char* prompt) {
        wake();
        set_detail(""); scroll_off = 0; step_n = 0; progress = 0;
        if (top() != AGENT) push(AGENT);
        toast("thinking…", 2);
        if (on_agent_request) on_agent_request(prompt ? prompt : "");
    }

    // ---- render to a Screen ----
    template<typename S>
    void render(S& scr) {
        scr.clear();
        if (!screen_on) { scr.flush(); return; }
        int rows = scr.text_rows();
        int cols = scr.char_cols();
        // status bar row 0: clock + flags + mode breadcrumb
        char sb[32];
        const char* md = mode_name(top());
        snprintf(sb, sizeof(sb), "%02u:%02u %s%s%s %s",
                 (clock/3600)%24, (clock/60)%60,
                 recording ? "REC " : "", bt ? "BT " : "", consent ? "" : "X ", md);
        scr.set_ink(true); scr.draw_text(0, 0, sb);

        Mode m = top();
        int body = 1;
        if (m == HOME) {
            // glanceable banner (the AI's last line) in larger type on capable panels
            if (hud_len) { scr.text_size(2); scr.draw_text(0, body, trunc(hud_line, cols/2)); scr.text_size(1); body++; }
            else { scr.draw_text(0, body, "Cyclops ready"); body++; }
            char ln[32];
            snprintf(ln, sizeof(ln), "%dmV %d notes %s", (bead_batt>0?bead_batt:ring_batt),
                     note_count, recording ? "REC" : "");
            trim(ln, cols); scr.draw_text(0, body, ln); body++;
            scr.draw_text(0, body, "wheel:menu"); body++;
        } else if (m == MENU) {
            for (int i = 0; i < rows-1 && i < menu_n; ++i) {
                const char* mk = (i == menu_sel) ? ">" : " ";
                char ln[32]; snprintf(ln, sizeof(ln), "%s%s", mk, menu_items[i]);
                trim(ln, cols); scr.draw_text(0, body+i, ln);
            }
        } else if (m == NOTES) {
            for (int i = 0; i < rows-1 && i < note_count; ++i) {
                const char* mk = (i == note_sel) ? ">" : " ";
                char ln[32]; snprintf(ln, sizeof(ln), "%s%d %s", mk, i+1, notes[i]);
                trim(ln, cols); scr.draw_text(0, body+i, ln);
            }
        } else if (m == NOTE_DETAIL || m == TRANSLATE || m == IMAGE_ANALYSIS || m == SSH || m == CAMERA) {
            draw_detail(scr, rows, cols, body);
        } else if (m == AGENT) {
            draw_detail(scr, rows, cols, body);
            // progress bar (only if rows allow) + tool-step ticks
            if (rows >= 6) {
                int bar_row = rows - 2;
                int filled = (progress * (cols-2)) / 100;
                char bar[32]; int bi = 0; bar[bi++] = '[';
                for (int i = 0; i < cols-2; ++i) bar[bi++] = (i < filled) ? '#' : '-';
                bar[bi++] = ']'; bar[bi] = 0; trim(bar, cols);
                scr.draw_text(0, bar_row, bar);
                // steps: last up-to-4 ticks joined
                char st[32]; int si = 0;
                int start = step_n > 4 ? step_n - 4 : 0;
                for (int i = start; i < step_n; ++i) {
                    si += snprintf(st + si, sizeof(st) - si, "\xB7%s ", steps[i]);
                }
                trim(st, cols); scr.draw_text(0, rows-1, st);
            }
        } else if (m == TRANSCRIBE) {
            char ln[32]; snprintf(ln, sizeof(ln), "REC %d:%02d", rec_secs/60, rec_secs%60);
            scr.draw_text(0, body, ln); body++;
            draw_detail(scr, rows, cols, body);
        } else if (m == HEALTH) {
            char ln[32];
            snprintf(ln, sizeof(ln), "HR %d  SpO2 %d%%", hr, spo2); scr.draw_text(0,body,ln);
            snprintf(ln, sizeof(ln), "ring %dmV bead %dmV", ring_batt, bead_batt); scr.draw_text(0,body+1,ln);
        } else if (m == NAV) {
            char ln[32]; snprintf(ln, sizeof(ln), "%s %dm", nav_arrow(nav_head), nav_dist); scr.draw_text(0,body,ln);
            scr.draw_text(0,body+1,nav_label);
        } else if (m == TELEPROMPTER) {
            char ln[32]; snprintf(ln, sizeof(ln), "TELE %d", tele_page); scr.draw_text(0,body,ln);
            draw_detail(scr, rows, cols, body+1);
        } else if (m == SETTINGS) {
            scr.draw_text(0,body,"Settings");
            scr.draw_text(0,body+1,"A:back");
        } else if (m == CONFIRM) {
            scr.draw_text(0,body,confirm_prompt);
            scr.draw_text(0,body+1,"A:yes  B:no");
        }
        // transient toast overlay (last row) wins over body content
        if (toast_ttl > 0) {
            char ln[TOAST]; snprintf(ln, sizeof(ln), "* %s", toast_msg);
            trim(ln, cols); scr.draw_text(0, rows-1, ln);
        }
        scr.flush();
    }

private:
    static int clamp(int v, int lo, int hi) { if (v<lo) v=lo; if (v>hi) v=hi; return v; }
    static void trim(char* s, int cols) { if ((int)strlen(s) > cols) s[cols]=0; }
    static const char* trunc(const char* s, int cols) { static char b[128]; int n=0; while (s[n] && n<cols && n<127) { b[n]=s[n]; ++n; } b[n]=0; return b; }
    static const char* nav_arrow(int deg) {
        // 8-point compass arrow from heading (0=N). Pure glyph, BOM-free.
        static const char* arrows[8] = {"\x18","\x1E","\x1B","\x1F","\x19","\x11","\x1A","\x17"};
        int i = ((deg % 360) + 360) % 360;
        return arrows[(i + 22) / 45 % 8];
    }
    static const char* mode_name(Mode m) {
        switch (m) {
            case HOME: return "HOME"; case MENU: return "MENU"; case NOTES: return "NOTES";
            case NOTE_DETAIL: return "NOTE"; case TRANSCRIBE: return "REC"; case TRANSLATE: return "TR";
            case HEALTH: return "HLTH"; case TELEPROMPTER: return "TELE"; case NAV: return "NAV";
            case CAMERA: return "CAM"; case IMAGE_ANALYSIS: return "IMG"; case SSH: return "SSH";
            case SETTINGS: return "CFG"; case CONFIRM: return "?"; case AGENT: return "AGENT";
        }
        return "";
    }
    template<typename S>
    void draw_detail(S& scr, int rows, int cols, int start_row) {
        // word-aware wrap (no mid-word splits) for agent answers on tiny panels
        int r = start_row;
        int p = scroll_off;
        while (p < detail_len && r < rows) {
            // find line end: up to cols chars, break at last space before cols
            int line_end = p;
            int last_space = -1;
            int n = 0;
            while (p + n < detail_len && n < cols) {
                char c = detail[p + n];
                if (c == '\n') { line_end = p + n; break; }
                if (c == ' ') last_space = p + n;
                line_end = p + n + 1;
                ++n;
            }
            if (line_end == p + n) { /* hit cols */
                if (last_space > p && detail[p + n] != ' ') line_end = last_space + 1;
            }
            char ln[64];
            int i = 0;
            while (p < line_end && detail[p] != '\n' && i < 63) ln[i++] = detail[p++];
            if (p < detail_len && detail[p] == '\n') ++p;
            else if (p < detail_len && detail[p] == ' ') ++p;  // swallow wrap-space
            ln[i] = 0;
            scr.draw_text(0, r, ln);
            ++r;
        }
    }
    void cmd(uint8_t a, const char* arg = nullptr) { if (send_cmd) send_cmd(a, arg ? arg : ""); }
};

} // namespace cyclops
#endif
