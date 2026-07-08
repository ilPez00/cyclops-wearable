#include "protocol.h"
#include <cstring>
#include <cstdio>

namespace cyclops {

uint16_t crc16_ccitt_false(const uint8_t* data, size_t len, uint16_t seed) {
    uint16_t crc = seed;
    for (size_t i = 0; i < len; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; ++b) {
            if (crc & 0x8000) crc = (uint16_t)((crc << 1) ^ 0x1021);
            else crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

size_t encode_frame(uint8_t type, const uint8_t* payload, size_t plen,
                    uint8_t* out, size_t out_cap) {
    const size_t overhead = 1 + 1 + 2 + 1 + 2; // magic*2 + len*2 + type + crc*2
    if (plen > 1024) return 0;
    if (out_cap < overhead + plen) return 0;
    size_t i = 0;
    out[i++] = 0xAA; out[i++] = 0x55;
    out[i++] = (uint8_t)(plen & 0xFF);
    out[i++] = (uint8_t)((plen >> 8) & 0xFF);
    out[i++] = type;
    if (plen) memcpy(out + i, payload, plen);
    i += plen;
    uint16_t crc = crc16_ccitt_false(&type, 1);
    crc = crc16_ccitt_false(payload, plen, crc);
    out[i++] = (uint8_t)(crc & 0xFF);
    out[i++] = (uint8_t)((crc >> 8) & 0xFF);
    return i;
}

void FrameDecoder::reset() {
    st_ = S_MAGIC1; len_ = 0; got_ = 0; type_ = 0;
    crc_calc_ = 0xFFFF; crc_recv_ = 0; buf_.clear();
}

void FrameDecoder::push(uint8_t b) {
    switch (st_) {
        case S_MAGIC1: if (b == 0xAA) st_ = S_MAGIC2; break;
        case S_MAGIC2: st_ = (b == 0x55) ? S_LEN1 : S_MAGIC1; break;
        case S_LEN1: len_ = b; st_ = S_LEN2; break;
        case S_LEN2: len_ = (uint16_t)(len_ | ((uint16_t)b << 8)); got_ = 0;
                     buf_.clear(); buf_.reserve(len_ ? len_ : 1); st_ = S_TYPE; break;
        case S_TYPE: type_ = b; crc_calc_ = crc16_ccitt_false(&type_, 1); st_ = S_PAYLOAD; break;
        case S_PAYLOAD:
            buf_.push_back(b);
            crc_calc_ = crc16_ccitt_false(&b, 1, crc_calc_);
            if (++got_ >= len_) st_ = S_CRC1;
            break;
        case S_CRC1: crc_recv_ = b; st_ = S_CRC2; break;
        case S_CRC2: {
            crc_recv_ = (uint16_t)(crc_recv_ | ((uint16_t)b << 8));
            if (crc_recv_ == crc_calc_ && cb_)
                cb_(type_, buf_.data(), buf_.size(), ctx_);
            reset();
            break;
        }
    }
}

void DisplayModel::clear_all() {
    for (int r = 0; r < ROWS; ++r) { lines[r][0] = '\0'; }
    active_row = 0;
}

void DisplayModel::set_line(int row, const char* txt) {
    if (row < 0 || row >= ROWS) return;
    int n = 0;
    while (txt[n] && n < COLS) { lines[row][n] = txt[n]; ++n; }
    lines[row][n] = '\0';
}

void DisplayModel::scroll(int dir) {
    active_row += dir;
    if (active_row < 0) active_row = 0;
    if (active_row >= ROWS) active_row = ROWS - 1;
}

} // namespace cyclops
