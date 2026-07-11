#include "cyclops_shared.h"
#include <cstdio>
#include <cstring>
#include <cassert>
using namespace cyclops;

static int frames=0; static uint8_t ltype=0; static uint8_t lpay[200]; static size_t llen=0;
static void on_frame(uint8_t t, const uint8_t* p, size_t n, void* c) {
    (void)c; frames++; ltype=t; llen=n; memcpy(lpay,p,n);
}
int main() {
    FrameDecoder dec(on_frame, nullptr);
    const char* pl="{\"v\":2}";
    uint8_t buf[128];
    size_t k = encode_frame(MSG_PEER_HELLO, (const uint8_t*)pl, strlen(pl), buf, sizeof(buf));
    assert(k>0);
    for (size_t i=0;i<k;++i) dec.push(buf[i]);
    assert(frames==1); assert(ltype==MSG_PEER_HELLO); assert(llen==strlen(pl));
    assert(memcmp(lpay,pl,llen)==0);
    printf("PASS shared frame round-trip\n");
    frames=0; uint8_t bad[128]; memcpy(bad,buf,k); bad[6]^=0xFF;
    for (size_t i=0;i<k;++i) dec.push(bad[i]);
    assert(frames==0); printf("PASS shared crc reject\n");
    // oversized declared length must not wedge the decoder forever
    frames=0;
    const uint8_t big_hdr[5] = {0xAA, 0x55, 0x2C, 0x01, MSG_PEER_HELLO}; // len=300 > buf capacity
    for (size_t i=0;i<sizeof(big_hdr);++i) dec.push(big_hdr[i]);
    for (int i=0;i<400;++i) dec.push(0x00); // junk payload bytes
    for (size_t i=0;i<k;++i) dec.push(buf[i]); // then a valid frame
    assert(frames==1); assert(ltype==MSG_PEER_HELLO);
    printf("PASS shared oversized-frame recovery\n");
    UiState ui; ui.init();
    ui.add_note("Buy milk"); ui.add_note("Call mom"); ui.add_note("Ship v2");
    assert(ui.note_count==3);
    ui.on_wheel(-1); assert(ui.sel==0);
    ui.on_wheel(1); ui.on_wheel(1); assert(ui.sel==2);
    ui.on_joy(1,0);
    ui.on_btn_a(); assert(ui.recording); ui.on_btn_a(); assert(!ui.recording);
    ui.on_proximity(true);
    char s[80]; int n=ui.status_json(s,sizeof(s)); ui.batt_mv=3900; assert(n>0); assert(strstr(s,"3900"));
    printf("PASS shared UI (%s)\n", s);
    printf("ALL SHARED TESTS PASSED\n");
    return 0;
}
