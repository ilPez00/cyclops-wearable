// On-demand photo capture served over WiFi HTTP (#1, zero-photo memory).
// Camera + WiFi + a tiny HTTP server come up only when a photo is actually
// requested, and tear back down (WiFi off) after an idle window with no new
// request -- BLE's radio time is undisturbed the rest of the time, and no
// permanent WiFi/BLE coexistence overhead is paid for a feature that fires
// a few times an hour at most.
//
// WiFi credentials come from /sdcard/wifi.txt (line 1 = SSID, line 2 =
// password). If the file or the SD card itself is absent, this feature is
// simply unavailable -- same "everything stubs without config" convention
// as the rest of Cyclops (see brain/aikeys.py for the same idea server-side).
#ifndef CAMERA_CAPTURE_H
#define CAMERA_CAPTURE_H
namespace cyclops {

class CameraCapture {
public:
    // idle_ms: how long with no new request before WiFi + the HTTP server
    // tear back down.
    explicit CameraCapture(unsigned long idle_ms = 60000) : idle_ms_(idle_ms) {}

    // Bring up (lazily, on first call) camera + WiFi + HTTP server, and
    // reset the idle-teardown timer. Safe to call repeatedly (e.g. once per
    // ACT_PHOTO while already up -- just re-arms the timer). Returns the
    // capture URL once ready, or "" if credentials are missing / the camera
    // or WiFi failed to come up.
    const char* request(unsigned long now);

    // Call every loop() tick. Tears WiFi + the HTTP server down (not the
    // camera driver itself -- cheap to leave initialized) once idle_ms_ has
    // passed since the last request.
    void tick(unsigned long now);

    bool ready() const { return server_up_; }

    // Immediate teardown regardless of the idle timer -- the off-body
    // privacy gate needs this to hold even mid-capture-window.
    void shutdown() { teardown_wifi(); }

private:
    bool ensure_camera();
    bool ensure_wifi_and_server();
    void teardown_wifi();

    unsigned long idle_ms_;
    unsigned long last_request_ = 0;
    bool cam_ready_ = false;
    bool server_up_ = false;
    char url_[64] = "";
};

}  // namespace cyclops
#endif  // CAMERA_CAPTURE_H
