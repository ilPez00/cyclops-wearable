// COLMI R02 BLE central client for the XIAO ESP32-S3 (NimBLE).
//
// The XIAO already runs a NimBLE *server* for the phone HUD link. NimBLE can
// also act as a *client* (central) on the same chip, so the wearable reads the
// ring directly — no phone needed for health metrics. This class wires the
// 16-byte ring protocol (ring_proto.h) to NimBLE and feeds hud.set_health().
//
// BLE code is guarded by ARDUINO so the host (g++) build only sees the parser
// + a no-op stub; the real link compiles under PlatformIO (xiao_* envs).
#ifndef RING_BLE_H
#define RING_BLE_H

#include "ring_proto.h"

#ifdef ARDUINO
#include <NimBLEDevice.h>
#include <string>
#endif

namespace cyclops {

class RingBle {
public:
    // Begin background connection to a ring by BLE name prefix (e.g. "R02_").
    // On the XIAO this starts a NimBLE scan + central connect; on host builds
    // nothing (offline-safe). Returns false if BLE is unavailable.
    bool begin(const char* name_prefix = "R02_");

    // Pump the BLE stack. Call from the main loop (XIAO). Host: no-op.
    // Performs the async connect + starts real-time HR/SpO2 streaming once the
    // ring is found.
    void update();

    // Latest decoded sample (HR / SpO2 / battery). Host-safe accessor.
    const RingSample& sample() const { return sample_; }

    bool connected() const { return connected_; }

    // Latest sample is "stale" if the ring is disconnected or no packet has
    // arrived for stale_after_ms_ (default 8s). The HUD uses this to show
    // "—" instead of a frozen HR/SpO2 after a drop. Host-safe accessor.
    bool stale() const { return !connected_ || (last_seen_ms_ != 0 &&
                              (now_ms() - last_seen_ms_) > stale_after_ms_); }
    void set_stale_after(unsigned ms) { stale_after_ms_ = ms; }

private:
    // --- ARDUINO-only connection state (declared here, defined in .cpp) ---
    static void on_ring_packet(const uint8_t* p);   // TX notify -> sample_
    static void on_disconnect();                     // reconnect on drop
    void start_scan();                               // (re)start peripheral scan

    RingSample sample_;
    bool connected_ = false;
#ifdef ARDUINO
    NimBLEClient* client_ = nullptr;
    NimBLERemoteCharacteristic* rx_ = nullptr;
    bool want_connect_ = false;
    NimBLEAddress pending_addr_ = NimBLEAddress("00:00:00:00:00:00");
    std::string prefix_ = "R02_";
    static RingBle* self_;     // back-pointer for static NimBLE callbacks
    // staleness + rescan bookkeeping (host-safe; only used under ARDUINO)
    unsigned last_seen_ms_ = 0;
    unsigned stale_after_ms_ = 8000;
    unsigned rescan_at_ms_ = 0;
    static const unsigned RESCAN_COOLDOWN_MS = 10000;
    // now_ms() is millis() under ARDUINO; returns 0 on host so staleness
    // math stays harmless (stale() then depends only on connected_).
    static unsigned now_ms();
    void mark_seen() { last_seen_ms_ = now_ms(); }
    void schedule_rescan() { rescan_at_ms_ = now_ms() + RESCAN_COOLDOWN_MS; }
#endif
};

}  // namespace cyclops

#endif  // RING_BLE_H
