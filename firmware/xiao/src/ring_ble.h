// COLMI R02 BLE central client for the XIAO ESP32-S3 (NimBLE).
//
// The XIAO already runs a NimBLE *server* for the phone HUD link. NimBLE can
// also act as a *client* (central) on the same chip, so the wearable reads the
// ring directly — no phone needed for health metrics. This file wires the
// 16-byte ring protocol (ring_proto.h) to NimBLE and feeds hud.set_health().
//
// BLE code is guarded by ARDUINO so the host (g++) build only sees the parser
// + a no-op stub; the real link compiles under PlatformIO (xiao_* envs).
#ifndef RING_BLE_H
#define RING_BLE_H

#include "ring_proto.h"

namespace cyclops {

class RingBle {
public:
    // Begin background connection to a ring by BLE name prefix (e.g. "R02_").
    // On the XIAO this starts a NimBLE scan + central connect; on host builds
    // nothing (offline-safe). Returns false if BLE is unavailable.
    bool begin(const char* name_prefix = "R02_");

    // Pump the BLE stack. Call from the main loop (XIAO). Host: no-op.
    void update();

    // Latest decoded sample (HR / SpO2 / battery). Host-safe accessor.
    const RingSample& sample() const { return sample_; }

    bool connected() const { return connected_; }

private:
    RingSample sample_;
    bool connected_ = false;
};

}  // namespace cyclops

#endif  // RING_BLE_H
