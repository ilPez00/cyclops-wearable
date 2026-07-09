// COLMI R02 smart ring — 16-byte packet protocol (host-testable, no BLE deps).
// Mirrors device/colmi_r02.py 1:1 so the XIAO firmware and the Python brain
// speak the exact same wire format. See docs/30-colmi-r02-integration.md.
//
// NUS-style service:
//   SERVICE  6E40FFF0-B5A3-F393-E0A9-E50E24DCCA9E
//   RX(write)  6E400002-B5A3-F393-E0A9-E50E24DCCA9E
//   TX(notify) 6E400003-B5A3-F393-E0A9-E50E24DCCA9E
// Packet: byte[0]=cmd (>=0x80 => error), byte[1..14]=subdata, byte[15]=CRC.
// CRC = sum(byte[0..14]) & 0xFF.
#ifndef RING_PROTO_H
#define RING_PROTO_H

#include <cstdint>

namespace cyclops {

// command tags
static const uint8_t RING_CMD_BATTERY          = 3;
static const uint8_t RING_CMD_READ_HEART_RATE  = 21;   // 0x15 daily log
static const uint8_t RING_CMD_START_REAL_TIME  = 105;
static const uint8_t RING_CMD_STOP_REAL_TIME   = 106;

// real-time reading kinds (packet byte[1] on START_REAL_TIME responses)
static const uint8_t RING_RT_HEART_RATE = 1;
static const uint8_t RING_RT_SPO2       = 3;

static const int RING_PACKET_LEN = 16;
static const uint8_t RING_ERROR_BIT = 0x80;

inline uint8_t ring_checksum(const uint8_t* p) {
    int s = 0;
    for (int i = 0; i < 15; i++) s += p[i];   // byte[15] is 0 while computing
    return (uint8_t)(s & 0xFF);
}

inline bool ring_is_valid(const uint8_t* p) {
    if (p[0] >= RING_ERROR_BIT) return false;       // ring error response
    return ring_checksum(p) == p[15];
}

// decoded live sample
struct RingSample {
    int hr = 0;
    int spo2 = 0;
    int battery = 0;
    bool charging = false;
};

// Parse one received TX packet into `out`. Returns true if it updated a field.
// Unknown/error packets are ignored (returns false) so callers can keep streaming.
inline bool ring_parse(const uint8_t* p, RingSample& out) {
    if (!ring_is_valid(p)) return false;
    switch (p[0]) {
        case RING_CMD_BATTERY:
            out.battery = p[1];
            out.charging = (p[2] != 0);
            return true;
        case RING_CMD_START_REAL_TIME: {
            uint8_t kind = p[1];
            if (p[2] != 0) return false;            // error code in byte[2]
            uint8_t val = p[3];
            if (kind == RING_RT_HEART_RATE) out.hr = val;
            else if (kind == RING_RT_SPO2)    out.spo2 = val;
            return true;
        }
        default:
            return false;                          // HR log / steps / unknown
    }
}

// Build a 16-byte request packet (cmd + up to 14 subdata bytes).
inline void ring_make_packet(uint8_t* out, uint8_t cmd, const uint8_t* sub = nullptr, int n = 0) {
    for (int i = 0; i < RING_PACKET_LEN; i++) out[i] = 0;
    out[0] = cmd;
    for (int i = 0; i < n && i < 14; i++) out[i + 1] = sub[i];
    out[15] = ring_checksum(out);
}

}  // namespace cyclops

#endif  // RING_PROTO_H
