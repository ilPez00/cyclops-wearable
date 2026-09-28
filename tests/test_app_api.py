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


def test_health_endpoint_exists():
    # the app's status pill + web dashboard poll /health; it must be 200
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            st, body = _get(port, "/health")
            assert st == 200 and body.get("ok") is True
        finally:
            srv.shutdown()


def test_dashboard_html_served():
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            import urllib.request

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                html = r.read().decode()
            # branding case is a design choice (the redesign moved CYCLOPS ->
            # Cyclops); what this gate is really for is that the dashboard is
            # served and still wired to the feed API.
            assert "cyclops" in html.lower() and "/api/feed" in html
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


def test_api_notify_records_and_buzzes():
    # W7: the phone triages; the brain records the event and, when buzz is
    # set, puts the line on the HUD. A non-buzz must not set the banner.
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            body = json.dumps(
                {"line": "whatsapp: Marco ciao", "pkg": "com.whatsapp", "buzz": True}
            ).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/notify", data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                out = json.loads(r.read())
            assert out["ok"] is True
            # recorded as a note
            st, notes = _get(port, "/api/notes")
            assert any("Marco" in n["text"] for n in notes), notes
            # silence path: buzz=False must not touch the banner
            from brain.hud_bridge import HudBridge
            class _Null:
                def write(self, b): pass
                def render_text(self, t): pass
            appserver.bridge = HudBridge(_Null())
            appserver.bridge.last_banner = "before"
            body2 = json.dumps(
                {"line": "news: headline", "pkg": "com.news", "buzz": False}
            ).encode()
            req2 = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/notify", data=body2,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req2, timeout=5) as r:
                out2 = json.loads(r.read())
            assert out2["buzzed"] is False
            assert appserver.bridge.last_banner == "before"
        finally:
            srv.shutdown()


def test_api_claims_and_resolution():
    # W9: the wrist surface reads /api/claims; resolution posts keep_new.
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            from brain.claims import ClaimStore
            from brain.hud_bridge import HudBridge

            class _Null:
                def write(self, b): pass
                def render_text(self, t): pass

            cs = ClaimStore(os.path.join(d, "claims.jsonl"),
                            os.path.join(d, "revs.jsonl"))
            appserver.bridge = HudBridge(_Null(), claims=cs)
            appserver.bridge.note_claim("the meeting is moved to tuesday at ten")
            appserver.bridge.note_claim("the meeting is moved to tuesday at eleven")

            st, body = _get(port, "/api/claims")
            assert st == 200 and len(body["active"]) == 1
            assert body["contradiction"] is not None

            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/claims/resolve",
                data=json.dumps({"keep_new": False}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                out = json.loads(r.read())
            assert out["ok"] is True and out["kept"] is False
            assert out["claim"]["status"] == "active"
        finally:
            srv.shutdown()


def test_api_activity_records_sessions_as_ledger_events():
    # Phone activity (UsageStats tier): foreground sessions become ledger
    # events (type activity, source phone:<package>). <30s noise skipped,
    # empty package rejected.
    import urllib.request as _url
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            body = json.dumps({"sessions": [
                {"package": "com.maps", "label": "Maps",
                 "started_at": "2026-09-19T10:00:00+00:00", "duration_s": 125},
                {"package": "com.x", "duration_s": 5},
                {"package": "", "duration_s": 999},
            ]}).encode()
            req = _url.Request(
                f"http://127.0.0.1:{port}/api/activity", data=body,
                headers={"Content-Type": "application/json"},
            )
            with _url.urlopen(req, timeout=5) as r:
                out = json.loads(r.read())
            assert out == {"ok": True, "kept": 1}, out
            st, notes = _get(port, "/api/notes")
            acts = [n for n in notes if n.get("type") == "activity"]
            assert len(acts) == 1, notes
            assert acts[0]["source"] == "phone:com.maps"
            assert "Maps" in acts[0]["text"] and "2m 5s" in acts[0]["text"]
        finally:
            srv.shutdown()


def test_api_events_appends_to_the_ledger():
    """POST /api/events (docs/34 §1a): writers outside the brain post rows
    instead of appending the JSONL themselves — one writer per process."""
    import urllib.request as _url
    from brain.events import EventLog

    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            req = _url.Request(
                f"http://127.0.0.1:{port}/api/events",
                data=json.dumps({"kind": "step", "body": "took the 8:10 train",
                                 "duration_s": 900, "source": "app"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with _url.urlopen(req, timeout=5) as r:
                out = json.loads(r.read())
            assert out["kind"] == "step" and out["duration_s"] == 900.0, out
            # the ledger served by the app lives beside the store (temp dir here)
            log = EventLog(os.path.join(d, "events.jsonl"))
            assert [e.body for e in log.all()] == ["took the 8:10 train"]
            # a row with no kind is refused, not silently defaulted
            req2 = _url.Request(
                f"http://127.0.0.1:{port}/api/events",
                data=json.dumps({"body": "orphan"}).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                _url.urlopen(req2, timeout=5)
                assert False, "expected 400"
            except Exception as e:
                assert "400" in str(e), e
        finally:
            srv.shutdown()


def test_api_timeline_merges_ledger_and_stores():
    """docs/34 §4a: one time axis for events + notes + claims, each row keeping
    its source and locator (nothing presented as more than it is)."""
    import urllib.request as _url
    with tempfile.TemporaryDirectory() as d:
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            # an ingest writes both a note AND a ledger row (docs/34 §1b)
            _url.urlopen(f"http://127.0.0.1:{port}/api/ingest?text="
                         + urllib.parse.quote("Remind me to call Marco by friday"),
                         timeout=5).read()
            st, rows = _get(port, "/api/timeline")
            assert st == 200 and isinstance(rows, list) and rows, rows
            kinds = {r["kind"] for r in rows}
            assert "capture" in kinds, kinds          # from the event ledger
            assert "note" in kinds, kinds             # from the legacy store
            for r in rows:
                assert r["locator"], r                # provenance is never empty
                assert "duration_s" in r, r           # the field nothing may drop
            assert [r["ts"] for r in rows] == sorted(
                (r["ts"] for r in rows), reverse=True), rows
            st, few = _get(port, "/api/timeline?limit=1")
            assert st == 200 and len(few) == 1, few
        finally:
            srv.shutdown()


def test_api_device_reports_what_the_wearable_sent():
    """docs/43 §7: the Device tab reads the last MSG_STATUS frame — including the
    presence/posture bits added for C5 — and reports absence as absence."""
    import urllib.request as _url
    from brain.hud_bridge import HudBridge
    from brain.protocol import MSG

    class _Null:
        def write(self, b):
            pass

        def render_text(self, t):
            pass

    with tempfile.TemporaryDirectory() as d:
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = d
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            st, before = _get(port, "/api/device")
            assert st == 200 and before["device"]["linked"] is False, before

            appserver.bridge = HudBridge(_Null())
            appserver.bridge.dispatch(MSG["STATUS"], json.dumps(
                {"t": 8, "batt": 3900, "chg": 1, "rec": 0, "mode": "HOME",
                 "pres": 0, "pos": 1, "toast": "photo: no wifi.txt"}))
            st, body = _get(port, "/api/device")
            dev = body["device"]
            assert dev["linked"] is True, body
            assert dev["batt_mv"] == 3900 and dev["charging"] is True
            assert dev["presence"] is False and dev["posture"] == "slouch", dev
            assert dev["toast"].startswith("photo:")     # the firmware's own line
            assert body["capture"]["stream_path"] == "/stream"
            assert body["hud"]["hint"] == "tap:ok 2x:back hold:ask"
            assert "available" in body["ota"]

            # absence is never guessed
            appserver.bridge.last_status = {}
            st, body2 = _get(port, "/api/device")
            assert body2["device"]["presence"] is None
            assert body2["device"]["posture"] is None
            assert body2["device"]["batt_mv"] is None
        finally:
            srv.shutdown()
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home


def test_api_ask_cites_or_says_it_cannot():
    """docs/34 §4b: the answer must carry claim/event ids, and with no model the
    endpoint must cite what the ledger has instead of inventing prose."""
    import urllib.request as _url
    from brain.claims import ClaimStore
    from brain.hud_bridge import HudBridge

    class _Null:
        def write(self, b):
            pass

        def render_text(self, t):
            pass

    with tempfile.TemporaryDirectory() as d:
        old_home = os.environ.get("HOME")
        os.environ["HOME"] = d
        old_agent = appserver.agent
        srv, port = _start(os.path.join(d, "notes.jsonl"))
        try:
            appserver.agent = None                  # offline path first
            _url.urlopen(f"http://127.0.0.1:{port}/api/ingest?text="
                         + urllib.parse.quote("the bike lock code is 4417"),
                         timeout=5).read()

            st, body = _get(port, "/api/ask?q=" + urllib.parse.quote("bike lock"))
            assert st == 200
            assert body["degraded"] is True, body
            assert body["citations"], body          # evidence was retrieved
            assert body["cited"] is True, body      # ids echoed in the answer
            # every id in the answer is traceable to the row it came from, and a
            # note citation names its store + id
            assert body["citations"][0]["id"] in body["answer"], body["answer"]
            note_cite = next((c for c in body["citations"] if c["kind"] == "note"),
                             None)
            assert note_cite is not None, body
            assert note_cite["locator"].startswith("notes.jsonl#"), note_cite

            # nothing in the ledger matches -> honest miss, and cited=false
            st, miss = _get(port, "/api/ask?q=" + urllib.parse.quote("zeppelin"))
            assert st == 200 and miss["citations"] == [], miss
            assert miss["cited"] is False
            assert miss["note"], miss               # the UI is told to distrust

            # a claim is citable evidence too
            cs = ClaimStore(os.path.join(d, "claims.jsonl"),
                            os.path.join(d, "revs.jsonl"))
            appserver.bridge = HudBridge(_Null(), claims=cs)
            appserver.bridge.note_claim("the standup moved to 14:30")
            st, body2 = _get(port, "/api/ask?q=" + urllib.parse.quote("standup"))
            assert any(c["kind"] == "claim" for c in body2["citations"]), body2

            # missing q is a 400, not a silent empty answer
            try:
                _get(port, "/api/ask")
                assert False, "expected 400"
            except Exception as e:
                assert "400" in str(e), e
        finally:
            srv.shutdown()
            appserver.agent = old_agent
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
