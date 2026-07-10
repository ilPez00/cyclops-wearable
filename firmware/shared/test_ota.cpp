// Host tests for the OTA-over-BLE receive state machine (ota.h).
// Build: g++ -std=c++17 -I lib/cyclops_shared/include shared/test_ota.cpp
// Wires OtaSink to an in-memory buffer so the whole update flow — begin,
// sequential chunks, size/CRC32 verify, and every failure path — runs on
// the host with no esp_ota / BLE dependencies.
#include "ota.h"
#include <cstdio>
#include <cstring>
#include <cassert>
#include <vector>
using namespace cyclops;

// ---- in-memory flash sink ----
struct MemFlash {
    std::vector<uint8_t> buf;
    uint32_t announced = 0;
    bool committed = false;
    bool finished = false;
    bool fail_begin = false, fail_write = false, fail_finish = false;
};
static bool mem_begin(uint32_t size, void* c) {
    auto* m = (MemFlash*)c; if (m->fail_begin) return false;
    m->buf.clear(); m->announced = size; m->committed = false; m->finished = false; return true;
}
static bool mem_write(const uint8_t* d, size_t n, void* c) {
    auto* m = (MemFlash*)c; if (m->fail_write) return false;
    m->buf.insert(m->buf.end(), d, d + n); return true;
}
static bool mem_finish(bool commit, void* c) {
    auto* m = (MemFlash*)c; if (m->fail_finish) return false;
    m->finished = true; m->committed = commit; return true;
}
static OtaSink make_sink(MemFlash* m) {
    OtaSink s; s.begin = mem_begin; s.write = mem_write; s.finish = mem_finish; s.ctx = m; return s;
}

// pack a 12-byte BEGIN payload
static void pack_begin(uint8_t* out, uint32_t size, uint32_t crc, uint32_t chunk) {
    for (int i=0;i<4;i++) out[i]    = (size  >> (8*i)) & 0xFF;
    for (int i=0;i<4;i++) out[4+i]  = (crc   >> (8*i)) & 0xFF;
    for (int i=0;i<4;i++) out[8+i]  = (chunk >> (8*i)) & 0xFF;
}
// pack a chunk payload [seq][data]
static std::vector<uint8_t> pack_chunk(uint32_t seq, const uint8_t* d, size_t n) {
    std::vector<uint8_t> v(4 + n);
    for (int i=0;i<4;i++) v[i] = (seq >> (8*i)) & 0xFF;
    memcpy(v.data()+4, d, n);
    return v;
}

int main() {
    // ---- image under test ----
    uint8_t img[300];
    for (size_t i=0;i<sizeof(img);++i) img[i] = (uint8_t)(i*7 + 3);
    uint32_t img_crc = crc32_final(crc32_ieee(img, sizeof(img)));

    // ---- 1. happy path: begin + 3 chunks + end -> committed, bytes match ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, sizeof(img), img_crc, 128);
        uint32_t ack;
        assert(rx.on_begin(beg, 12, &ack) == OTA_OK); assert(ack == 0);
        assert(rx.active()); assert(rx.expected() == sizeof(img));
        size_t off=0; uint32_t seq=0;
        while (off < sizeof(img)) {
            size_t n = (sizeof(img)-off > 128) ? 128 : sizeof(img)-off;
            auto c = pack_chunk(seq, img+off, n);
            assert(rx.on_chunk(c.data(), c.size(), &ack) == OTA_OK);
            assert(ack == seq);
            off += n; seq++;
        }
        assert(rx.received() == sizeof(img));
        assert(rx.on_end(&ack) == OTA_OK);
        assert(!rx.active());
        assert(m.committed && m.finished);
        assert(m.buf.size() == sizeof(img));
        assert(memcmp(m.buf.data(), img, sizeof(img)) == 0);
        printf("PASS ota happy path (%zu bytes, crc=%08x)\n", sizeof(img), img_crc);
    }

    // ---- 2. busy: second begin while active is rejected ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, sizeof(img), img_crc, 128);
        uint32_t ack;
        assert(rx.on_begin(beg, 12, &ack) == OTA_OK);
        assert(rx.on_begin(beg, 12, &ack) == OTA_BUSY);
        printf("PASS ota busy reject\n");
    }

    // ---- 3. chunk/end with no session -> BAD_STATE ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint32_t ack;
        auto c = pack_chunk(0, img, 10);
        assert(rx.on_chunk(c.data(), c.size(), &ack) == OTA_BAD_STATE);
        assert(rx.on_end(&ack) == OTA_BAD_STATE);
        printf("PASS ota bad-state reject\n");
    }

    // ---- 4. out-of-order / duplicate seq -> BAD_SEQ ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, sizeof(img), img_crc, 128);
        uint32_t ack; rx.on_begin(beg, 12, &ack);
        auto c0 = pack_chunk(0, img, 64);
        assert(rx.on_chunk(c0.data(), c0.size(), &ack) == OTA_OK);
        auto skip = pack_chunk(2, img+64, 64);   // skipped seq 1
        assert(rx.on_chunk(skip.data(), skip.size(), &ack) == OTA_BAD_SEQ);
        auto dup = pack_chunk(0, img, 64);        // duplicate seq 0
        assert(rx.on_chunk(dup.data(), dup.size(), &ack) == OTA_BAD_SEQ);
        printf("PASS ota bad-seq reject\n");
    }

    // ---- 5. overflow: chunk exceeds announced size -> OVERFLOW + abort ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, 50, img_crc, 128);
        uint32_t ack; rx.on_begin(beg, 12, &ack);
        auto c = pack_chunk(0, img, 100);         // 100 > 50
        assert(rx.on_chunk(c.data(), c.size(), &ack) == OTA_OVERFLOW);
        assert(!rx.active());                      // aborted
        printf("PASS ota overflow reject\n");
    }

    // ---- 6. size mismatch at end ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, sizeof(img), img_crc, 128);
        uint32_t ack; rx.on_begin(beg, 12, &ack);
        auto c = pack_chunk(0, img, 100);         // only 100 of 300
        rx.on_chunk(c.data(), c.size(), &ack);
        assert(rx.on_end(&ack) == OTA_SIZE_MISMATCH);
        assert(!rx.active());
        printf("PASS ota size-mismatch reject\n");
    }

    // ---- 7. crc mismatch at end (right size, wrong crc announced) ----
    {
        MemFlash m; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, sizeof(img), img_crc ^ 0xDEADBEEF, 128);
        uint32_t ack; rx.on_begin(beg, 12, &ack);
        size_t off=0; uint32_t seq=0;
        while (off < sizeof(img)) {
            size_t n = (sizeof(img)-off > 128) ? 128 : sizeof(img)-off;
            auto c = pack_chunk(seq, img+off, n);
            rx.on_chunk(c.data(), c.size(), &ack); off += n; seq++;
        }
        assert(rx.on_end(&ack) == OTA_CRC_MISMATCH);
        assert(!m.committed);
        printf("PASS ota crc-mismatch reject\n");
    }

    // ---- 8. flash sink failures propagate ----
    {
        MemFlash m; m.fail_begin = true; OtaSink sk = make_sink(&m); OtaReceiver rx(sk);
        uint8_t beg[12]; pack_begin(beg, sizeof(img), img_crc, 128);
        uint32_t ack;
        assert(rx.on_begin(beg, 12, &ack) == OTA_FLASH_ERR);
        assert(!rx.active());

        MemFlash m2; m2.fail_write = true; OtaSink sk2 = make_sink(&m2); OtaReceiver rx2(sk2);
        rx2.on_begin(beg, 12, &ack);
        auto c = pack_chunk(0, img, 64);
        assert(rx2.on_chunk(c.data(), c.size(), &ack) == OTA_FLASH_ERR);
        assert(!rx2.active());
        printf("PASS ota flash-err propagation\n");
    }

    // ---- 9. ack json shape ----
    {
        char s[64]; int n = OtaReceiver::ack_json(s, sizeof(s), 42, OTA_CRC_MISMATCH);
        assert(n > 0); assert(strcmp(s, "{\"seq\":42,\"st\":6}") == 0);
        printf("PASS ota ack json (%s)\n", s);
    }

    // ---- 10. crc32 matches known zlib value for "123456789" ----
    {
        const char* t = "123456789";
        uint32_t c = crc32_final(crc32_ieee((const uint8_t*)t, 9));
        assert(c == 0xCBF43926u);   // canonical CRC32 check value
        printf("PASS ota crc32 check value (%08x)\n", c);
    }

    printf("ALL OTA TESTS PASSED\n");
    return 0;
}
