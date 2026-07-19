// RowLink host gate: encode (controller) -> byte stream -> decode (display)
// must round-trip every row exactly, and framing must survive the edge cases
// the HUD can actually produce (full-width rows, the REC bell 0x07, an
// accidental newline in text, over-long text).
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "rowlink.h"

using namespace cycluno;

// Captured rows from the decoder callback.
static struct { uint8_t idx; char text[64]; } got[16];
static int got_n = 0;
static void sink(uint8_t idx, const char* text, void*) {
    got[got_n].idx = idx;
    strncpy(got[got_n].text, text, sizeof(got[got_n].text) - 1);
    got[got_n].text[sizeof(got[got_n].text) - 1] = 0;
    ++got_n;
}

// Encode one row and stream it through the decoder.
static void feed(RowLinkDecoder& d, uint8_t idx, const char* text) {
    uint8_t buf[ROWLINK_MAX_TEXT + 2];
    uint8_t n = rowlink_encode(idx, text, buf, sizeof(buf));
    for (uint8_t i = 0; i < n; ++i) d.push(buf[i]);
}

int main() {
    RowLinkDecoder d(sink);

    // 1) plain 4-row HUD round-trips exactly
    got_n = 0;
    feed(d, 0, "HOME");
    feed(d, 1, "CyclUno ready");
    feed(d, 2, "");
    feed(d, 3, "A:rec  B:menu");
    assert(got_n == 4);
    assert(got[0].idx == 0 && strcmp(got[0].text, "HOME") == 0);
    assert(got[1].idx == 1 && strcmp(got[1].text, "CyclUno ready") == 0);
    assert(got[2].idx == 2 && strcmp(got[2].text, "") == 0);      // empty row ok
    assert(got[3].idx == 3 && strcmp(got[3].text, "A:rec  B:menu") == 0);
    printf("PASS 4-row round-trip\n");

    // 2) full-width row (exactly 21 chars) is preserved
    got_n = 0;
    const char* full = "ABCDEFGHIJKLMNOPQRSTU";   // 21 chars
    assert(strlen(full) == ROWLINK_MAX_TEXT);
    feed(d, 1, full);
    assert(got_n == 1 && strcmp(got[1 - 1].text, full) == 0);
    printf("PASS full-width row\n");

    // 3) over-long text truncates to ROWLINK_MAX_TEXT, framing stays intact
    got_n = 0;
    feed(d, 0, "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ");   // 36 chars
    feed(d, 1, "next");                                    // must still arrive
    assert(got_n == 2);
    assert(strlen(got[0].text) == ROWLINK_MAX_TEXT);
    assert(strncmp(got[0].text, "0123456789ABCDEFGHIJK", ROWLINK_MAX_TEXT) == 0);
    assert(got[1].idx == 1 && strcmp(got[1].text, "next") == 0);
    printf("PASS over-long truncation keeps framing\n");

    // 4) the REC bell (0x07) is data, not a delimiter
    got_n = 0;
    feed(d, 0, "HOME \x07REC");
    assert(got_n == 1 && strcmp(got[0].text, "HOME \x07REC") == 0);
    printf("PASS bell 0x07 passes through\n");

    // 5) a stray newline in text can't break framing (encoded as space)
    got_n = 0;
    feed(d, 2, "a\nb");
    feed(d, 3, "after");
    assert(got_n == 2);
    assert(strcmp(got[0].text, "a b") == 0);   // '\n' -> ' '
    assert(got[1].idx == 3 && strcmp(got[1].text, "after") == 0);
    printf("PASS newline-in-text neutralized\n");

    printf("ALL ROWLINK TESTS PASSED\n");
    return 0;
}
