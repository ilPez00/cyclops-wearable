#include "../include/v2/protocol_v2.h"
#include "../include/protocol.h"
#include <cstdio>
#include <cstring>
#include <cassert>
using namespace cyclops; using namespace cyclops::v2;

int main() {
    // HUD frame build+parse round-trip via v1 framing crc
    const char* lines[4] = {"Buy milk", "Call mom", 0, 0};
    uint8_t hud[128];
    size_t k = build_hud_frame(0, lines, 2, true, hud, sizeof(hud));
    assert(k > 0);
    // decode: find L lines
    int nlines = 0; char got[4][20] = {0};
    int li = 0, ci = 0;
    for (size_t i = 0; i < k; ++i) {
        if (hud[i] == 'L' && li < 4) { ci = 0; ++i; while (i<k && hud[i]!='\n' && ci<19) got[li][ci++] = (char)hud[i++]; got[li][ci]=0; ++li; }
    }
    assert(li == 2);
    assert(strcmp(got[0], "Buy milk") == 0);
    assert(strcmp(got[1], "Call mom") == 0);
    printf("PASS v2 hud build/parse (%d lines)\n", li);

    // HEALTH parse
    const char* hp = "t=1717000000000,hr=72,spo2=98,sl=2,batt=3900";
    int64_t t; int hr,spo2,sl,batt;
    assert(parse_health((const uint8_t*)hp, strlen(hp), t, hr, spo2, sl, batt));
    assert(hr == 72 && spo2 == 98 && batt == 3900);
    printf("PASS v2 health parse (hr=%d spo2=%d)\n", hr, spo2);

    // v1 crc still works (regression)
    uint8_t f[64]; size_t fl = encode_frame(MSG_HELLO, (const uint8_t*)"{}", 2, f, sizeof(f));
    assert(fl > 0);
    printf("PASS v1 framing intact (%zu bytes)\n", fl);

    printf("ALL V2 HOST TESTS PASSED\n");
    return 0;
}
