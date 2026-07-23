import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from brain.sightings import SightingLog, _fetch, _resolve_allowed_ip, capture_and_tag


def _tmp_log():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    os.remove(path)  # SightingLog creates it lazily; start from "doesn't exist"
    return SightingLog(path)


def test_add_and_all():
    log = _tmp_log()
    assert log.all() == []
    e = log.add("desk, laptop, coffee cup", ts=1000.0)
    assert e["tags"] == "desk, laptop, coffee cup"
    assert log.all() == [e]


def test_search_is_case_insensitive_substring():
    log = _tmp_log()
    log.add("Office Desk, Laptop", ts=1)
    log.add("kitchen, stove, kettle", ts=2)
    assert len(log.search("desk")) == 1
    assert len(log.search("KETTLE")) == 1
    assert log.search("keys") == []


def test_search_empty_query_returns_nothing():
    log = _tmp_log()
    log.add("desk", ts=1)
    assert log.search("") == []
    assert log.search("   ") == []


def test_capture_and_tag_happy_path():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8FAKEJPEG\xff\xd9"
    vision = lambda b64, prompt: "desk, laptop, coffee cup"
    entry = capture_and_tag("http://device/capture", vision, log, fetch=fetch)
    assert entry is not None
    assert entry["tags"] == "desk, laptop, coffee cup"
    assert log.all() == [entry]


def test_capture_and_tag_discards_bytes_never_logs_image():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8REALJPEGBYTES\xff\xd9"
    vision = lambda b64, prompt: "kitchen"
    capture_and_tag("http://device/capture", vision, log, fetch=fetch)
    raw = log.path.read_text(encoding="utf-8")
    assert "REALJPEGBYTES" not in raw
    assert "kitchen" in raw


def test_capture_and_tag_fetch_failure_returns_none():
    log = _tmp_log()
    fetch = lambda url: None  # camera unreachable / offline
    vision = lambda b64, prompt: "should not be called"
    assert capture_and_tag("http://device/capture", vision, log, fetch=fetch) is None
    assert log.all() == []


def test_capture_and_tag_vision_exception_returns_none():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8x\xff\xd9"

    def boom(b64, prompt):
        raise RuntimeError("vision backend down")

    assert capture_and_tag("http://device/capture", boom, log, fetch=fetch) is None
    assert log.all() == []


def test_fetch_rejects_non_http_scheme():
    # firmware's ACT_PHOTO arg is relayed unauthenticated over
    # /api/hud_cmd?a=16&arg=<url> -- must reject file:// etc even if
    # something upstream forgets to validate.
    assert _fetch("file:///etc/passwd") is None
    assert _fetch("ftp://192.168.1.50/capture") is None


def test_fetch_rejects_loopback_and_link_local():
    # link-local specifically because 169.254.169.254 is the cloud metadata
    # endpoint on AWS/GCP/Azure -- the canonical SSRF target.
    assert _fetch("http://127.0.0.1/capture") is None
    assert _fetch("http://169.254.169.254/latest/meta-data/") is None


def test_fetch_rejects_public_host():
    assert _fetch("http://8.8.8.8/capture") is None


def test_resolve_allowed_ip_accepts_private_ranges():
    # the wearable's actual IP shape: DHCP-assigned on a private LAN
    assert _resolve_allowed_ip("192.168.1.50") == "192.168.1.50"
    assert _resolve_allowed_ip("10.0.0.5") == "10.0.0.5"
    assert _resolve_allowed_ip("172.16.0.5") == "172.16.0.5"


def test_resolve_allowed_ip_rejects_loopback_link_local_public():
    assert _resolve_allowed_ip("127.0.0.1") is None
    assert _resolve_allowed_ip("169.254.169.254") is None  # cloud metadata
    assert _resolve_allowed_ip("8.8.8.8") is None


def test_resolve_allowed_ip_rejects_unresolvable():
    assert _resolve_allowed_ip("this-does-not-resolve.invalid") is None


def test_fetch_does_not_follow_redirect_to_unvalidated_target():
    # A host that passes the IP-allow check but responds 3xx toward a
    # public/metadata target must not be transparently followed -- there is
    # no redirect-following here at all, any non-2xx is just a failure.
    # 127.0.0.1 is loopback and would normally be rejected by the allow
    # check itself; monkeypatch it through so this test isolates the
    # redirect behavior specifically, not the host check (covered above).
    import http.server
    import threading

    import brain.sightings as sightings

    class RedirectHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), RedirectHandler)
    port = srv.server_port
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    real_resolve = sightings._resolve_allowed_ip
    sightings._resolve_allowed_ip = lambda host: "127.0.0.1"
    try:
        assert _fetch(f"http://127.0.0.1:{port}/capture") is None
    finally:
        sightings._resolve_allowed_ip = real_resolve
        srv.shutdown()


def test_capture_and_tag_offline_or_error_stub_not_logged():
    log = _tmp_log()
    fetch = lambda url: b"\xff\xd8x\xff\xd9"
    vision = lambda b64, prompt: "offline: vision would analyze frame (12 b64 chars)"
    assert capture_and_tag("http://device/capture", vision, log, fetch=fetch) is None
    assert log.all() == []
