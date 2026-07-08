// Host test driver for Cyclops device protocol + UI. Build-only, no HW.
#include "../include/protocol.h"
#include "../include/ui.h"
#include <cstdio>
#include <cstring>
#include <cassert>
#include <vector>

using namespace cyclops;

static int frames = 0;
static uint8_t last_type = 0;
static std::vector<uint8_t> last_payload;
static void on_frame(uint8_t type, const uint8_t* p, size_t n, void* ctx) {
    (void)ctx; frames++; last_type = type;
    last_payload.assign(p, p + n);
}

int main() {
    // 1) round-trip encode/decode
    FrameDecoder dec(on_frame, nullptr);
    const char* payload = "{\"v\":1}";
    uint8_t buf[128];
    size_t k = encode_frame(MSG_HELLO, (const uint8_t*)payload, strlen(payload), buf, sizeof(buf));
    assert(k > 0);
    for (size_t i = 0; i < k; ++i) dec.push(buf[i]);
    assert(frames == 1);
    assert(last_type == MSG_HELLO);
    assert(last_payload.size() == strlen(payload) &&
           memcmp(last_payload.data(), payload, strlen(payload)) == 0);
    printf("PASS: frame round-trip\n");

    // 2) CRC rejection: corrupt one byte
    frames = 0;
    uint8_t bad[128]; memcpy(bad, buf, k);
    bad[6] ^= 0xFF;
    for (size_t i = 0; i < k; ++i) dec.push(bad[i]);
    assert(frames == 0);
    printf("PASS: CRC rejection\n");

    // 3) UI adds notes and scrolls
    UiState ui; ui.init();
    ui.add_note("Buy milk");
    ui.add_note("Call mom");
    ui.add_note("Ship cyclops");
    assert(ui.note_count == 3);
    ui.on_wheel(-1); // up
    assert(ui.sel == 0);
    ui.on_wheel(1);  // down twice
    ui.on_wheel(1);
    assert(ui.sel == 2);
    ui.on_btn_a();   // toggle record
    assert(ui.recording);
    ui.on_btn_a();
    assert(!ui.recording);
    ui.on_btn_b();   // screen off
    assert(!ui.screen_on);
    printf("PASS: UI state machine\n");

    // 4) status json
    const char* s = ui.status_json(3700, true);
    assert(strstr(s, "3700") && strstr(s, "charging"));
    printf("PASS: status json (%s)\n", s);

    printf("ALL HOST TESTS PASSED\n");
    return 0;
}
