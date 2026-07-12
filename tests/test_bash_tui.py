"""Bash TUI smoke: --once against a stub brain server. Offline, stdlib only."""

import http.server
import json
import os
import subprocess
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "shells", "cyclops.sh")


class StubBrain(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b'{"ok":true}'
        elif self.path.startswith("/api/notes"):
            body = json.dumps(
                [
                    {"type": "task", "text": "order encoder knobs", "due": "friday"},
                    {"type": "idea", "text": "wired uno pipeline"},
                ]
            ).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def _serve():
    srv = http.server.HTTPServer(("127.0.0.1", 0), StubBrain)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def test_once_mode_prints_status_and_notes():
    srv = _serve()
    try:
        out = subprocess.run(
            ["bash", SCRIPT, "--once"],
            env={**os.environ, "CYCLOPS_URL": f"http://127.0.0.1:{srv.server_port}"},
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert out.returncode == 0, out.stderr
        assert "online" in out.stdout
        assert "IDEA" in out.stdout and "wired uno pipeline" in out.stdout
        assert "TASK" in out.stdout and "due friday" in out.stdout
    finally:
        srv.shutdown()
    print("OK --once prints live status + formatted notes")


def test_once_mode_offline_says_offline():
    out = subprocess.run(
        ["bash", SCRIPT, "--once"],
        env={**os.environ, "CYCLOPS_URL": "http://127.0.0.1:9"},  # discard port
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert out.returncode == 0
    assert "offline" in out.stdout
    print("OK unreachable brain reads as offline, exit 0")


def test_help_shows_usage():
    out = subprocess.run(
        ["bash", SCRIPT, "--help"], capture_output=True, text=True, timeout=10
    )
    assert out.returncode == 0 and "--once" in out.stdout
    print("OK --help prints usage")
