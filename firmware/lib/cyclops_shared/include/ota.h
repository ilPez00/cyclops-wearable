// Cyclops OTA-over-BLE — host-testable receive state machine (no esp_ota deps).
//
// Firmware updates ride the existing frame protocol (cyclops_shared.h):
//   phone -> device  MSG_OTA_BEGIN  {size, crc32, chunk} announces an image
//   phone -> device  MSG_OTA_CHUNK  [seq:u32-le][data...] streams it in order
//   phone -> device  MSG_OTA_END    (empty) requests finalize/verify
//   device -> phone  MSG_OTA_ACK    {"seq":n,"st":code} flow-control + result
//
// OtaReceiver owns the bookkeeping (expected size, sequential seq, running
// CRC32, accumulated length) and delegates the actual partition writes to
// injected sinks, so the whole thing compiles + tests on the host with g++.
// The XIAO wires the sinks to esp_ota_*; host tests wire them to a buffer.
#ifndef CYCLOPS_OTA_H
#define CYCLOPS_OTA_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>

namespace cyclops {

// ---- CRC32 (IEEE 802.3, poly 0xEDB88320, reflected) — matches zlib/Python. ----
inline uint32_t crc32_ieee(const uint8_t* d, size_t n, uint32_t crc = 0xFFFFFFFFu) {
    for (size_t i = 0; i < n; ++i) {
        crc ^= d[i];
        for (int b = 0; b < 8; ++b)
            crc = (crc & 1u) ? (crc >> 1) ^ 0xEDB88320u : (crc >> 1);
    }
    return crc;
}
// Finalize a streamed CRC32 (XOR-out). Feed running value from crc32_ieee().
inline uint32_t crc32_final(uint32_t running) { return running ^ 0xFFFFFFFFu; }

// ACK status codes (device -> phone, byte in MSG_OTA_ACK json "st").
enum OtaStatus : uint8_t {
    OTA_OK          = 0,   // begin accepted / chunk stored / image verified
    OTA_BUSY        = 1,   // a session is already active
    OTA_BAD_STATE   = 2,   // chunk/end arrived with no active session
    OTA_BAD_SEQ     = 3,   // out-of-order / duplicate chunk
    OTA_OVERFLOW    = 4,   // chunk would exceed announced size
    OTA_SIZE_MISMATCH = 5, // end: bytes received != announced size
    OTA_CRC_MISMATCH  = 6, // end: computed CRC32 != announced CRC32
    OTA_FLASH_ERR   = 7,   // an injected sink reported failure
};

// Parameters parsed from MSG_OTA_BEGIN. Kept binary (little-endian) so the
// phone can pack it without a JSON encoder in the hot path.
//   bytes[0..3]  total image size   (u32-le)
//   bytes[4..7]  image CRC32        (u32-le, finalized IEEE)
//   bytes[8..11] chunk size         (u32-le, informational)
struct OtaBegin {
    uint32_t size = 0;
    uint32_t crc32 = 0;
    uint32_t chunk = 0;
    // Parse a 12-byte (or longer) BEGIN payload. Returns false if too short.
    bool parse(const uint8_t* p, size_t n) {
        if (n < 12) return false;
        size  = (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
        crc32 = (uint32_t)p[4] | (uint32_t)p[5] << 8 | (uint32_t)p[6] << 16 | (uint32_t)p[7] << 24;
        chunk = (uint32_t)p[8] | (uint32_t)p[9] << 8 | (uint32_t)p[10] << 16 | (uint32_t)p[11] << 24;
        return size > 0;
    }
};

// Injected side-effects. On the XIAO these call esp_ota_begin/write/end +
// esp_ota_set_boot_partition. In tests they append to a buffer. All return
// true on success; a false return trips OTA_FLASH_ERR and aborts the session.
struct OtaSink {
    // begin(size) -> ready to receive `size` bytes.
    bool (*begin)(uint32_t size, void* ctx) = nullptr;
    // write(data,len) -> persist the next contiguous span.
    bool (*write)(const uint8_t* data, size_t len, void* ctx) = nullptr;
    // finish(commit) -> close the image; commit=true marks it bootable.
    bool (*finish)(bool commit, void* ctx) = nullptr;
    void* ctx = nullptr;
};

// The receive state machine. One image at a time; chunks must be strictly
// sequential starting at seq 0. Not thread-safe (drive it from the BLE cb).
class OtaReceiver {
public:
    explicit OtaReceiver(const OtaSink& sink) : sink_(sink) {}

    bool active() const { return active_; }
    uint32_t received() const { return got_; }
    uint32_t expected() const { return begin_.size; }

    // MSG_OTA_BEGIN handler. Returns an OtaStatus; sets *ack_seq to 0.
    OtaStatus on_begin(const uint8_t* p, size_t n, uint32_t* ack_seq) {
        if (ack_seq) *ack_seq = 0;
        if (active_) return OTA_BUSY;
        OtaBegin b;
        if (!b.parse(p, n)) return OTA_SIZE_MISMATCH;
        begin_ = b;
        got_ = 0; next_seq_ = 0; crc_ = 0xFFFFFFFFu;
        if (sink_.begin && !sink_.begin(b.size, sink_.ctx)) return OTA_FLASH_ERR;
        active_ = true;
        return OTA_OK;
    }

    // MSG_OTA_CHUNK handler. Payload = [seq:u32-le][data...].
    // *ack_seq is set to the chunk's seq so the phone can pace the stream.
    OtaStatus on_chunk(const uint8_t* p, size_t n, uint32_t* ack_seq) {
        if (ack_seq) *ack_seq = next_seq_;
        if (!active_) return OTA_BAD_STATE;
        if (n < 4) return OTA_BAD_SEQ;
        uint32_t seq = (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
        if (ack_seq) *ack_seq = seq;
        if (seq != next_seq_) return OTA_BAD_SEQ;    // out-of-order or dup
        const uint8_t* data = p + 4;
        size_t dlen = n - 4;
        if (got_ + dlen > begin_.size) { abort(); return OTA_OVERFLOW; }
        if (dlen && sink_.write && !sink_.write(data, dlen, sink_.ctx)) { abort(); return OTA_FLASH_ERR; }
        crc_ = crc32_ieee(data, dlen, crc_);
        got_ += (uint32_t)dlen;
        next_seq_++;
        return OTA_OK;
    }

    // MSG_OTA_END handler. Verifies size + CRC32, commits on success.
    OtaStatus on_end(uint32_t* ack_seq) {
        if (ack_seq) *ack_seq = next_seq_;
        if (!active_) return OTA_BAD_STATE;
        if (got_ != begin_.size) { abort(); return OTA_SIZE_MISMATCH; }
        if (crc32_final(crc_) != begin_.crc32) { abort(); return OTA_CRC_MISMATCH; }
        bool ok = !sink_.finish || sink_.finish(true, sink_.ctx);
        active_ = false;
        return ok ? OTA_OK : OTA_FLASH_ERR;
    }

    // Tear down an in-flight session (flash discarded, not committed).
    void abort() {
        if (active_ && sink_.finish) sink_.finish(false, sink_.ctx);
        active_ = false; got_ = 0; next_seq_ = 0; crc_ = 0xFFFFFFFFu;
    }

    // Build a MSG_OTA_ACK json body. Returns length written.
    static int ack_json(char* out, size_t cap, uint32_t seq, OtaStatus st) {
        return snprintf(out, cap, "{\"seq\":%u,\"st\":%u}", (unsigned)seq, (unsigned)st);
    }

private:
    OtaSink sink_;
    OtaBegin begin_;
    bool active_ = false;
    uint32_t got_ = 0;
    uint32_t next_seq_ = 0;
    uint32_t crc_ = 0xFFFFFFFFu;
};

} // namespace cyclops
#endif // CYCLOPS_OTA_H
