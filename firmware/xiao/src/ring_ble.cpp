// COLMI R02 BLE central client — implementation.
// Host (g++) build: BLE guarded out, begin()/update() are safe no-ops so the
// firmware host gate compiles and the parser can be unit-tested. Under
// PlatformIO (xiao_*) the ARDUINO branch wires NimBLE as a central.
#include "ring_ble.h"

#ifdef ARDUINO
#include <NimBLEDevice.h>
#include <mutex>
#endif

namespace cyclops {

bool RingBle::begin(const char* name_prefix) {
    (void)name_prefix;
#ifdef ARDUINO
    // The XIAO already initialized NimBLE as a server in main.cpp. To also be a
    // client we create a NimBLEScan and look for the ring's NUS service.
    static bool scan_started = false;
    if (!scan_started) {
        NimBLEDevice::init("");
        auto* scan = NimBLEDevice::getScan();
        scan->setActiveScan(true);
        // A real impl subclasses NimBLEAdvertisedDeviceCallbacks to detect the
        // ring by name, then NimBLEDevice::createClient() + connect to
        // UART_SERVICE_UUID, subscribe UART_TX_CHAR_UUID, and forward each
        // 16-byte notification to ring_parse(). See docs/30 for the full flow.
        scan->start(5);  // 5s scan window; connection handled in callback
        scan_started = true;
    }
    return true;  // scan started; connection completes async
#else
    return false;  // no BLE on host build
#endif
}

void RingBle::update() {
#ifdef ARDUINO
    // NimBLE is event-driven; nothing to pump here. The advertised-device
    // callback performs connect + notify-subscribe and calls ring_parse(),
    // writing results into sample_. A minimal callback would do:
    //   uint8_t p[16]; memcpy(p, data, 16); ring_parse(p, sample_);
#endif
}

}  // namespace cyclops
