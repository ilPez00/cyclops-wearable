#ifndef CYCLOPS_SHARED_H
#define CYCLOPS_SHARED_H
// Cyclops shared lib — header-only for portable MCU builds (AVR/ESP32/host).
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>

// ---- CRC16-CCITT (FALSE) ----
inline uint16_t crc16_ccitt_false(const uint8_t* d, size_t n, uint16_t seed = 0xFFFF) {
    uint16_t crc = seed;
    for (size_t i = 0; i < n; ++i) {
        crc ^= (uint16_t)d[i] << 8;
        for (int b = 0; b < 8; ++b) crc = (crc & 0x8000) ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

namespace cyclops {

// audio backpressure counter (incremented when a BLE notify is dropped because
// the queue is full; see audio_task in xiao/src/main.cpp). inline so it has a
// single definition across host + xiao builds without a separate TU.
inline unsigned long audio_dropped = 0;

enum MsgType : uint8_t {
    MSG_HELLO=1, MSG_HEARTBEAT=2, MSG_INPUT_EVENT=3, MSG_AUDIO_META=4,
    MSG_AUDIO_CHUNK=5, MSG_DISPLAY_CMD=6, MSG_NOTE=7, MSG_STATUS=8,
    MSG_CMD=9, MSG_ACK=10,
    MSG_PEER_HELLO=11, MSG_TIME_SYNC=12, MSG_HEALTH_SAMPLE=13,
    MSG_HUD_FRAME=14, MSG_RING_GESTURE=15, MSG_AUDIO_COMPRESSED=16,
    MSG_CONFIRM=17, MSG_PEER_STATUS=18, MSG_AUDIO_STOP=19, MSG_TTS=20,
    // OTA firmware update over BLE (see ota.h). BEGIN/CHUNK/END are phone->device,
    // ACK is device->phone for flow-control + verify result.
    MSG_OTA_BEGIN=21, MSG_OTA_CHUNK=22, MSG_OTA_END=23, MSG_OTA_ACK=24
};

// Encode a frame. Returns byte count (0 on overflow). cap must be >= 7+plen.
// CRC covers len(2)+type(1)+payload.
inline size_t encode_frame(uint8_t type, const uint8_t* payload, size_t plen,
                           uint8_t* out, size_t cap) {
    if (plen > 0xFFFF || cap < 7 + plen) return 0;
    out[0] = 0xAA; out[1] = 0x55;
    out[2] = (uint8_t)(plen & 0xFF);
    out[3] = (uint8_t)((plen >> 8) & 0xFF);
    out[4] = type;
    if (plen) memcpy(out + 5, payload, plen);
    uint16_t crc = crc16_ccitt_false(out + 2, 3 + plen);
    out[5 + plen] = (uint8_t)(crc & 0xFF);
    out[6 + plen] = (uint8_t)((crc >> 8) & 0xFF);
    return 7 + plen;
}

// Streaming decoder. Buffers len+type+payload then CRCs that window.
class FrameDecoder {
public:
    using Cb = void(*)(uint8_t type, const uint8_t* payload, size_t plen, void* ctx);
    FrameDecoder(Cb cb, void* ctx) : cb_(cb), ctx_(ctx) { reset(); }
    void reset() { st_ = M1; got_ = 0; len_ = 0; type_ = 0; }
    void push(uint8_t b) {
        switch (st_) {
            case M1: if (b == 0xAA) st_ = M2; break;
            case M2: st_ = (b == 0x55) ? L1 : (b == 0xAA ? M2 : M1); break;
            case L1: len_ = b; st_ = L2; break;
            case L2: len_ = (uint16_t)(len_ | ((uint16_t)b << 8)); got_ = 0; st_ = T; break;
            case T:  if (len_ > sizeof(buf_) - 3) { reset(); break; } // reject frames larger than buffer: decoder would never drain them
                     type_ = b; buf_[0] = (uint8_t)(len_ & 0xFF); buf_[1] = (uint8_t)(len_ >> 8); buf_[2] = type_; got_ = 3; st_ = (len_ ? P : CR1); break;
            case P:
                if (got_ < sizeof(buf_)) buf_[got_++] = b;
                if (got_ - 3 >= len_) st_ = CR1;
                break;
            case CR1: crc_recv_ = b; st_ = CR2; break;
            case CR2: {
                crc_recv_ |= (uint16_t)b << 8;
                uint16_t exp = crc16_ccitt_false(buf_, got_);
                if (crc_recv_ == exp && cb_ && got_ >= 3) cb_(type_, buf_ + 3, got_ - 3, ctx_);
                reset();
                break;
            }
        }
    }
private:
    enum St { M1,M2,L1,L2,T,P,CR1,CR2 } st_ = M1;
    uint16_t len_ = 0, got_ = 0, crc_recv_ = 0;
    uint8_t type_ = 0; uint8_t buf_[256];
    Cb cb_; void* ctx_;
};

// ---- UI state machine (resolution-agnostic) ----
struct DisplayModel {
    static const int ROWS = 4;
    static const int COLS = 22;
    char lines[ROWS][COLS+1];
    int active_row = 0;
    void clear_all() { for (int i=0;i<ROWS;++i) lines[i][0]=0; }
    void set_line(int r, const char* t) { if (r<0||r>=ROWS) return; strncpy(lines[r], t, COLS); lines[r][COLS]=0; }
    void scroll(int dir) { active_row += dir; if (active_row<0) active_row=0; if (active_row>=ROWS) active_row=ROWS-1; }
};

struct UiState {
    DisplayModel disp;
    static const int MAX_NOTES = 12;
    char notes[MAX_NOTES][DisplayModel::COLS+1];
    int note_count=0, view_top=0, sel=0;
    bool recording=false, screen_on=true;
    // status telemetry for the screen
    uint16_t batt_mv=3900; bool charging=false; bool bt=false; int hr=0; uint32_t clock_utc=0;

    void init() { disp.clear_all(); note_count=0; view_top=0; sel=0; recording=false; screen_on=true; render(); }
    void add_note(const char* t) {
        if (note_count >= MAX_NOTES) { memmove(notes[0], notes[1], (MAX_NOTES-1)*(DisplayModel::COLS+1)); note_count=MAX_NOTES-1; }
        int n=0; while (t[n] && n<DisplayModel::COLS) { notes[note_count][n]=t[n]; ++n; } notes[note_count][n]=0;
        note_count++; render();
    }
    void render() {
        disp.clear_all();
        char hdr[DisplayModel::COLS+1];
        snprintf(hdr, sizeof(hdr), recording ? "[REC] n:%d" : "n:%d", note_count);
        disp.set_line(0, hdr);
        for (int i=0;i<3 && view_top+i<note_count;++i) {
            int idx=view_top+i; const char* mk = (idx==sel)?"#":" ";
            char row[40]; snprintf(row,sizeof(row),"%s%d %s",mk,idx+1,notes[idx]);
            disp.set_line(i+1,row);
        }
        if (!screen_on) disp.clear_all();
    }
    void on_wheel(int delta) { if (delta>0 && sel<note_count-1) sel++; else if (delta<0 && sel>0) sel--; clamp_view(); render(); }
    void on_btn_a() { recording=!recording; render(); }
    void on_btn_b() { screen_on=!screen_on; render(); }
    void on_joy(int dx, int dy) {
        if (dy>0) on_wheel(1); else if (dy<0) on_wheel(-1);
        if (dx>0) { if (note_count) sel = (sel+1) % note_count; }
        render();
    }
    void on_proximity(bool near) { if (near && !screen_on) { screen_on=true; render(); } }
    void on_gesture(const char* name) {
        if (!strcmp(name,"nod")) recording=!recording;
        else if (!strcmp(name,"shake")) screen_on=false;
        render();
    }
    // read accessors for screens
    int count() const { return note_count; }
    const char* note(int i) const { return (i>=0 && i<note_count) ? notes[i] : ""; }
    int selected() const { return sel; }
    int top() const { return view_top; }
    int status_json(char* out, size_t cap) const {
        return snprintf(out, cap, "{\"t\":8,\"batt\":%u,\"chg\":%d,\"rec\":%d,\"bt\":%d,\"hr\":%d}",
                        batt_mv, charging?1:0, recording?1:0, bt?1:0, hr);
    }
private:
    void clamp_view() { if (sel<view_top) view_top=sel; if (sel>view_top+2) view_top=sel-2; }
};

} // namespace cyclops
#endif
