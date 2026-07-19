// RowLink — the one-way HUD row protocol between the two CyclUno boards.
//
// The controller (cycluno/main.cpp) renders 4 text rows and streams them over
// SoftwareSerial to the display board (cyclobig/main.cpp), which reassembles
// and draws them. Framing, per row:
//
//     [idx byte 0..3][text ASCII, no '\n'][ '\n' ]
//
// The row index (<= 3) and the REC bell marker (0x07) can never equal '\n'
// (0x0A), so the newline is an unambiguous delimiter. This header is the
// single source of both ends so a host test can round-trip encode -> decode
// (shared/test_rowlink.cpp); no Arduino headers here, so it builds on the host.
#pragma once
#include <stdint.h>

namespace cycluno {

// Widest row text carried on the link (matches the HUD's COLS = 21).
static const uint8_t ROWLINK_MAX_TEXT = 21;

// Encode one row frame into `buf` (needs ROWLINK_MAX_TEXT + 2 bytes for the
// worst case). Text is truncated at ROWLINK_MAX_TEXT; any stray '\n' in the
// text is substituted with a space so it can never be mistaken for the frame
// delimiter. Returns the number of bytes written.
inline uint8_t rowlink_encode(uint8_t idx, const char* text,
                              uint8_t* buf, uint8_t cap) {
    if (cap < 2) return 0;
    uint8_t n = 0;
    buf[n++] = idx;
    for (uint8_t i = 0; text && text[i] && i < ROWLINK_MAX_TEXT && n < (uint8_t)(cap - 1); ++i)
        buf[n++] = (text[i] == '\n') ? (uint8_t)' ' : (uint8_t)text[i];
    buf[n++] = '\n';
    return n;
}

// Streaming decoder: push received bytes one at a time; the callback fires
// once per complete row with the index and NUL-terminated text.
class RowLinkDecoder {
public:
    typedef void (*RowFn)(uint8_t idx, const char* text, void* ctx);

    RowLinkDecoder(RowFn fn, void* ctx = nullptr) : fn_(fn), ctx_(ctx) {}

    void push(uint8_t b) {
        if (expect_idx_) {
            idx_ = b; len_ = 0; expect_idx_ = false;
        } else if (b == '\n') {
            buf_[len_] = 0;
            if (fn_) fn_(idx_, buf_, ctx_);
            expect_idx_ = true;
        } else if (len_ < ROWLINK_MAX_TEXT) {
            buf_[len_++] = (char)b;
        }
        // bytes past ROWLINK_MAX_TEXT are dropped until the delimiting '\n'
    }

private:
    RowFn fn_;
    void* ctx_;
    char buf_[ROWLINK_MAX_TEXT + 1];
    uint8_t len_ = 0, idx_ = 0;
    bool expect_idx_ = true;
};

}  // namespace cycluno
