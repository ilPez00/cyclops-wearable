// COLMI R02 BLE central client — implementation.
// Host (g++) build: BLE guarded out, begin()/update() are safe no-ops so the
// firmware host gate compiles and the parser can be unit-tested. Under
// PlatformIO (xiao_*) the ARDUINO branch wires NimBLE as a central client
// that connects to the ring's NUS service and streams HR/SpO2/battery into
// hud.set_health() (see docs/30 for the full flow).
#include "ring_ble.h"

#ifdef ARDUINO
#include <NimBLEDevice.h>
#endif

namespace cyclops {

#ifdef ARDUINO
// --- BLE plumbing (client side; the server is already up in main.cpp) -------
static const char* RING_SRVC = "6e40fff0-b5a3-f393-e0a9-e50e24dcca9e";
static const char* RING_RX   = "6e400002-b5a3-f393-e0a9-e50e24dcca9e";
static const char* RING_TX   = "6e400003-b5a3-f393-e0a9-e50e24dcca9e";
static const uint8_t RING_START_RT = 105, RING_STOP_RT = 106;
static const uint8_t RT_HR = 1, RT_SPO2 = 3;
#endif

RingBle* RingBle::self_ = nullptr;

bool RingBle::begin(const char* name_prefix) {
    (void)name_prefix;
#ifdef ARDUINO
    self_ = this;
    prefix_ = name_prefix ? name_prefix : "R02_";
    // main.cpp already did NimBLEDevice::init() for the server. Do NOT re-init;
    // just start a scan as a central. NimBLE supports server+client on one chip.
    static bool scan_started = false;
    if (!scan_started) {
        auto* scan = NimBLEDevice::getScan();
        scan->setActiveScan(true);
        scan->setInterval(100); scan->setWindow(80);
        class ScanCb : public NimBLEAdvertisedDeviceCallbacks {
            void onResult(NimBLEAdvertisedDevice* d) override {
                if (d->getName().rfind(self_->prefix_, 0) == 0) {  // name prefix
                    NimBLEDevice::getScan()->stop();
                    self_->want_connect_ = true;
                    self_->pending_addr_ = d->getAddress();
                }
            }
        };
        static ScanCb scb;
        scan->setAdvertisedDeviceCallbacks(&scb, false);
        scan->start(5, false);   // 5s window, don't restart
        scan_started = true;
    }
    return true;
#else
    return false;  // no BLE on host build
#endif
}

void RingBle::update() {
#ifdef ARDUINO
    if (!connected_ && want_connect_) {
        want_connect_ = false;
        client_ = NimBLEDevice::createClient();
        if (client_) {
            // subclass the callbacks (NimBLE uses virtual overrides, not lambdas)
            static class : public NimBLEClientCallbacks {
                void onDisconnect(NimBLEClient*) override { RingBle::on_disconnect(); }
            } cb;
            client_->setClientCallbacks(&cb);
        }
        if (client_ && client_->connect(pending_addr_)) {
            NimBLERemoteService* svc = client_->getService(RING_SRVC);
            if (svc) {
                NimBLERemoteCharacteristic* tx = svc->getCharacteristic(RING_TX);
                rx_ = svc->getCharacteristic(RING_RX);
                if (tx && rx_) {
                    tx->registerForNotify([](NimBLERemoteCharacteristic*,
                                             uint8_t* data, size_t len, bool) {
                        uint8_t pkt[RING_PACKET_LEN];
                        if (len >= RING_PACKET_LEN) {
                            memcpy(pkt, data, RING_PACKET_LEN);
                            RingBle::on_ring_packet(pkt);
                        }
                    });
                    connected_ = true;
                    // start real-time streaming: HR then SpO2
                    uint8_t req[16];
                    uint8_t rt_hr[2]  = {RT_HR, 1};
                    uint8_t rt_spo2[2] = {RT_SPO2, 1};
                    ring_make_packet(req, RING_START_RT, rt_hr, 2);
                    rx_->writeValue(req, false);
                    ring_make_packet(req, RING_START_RT, rt_spo2, 2);
                    rx_->writeValue(req, false);
                    return;
                }
            }
        }
        // connect failed: drop client, will rescan on next disconnect sweep
        if (client_) { NimBLEDevice::deleteClient(client_); client_ = nullptr; }
    }
#endif
}

#ifdef ARDUINO
void RingBle::on_ring_packet(const uint8_t* p) {
    if (self_) ring_parse(p, self_->sample_);
}

// Called from client callback on disconnect; triggers a rescan.
void RingBle::on_disconnect() {
    if (self_) {
        self_->connected_ = false;
        self_->client_ = nullptr;
        self_->want_connect_ = true;
    }
}
#endif

}  // namespace cyclops
