#include "v2/protocol_v2.h"
#include <cstring>
#include <cstdio>

namespace cyclops { namespace v2 {

size_t build_hud_frame(uint8_t kind, const char* lines[4], int nlines,
                       bool more, uint8_t* out, size_t cap) {
    // minimal format: K<kind>\nL<line0>\nL<line1>... M<more>
    // avoid json parser on tiny MCU. Phone/glasses decode with tiny state machine.
    size_t i = 0;
    auto put = [&](const char* s) {
        while (*s && i < cap - 1) out[i++] = (uint8_t)(*s++);
    };
    char kb[4]; snprintf(kb, sizeof(kb), "K%d\n", (int)kind);
    put(kb);
    for (int l = 0; l < nlines && l < 4; ++l) {
        out[i++] = 'L'; // L
        const char* s = lines[l];
        int n = 0;
        while (s[n] && n < 18 && i < cap - 1) out[i++] = (uint8_t)(s[n++]);
        out[i++] = '\n';
    }
    out[i++] = 'M'; out[i++] = more ? '1' : '0'; out[i++] = '\n';
    return i;
}

bool parse_health(const uint8_t* p, size_t n, int64_t& t, int& hr,
                  int& spo2, int& sleep_stage, int& batt_mv) {
    // expected: t=<ms>,hr=<bpm>,spo2=<pct>,sl=<stage>,batt=<mv>
    char buf[128]; if (n >= sizeof(buf)) n = sizeof(buf) - 1;
    memcpy(buf, p, n); buf[n] = 0;
    t = hr = spo2 = sleep_stage = batt_mv = 0;
    if (sscanf(buf, "t=%lld,hr=%d,spo2=%d,sl=%d,batt=%d",
               &t, &hr, &spo2, &sleep_stage, &batt_mv) >= 2) return true;
    return false;
}

}} // namespace
