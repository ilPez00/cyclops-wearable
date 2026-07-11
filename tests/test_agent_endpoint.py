"""Offline test for the server's /api/agent endpoint (no network/keys)."""

import json
import os
import sys
import tempfile
import threading
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import importlib.util
from http.server import ThreadingHTTPServer

REPO = os.path.dirname(os.path.dirname(__file__))
spec = importlib.util.spec_from_file_location(
    "appserver", os.path.join(REPO, "app", "server.py")
)
appserver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(appserver)

# Inject a fake Agent so no model/network is touched


class FakeAgent:
    def __init__(self, *a, **k):
        pass

    def run(self, text, images=None, audio_transcript=None):
        return type(
            "R",
            (),
            {
                "text": f"agent reply to: {text[:20]}",
                "tool_calls": 1,
                "steps": [
                    {
                        "tool": "device",
                        "args": {"action": "notes"},
                        "result": "[reminder] call marco",
                    }
                ],
            },
        )()


appserver.Agent = FakeAgent


def test_api_agent_returns_steps():
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "notes.jsonl")
        srv = ThreadingHTTPServer(("127.0.0.1", 0), appserver.H)
        appserver.STORE_PATH = store
        appserver.pipeline = appserver.build_pipeline(store_path=store)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            url = f"http://127.0.0.1:{port}/api/agent?text=" + urllib.parse.quote(
                "summarize my day"
            )
            with urllib.request.urlopen(url, timeout=5) as r:
                body = json.loads(r.read())
            assert body["text"].startswith("agent reply"), body
            assert body["tool_calls"] == 1
            assert body["steps"][0]["tool"] == "device"
        finally:
            srv.shutdown()
