#ifndef CYCLOPS_PROTOCOL_H
#define CYCLOPS_PROTOCOL_H
#include <cstdint>
#include <cstddef>
#include <vector>

namespace cyclops {

// CRC16-CCITT (0xFFFF init, poly 0x1021, no reflect) — "FALSE" variant.
uint16_t crc16_ccitt_false(const uint8_t* data, size_t len, uint16_t seed = 0xFFFF);

enum MsgType : uint8_t {
    MSG_HELLO = 1,
    MSG_HEARTBEAT = 2,
    MSG_INPUT_EVENT = 3,
    MSG_AUDIO_META = 4,
    MSG_AUDIO_CHUNK = 5,
    MSG_DISPLAY_CMD = 6,
    MSG_NOTE = 7,
    MSG_STATUS = 8,
    MSG_CMD = 9,
    MSG_ACK = 10,
};

// Encode a frame into out. Returns number of bytes written (0 on overflow).
size_t encode_frame(uint8_t type, const uint8_t* payload, size_t plen,
                    uint8_t* out, size_t out_cap);

// Streaming decoder: feed bytes one at a time. Calls on_frame() when a full
// valid frame is received. On CRC failure the frame is dropped and state resets.
class FrameDecoder {
public:
    using FrameCb = void(*)(uint8_t type, const uint8_t* payload, size_t plen, void* ctx);
    FrameDecoder(FrameCb cb, void* ctx) : cb_(cb), ctx_(ctx) {}
    void reset();
    void push(uint8_t b);
private:
    enum State { S_MAGIC1, S_MAGIC2, S_LEN1, S_LEN2, S_TYPE, S_PAYLOAD, S_CRC1, S_CRC2 };
    State st_ = S_MAGIC1;
    uint16_t len_ = 0;
    uint16_t got_ = 0;
    uint8_t type_ = 0;
    uint16_t crc_calc_ = 0xFFFF;
    uint16_t crc_recv_ = 0;
    std::vector<uint8_t> buf_;
    FrameCb cb_;
    void* ctx_;
};

// Display model: line buffer the screen renders. MCU-friendly (no heap churn).
struct DisplayModel {
    static const int ROWS = 4;
    static const int COLS = 22;
    char lines[ROWS][COLS + 1];
    int active_row = 0;
    void clear_all();
    void set_line(int row, const char* txt);
    void scroll(int dir); // dir: -1 up, +1 down
};

} // namespace cyclops
#endif
