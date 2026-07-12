"""Tests for F5 — companion app API + factory pipeline wiring (offline)."""

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

# load app/server.py as a module WITHOUT running main()
REPO = os.path.dirname(os.path.dirname(__file__))
spec = importlib.util.spec_from_file_location(
    "appserver", os.path.join(REPO, "app", "server.py")
)
appserver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(appserver)


def _start(tmp_store):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), appserver.H)
    appserver.STORE_PATH = tmp_store
    appserver.pipeline = appserver.build_pipeline(store_path=tmp_store)
    appserver.pipeline.store.clear()
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def _get(port, path):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
        return r.status, json.loads(r.read())


def test_api_notes_and_ingest():
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "notes.jsonl")
        srv, port = _start(store)
        try:
            st, body = _get(port, "/api/notes")
            assert st == 200 and isinstance(body, list)
            # ingest via query
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ingest?text="
                + urllib.parse.quote("Remind me to call Marco by friday"),
                timeout=5,
            ).read()
            st, body = _get(port, "/api/notes")
            assert any(n["type"] == "reminder" for n in body), body
        finally:
            srv.shutdown()


def test_api_status_reflects_brain_state():
    # HUD mirror polls /api/status; it used to 404 (HUD showed nothing).
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "notes.jsonl")
        srv, port = _start(store)
        try:
            st, body = _get(port, "/api/status")
            assert st == 200
            assert body["t"] == 8 and body["online"] is True
            assert body["mode"] == "HOME" and body["rec"] == 0
            assert "banner" in body and "notes" in body
        finally:
            srv.shutdown()


def test_api_vision_offline_safe():
    # Vision screen POSTs {image, prompt}; must degrade gracefully with no VLM.
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/vision",
                data=json.dumps({"image": "data:abc", "prompt": "what is this"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            body = json.loads(urllib.request.urlopen(req, timeout=5).read())
            assert "result" in body or "error" in body
            if "result" in body:
                assert "offline" in body["result"] or len(body["result"]) > 0
        finally:
            srv.shutdown()


def test_api_feed_aggregates_notes():
    # Unified activity stream: notes appear as feed events, newest first.
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "notes.jsonl")
        srv, port = _start(store)
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ingest?text="
                + urllib.parse.quote("call Marco by friday"),
                timeout=5,
            ).read()
            st, body = _get(port, "/api/feed")
            assert st == 200 and isinstance(body, list)
            assert body, "feed should contain the ingested note"
            e = body[0]
            assert "ts" in e and "kind" in e and "message" in e
            assert any("Marco" in x["message"] for x in body)
        finally:
            srv.shutdown()


def test_api_extract_returns_candidates_gracefully():
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "notes.jsonl")
        srv, port = _start(store)
        try:
            st, body = _get(
                port,
                "/api/extract?text="
                + urllib.parse.quote(
                    "We decided to launch on monday. Idea: add a vibration alert."
                ),
            )
            assert st == 200 and isinstance(body, list)
            types = {n["type"] for n in body}
            assert "decision" in types and "idea" in types, body
        finally:
            srv.shutdown()


def test_api_chat_degrades_without_key():
    # With no real LLM key configured for 'groq' in this isolated env the
    # chat endpoint must return 200 with an error field, never crash.
    with tempfile.TemporaryDirectory() as d:
        store = os.path.join(d, "notes.jsonl")
        srv, port = _start(store)
        try:
            st, body = _get(port, "/api/chat?text=hello")
            assert st == 200
            assert "reply" in body  # either a string or None+error
        finally:
            srv.shutdown()
