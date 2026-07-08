#ifndef CYCLOPS_PROTOCOL_V2_H
#define CYCLOPS_PROTOCOL_V2_H
#include <cstdint>
#include "../protocol.h"

namespace cyclops { namespace v2 {

enum MsgV2 : uint8_t {
    MSG_PEER_HELLO = 11,
    MSG_TIME_SYNC = 12,
    MSG_HEALTH_SAMPLE = 13,
    MSG_HUD_FRAME = 14,
    MSG_RING_GESTURE = 15,
    MSG_AUDIO_COMPRESSED = 16,
    MSG_CONFIRM = 17,
    MSG_PEER_STATUS = 18,
};

// Build a compact HUD frame payload (max 4 lines, 18 chars each).
// Returns bytes written into out (JSON-ish, but we use a fixed minimal format).
size_t build_hud_frame(uint8_t kind, const char* lines[4], int nlines,
                       bool more, uint8_t* out, size_t cap);

// Parse a HEALTH_SAMPLE JSON payload into fields. Returns true if parsed.
bool parse_health(const uint8_t* p, size_t n, int64_t& t, int& hr,
                  int& spo2, int& sleep_stage, int& batt_mv);

// Ring gesture enum
enum RingGesture : uint8_t { RING_TAP=0, RING_DOUBLE=1, RING_LONG=2, RING_SWIPE=3 };

}} // namespace
#endif
