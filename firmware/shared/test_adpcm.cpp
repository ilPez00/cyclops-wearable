// ADPCM wire-contract test: the C++ encoder must be BYTE-IDENTICAL to
// brain/adpcm.py on shared vectors (same style as the CRC/framing tests),
// and the decoder must reproduce the pinned reconstructions.
// Vectors + expected bytes generated from the Python implementation.
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "adpcm.h"

using namespace cyclops;

static void hex(const uint8_t* b, size_t n, char* out) {
    for (size_t i = 0; i < n; ++i) sprintf(out + 2 * i, "%02x", b[i]);
    out[2 * n] = 0;
}

static void expect_encode(const char* name, const int16_t* pcm, size_t n,
                          const char* want_hex, int want_end_index) {
    uint8_t buf[256]; char got[513];
    int end = -1;
    size_t k = adpcm_encode_chunk(pcm, n, buf, sizeof(buf), 0, &end);
    assert(k == strlen(want_hex) / 2);
    hex(buf, k, got);
    if (strcmp(got, want_hex) != 0) {
        printf("FAIL %s: got %s want %s\n", name, got, want_hex);
        assert(false);
    }
    assert(end == want_end_index);
    printf("PASS encode %s (%zu bytes, end_index=%d)\n", name, k, end);
}

int main() {
    // silence: all zero codes
    int16_t silence[16] = {0};
    expect_encode("silence16", silence, 16, "000000000000000000000000", 0);

    // ramp -8000..7000 step 1000
    int16_t ramp[16];
    for (int i = 0; i < 16; ++i) ramp[i] = (int16_t)(-8000 + 1000 * i);
    expect_encode("ramp16", ramp, 16, "c0e000007077777747100121", 60);

    // odd count: pad flag byte[3]=1, decoder must yield exactly 7 samples
    int16_t odd7[7] = {100, -200, 300, -400, 500, -600, 700};
    expect_encode("odd7", odd7, 7, "64000001f0f7f707", 48);

    // full-scale alternation (pathological, pins clamping behavior)
    int16_t ext[8] = {32767, -32768, 32767, -32768, 0, 0, 32767, -32768};
    expect_encode("extremes8", ext, 8, "ff7f0000f0f2fff5", 43);

    // decoder: pinned reconstructions from the Python mirror
    {
        uint8_t buf[64]; int16_t out[32];
        size_t k = adpcm_encode_chunk(ramp, 16, buf, sizeof(buf));
        size_t n = adpcm_decode_chunk(buf, k, out, 32);
        assert(n == 16);
        const int16_t want[16] = {-8000, -7989, -7959, -7896, -7760, -7467,
                                  -6836, -5479, -2569, 1173, 1676, 3048,
                                  4294, 4672, 5702, 7263};
        for (int i = 0; i < 16; ++i) assert(out[i] == want[i]);
        printf("PASS decode ramp16 matches python reconstruction\n");

        k = adpcm_encode_chunk(odd7, 7, buf, sizeof(buf));
        n = adpcm_decode_chunk(buf, k, out, 32);
        assert(n == 7);  // pad flag honored — no phantom 8th sample
        const int16_t want7[7] = {100, 89, 119, 56, 192, -101, 530};
        for (int i = 0; i < 7; ++i) assert(out[i] == want7[i]);
        printf("PASS decode odd7 (pad flag drops the padding nibble)\n");
    }

    // warm-stream quality: 1 s of 440 Hz @16 kHz in 472-sample chunks with
    // the index carried across chunks must stay speech-grade on the tail.
    {
        static int16_t sig[16000], rec[16000];
        for (int i = 0; i < 16000; ++i)
            sig[i] = (int16_t)(8000.0 * sin(2.0 * M_PI * 440.0 * i / 16000.0));
        uint8_t buf[512];
        int idx = 0; size_t produced = 0;
        for (int off = 0; off < 16000; off += 472) {
            int n = off + 472 <= 16000 ? 472 : 16000 - off;
            size_t k = adpcm_encode_chunk(sig + off, n, buf, sizeof(buf), idx, &idx);
            assert(k > 0);
            produced += adpcm_decode_chunk(buf, k, rec + off, 16000 - off);
        }
        assert(produced == 16000);
        long max_err = 0;
        for (int i = 8000; i < 16000; ++i) {
            long e = labs((long)sig[i] - rec[i]);
            if (e > max_err) max_err = e;
        }
        printf("PASS stream tail maxerr=%ld (< 400)\n", max_err);
        assert(max_err < 400);
    }

    // guards: undersized buffer -> 0; malformed pad byte -> 0
    {
        uint8_t tiny[5]; int16_t out[8];
        assert(adpcm_encode_chunk(ramp, 16, tiny, sizeof(tiny)) == 0);
        uint8_t bad[6] = {0, 0, 0, 7, 0x11, 0x22};
        assert(adpcm_decode_chunk(bad, sizeof(bad), out, 8) == 0);
        printf("PASS guards (small buffer, malformed pad byte)\n");
    }

    printf("ALL ADPCM TESTS PASSED\n");
    return 0;
}
