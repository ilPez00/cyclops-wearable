// IMA ADPCM (DVI4) mono codec — header-only, host-testable, no deps.
//
// Why: 16 kHz PCM16 needs 32 KB/s; BLE notify throughput measured on the
// XIAO link is ~2-8 KB/s (docs/13 premortem #2). IMA ADPCM is 4 bits/sample
// (4:1), deterministic integer math, ~40 lines each way — the standard
// choice for MCU audio over thin links.
//
// Wire format of one compressed chunk (MSG_AUDIO_CHUNK payload when the
// AUDIO_META codec byte == AUDIO_CODEC_ADPCM):
//   [0..1] int16 LE  predictor (decoder seed = first sample)
//   [2]    uint8     step index seed
//   [3]    uint8     pad flag: 1 = odd sample count (last high nibble unused)
//   [4..]  packed 4-bit codes, low nibble first — 2 samples/byte
// Each chunk is self-contained (decoder needs only its header), so lost BLE
// notifies corrupt only their own ~30 ms window, never the stream. The
// ENCODER should still carry its step index across chunks (pass the returned
// end index as the next seed) — that keeps the adaption warm and confines
// the cold-start distortion to the very first chunk.
//
// The Python mirror is brain/adpcm.py — test_shared/test_adpcm.py assert the
// two implementations are byte-identical on shared vectors (same contract
// style as the CRC/framing tests).

#pragma once
#include <stdint.h>
#include <stddef.h>

namespace cyclops {

static const int8_t ADPCM_INDEX_TABLE[16] = {
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8,
};

static const int16_t ADPCM_STEP_TABLE[89] = {
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
};

static const uint8_t AUDIO_CODEC_PCM16 = 0;
static const uint8_t AUDIO_CODEC_ADPCM = 1;

inline int adpcm_clamp_index(int i) { return i < 0 ? 0 : (i > 88 ? 88 : i); }

// Encode one 4-bit code for `sample` given codec state. Updates state.
inline uint8_t adpcm_encode_sample(int16_t sample, int32_t& predictor, int& index) {
    int step = ADPCM_STEP_TABLE[index];
    int32_t diff = (int32_t)sample - predictor;
    uint8_t code = 0;
    if (diff < 0) { code = 8; diff = -diff; }
    if (diff >= step) { code |= 4; diff -= step; }
    if (diff >= step >> 1) { code |= 2; diff -= step >> 1; }
    if (diff >= step >> 2) { code |= 1; }
    // reconstruct exactly like the decoder so state never drifts
    int32_t delta = step >> 3;
    if (code & 4) delta += step;
    if (code & 2) delta += step >> 1;
    if (code & 1) delta += step >> 2;
    if (code & 8) predictor -= delta; else predictor += delta;
    if (predictor > 32767) predictor = 32767;
    if (predictor < -32768) predictor = -32768;
    index = adpcm_clamp_index(index + ADPCM_INDEX_TABLE[code]);
    return code;
}

inline int16_t adpcm_decode_sample(uint8_t code, int32_t& predictor, int& index) {
    int step = ADPCM_STEP_TABLE[index];
    int32_t delta = step >> 3;
    if (code & 4) delta += step;
    if (code & 2) delta += step >> 1;
    if (code & 1) delta += step >> 2;
    if (code & 8) predictor -= delta; else predictor += delta;
    if (predictor > 32767) predictor = 32767;
    if (predictor < -32768) predictor = -32768;
    index = adpcm_clamp_index(index + ADPCM_INDEX_TABLE[code]);
    return (int16_t)predictor;
}

// Encode `n` PCM16 samples into `out` (self-contained chunk with 4-byte
// state header). Returns bytes written, or 0 if `cap` is too small.
// Capacity needed: 4 + (n+1)/2. When `end_index` is given it receives the
// final step index — pass it back as `seed_index` for the next chunk so the
// adaption stays warm across a stream.
inline size_t adpcm_encode_chunk(const int16_t* pcm, size_t n,
                                 uint8_t* out, size_t cap,
                                 int seed_index = 0, int* end_index = nullptr) {
    if (n == 0 || cap < 4 + (n + 1) / 2) return 0;
    int32_t predictor = pcm[0];
    int index = adpcm_clamp_index(seed_index);
    out[0] = (uint8_t)(predictor & 0xFF);
    out[1] = (uint8_t)((predictor >> 8) & 0xFF);
    out[2] = (uint8_t)index;
    out[3] = (uint8_t)(n & 1);              // pad flag: odd sample count
    size_t o = 4;
    uint8_t nibbles = 0;
    for (size_t i = 0; i < n; ++i) {
        uint8_t code = adpcm_encode_sample(pcm[i], predictor, index);
        if ((i & 1) == 0) {
            nibbles = code;                 // low nibble first
        } else {
            nibbles |= (uint8_t)(code << 4);
            out[o++] = nibbles;
        }
    }
    if (n & 1) out[o++] = nibbles;          // trailing low nibble, high = 0
    if (end_index) *end_index = index;
    return o;
}

// Decode a self-contained chunk produced by adpcm_encode_chunk.
// Returns samples written, or 0 on malformed input / small buffer.
inline size_t adpcm_decode_chunk(const uint8_t* in, size_t len,
                                 int16_t* pcm, size_t max_samples) {
    if (len < 4 || in[3] > 1) return 0;
    int32_t predictor = (int16_t)((uint16_t)in[0] | ((uint16_t)in[1] << 8));
    int index = adpcm_clamp_index(in[2]);
    size_t nib = (len - 4) * 2 - in[3];     // pad flag drops the last nibble
    if (nib > max_samples) return 0;
    size_t o = 0;
    for (size_t i = 0; i < nib; ++i) {
        uint8_t byte = in[4 + (i >> 1)];
        uint8_t code = (i & 1) ? (byte >> 4) : (byte & 0x0F);
        pcm[o++] = adpcm_decode_sample(code, predictor, index);
    }
    return o;
}

}  // namespace cyclops
