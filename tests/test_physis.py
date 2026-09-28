"""Offline tests for the two physis bridges.

Pinned here:
  * brain/physis.py — the LEGACY embedder adapter (physis-pro-web `/api/v1/embed`
    in FakePro; HashEmbedder fallback when nothing answers). physis-pro is
    retired; this surface stays tested because ConceptIndex can still use it.
  * brain/physis_next.py + /api/physis/* — the LIVE memory path: physis-next
    MCP over HTTP (POST /mcp, JSON-RPC 2.0, NDJSON) in FakeMCP.

No network, no model, no real physis binary required.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain import physis as physis_mod  # noqa: E402  (legacy embedder)
from brain.physis import PhysisEmbedder, PhysisUnavailable, best_embedder  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    "appserver_physis", os.path.join(REPO, "app", "server.py")
)
appserver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(appserver)

PRO_CALLS = {"n": 0}
MCP_CALLS: list[dict] = []


class FakePro(BaseHTTPRequestHandler):
    """physis-pro-web shape, reduced to the one route brain/physis.py keeps."""

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer dev-token":
            return self._send({"error": "unauthorized"}, 401)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        PRO_CALLS["n"] += 1
        if self.path == "/api/v1/embed":
            text = body.get("text", "")
            v = [float((len(text) + i) % 7) for i in range(8)]
            n = sum(x * x for x in v) ** 0.5 or 1.0
            return self._send({"embedding": [x / n for x in v], "dim": 8})
        return self._send({"error": "nope"}, 404)


class FakeMCP(BaseHTTPRequestHandler):
    """physis-next MCP-over-HTTP: POST /mcp, one JSON-RPC request, NDJSON body."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        req = json.loads(self.rfile.read(length) or b"{}")
        name = (req.get("params") or {}).get("name", "")
        args = (req.get("params") or {}).get("arguments", {})
        MCP_CALLS.append({"name": name, "args": args})
        if name == "physis.capabilities":
            structured = {"api_version": "physis.system.v1",
                          "workspace": "/tmp/fake-workspace"}
            text = "physis-next fake"
        elif name == "physis.search":
            structured = {"results": [{"score": 0.91, "entity_id": "file:hud.h",
                                       "snippet": "one button grid"}]}
            text = "0.91 file:hud.h one button grid"
        elif name == "physis.remember":
            structured = {"recorded": True, "outcome": args.get("outcome"),
                          "text": args.get("text")}
            text = "remembered"
        elif name == "physis.history":
            structured = {"rows": [{"summary": "hud bindings done"}]}
            text = "hud bindings done"
        elif name == "physis.predict":
            structured = {"runs": [], "failure_rate": 0.0}
            text = "no prior runs"
        else:
            structured, text = {}, "unknown tool"
        body = json.dumps({"jsonrpc": "2.0", "id": req.get("id"),
                           "result": {"content": [{"type": "text", "text": text}],
                                      "structuredContent": structured,
                                      "isError": False}}) + "\n"
        raw = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def _serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _url(srv) -> str:
    return f"http://127.0.0.1:{srv.server_address[1]}"


def _env(**kw):
    old = dict(os.environ)
    for k, v in kw.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return old


def _restore(old):
    os.environ.clear()
    os.environ.update(old)


# ------------------------------------------------------- legacy bridge (embed)

def test_embed_roundtrip():
    srv = _serve(FakePro)
    old = _env(PHYSIS_URL=_url(srv), PHYSIS_API_TOKEN="dev-token")
    try:
        vec = physis_mod.embed("hello")
        assert len(vec) == 8 and abs(sum(x * x for x in vec) - 1.0) < 1e-6
    finally:
        _restore(old)
        srv.shutdown()


def test_auth_failure_surfaces():
    srv = _serve(FakePro)
    old = _env(PHYSIS_URL=_url(srv), PHYSIS_API_TOKEN="wrong")
    try:
        try:
            physis_mod.embed("hello")
            assert False, "expected PhysisUnavailable"
        except PhysisUnavailable:
            pass
    finally:
        _restore(old)
        srv.shutdown()


def test_unconfigured_falls_back_to_hash():
    old = _env(PHYSIS_URL=None, PHYSIS_API_TOKEN=None)
    try:
        from brain.concepts import HashEmbedder

        assert isinstance(best_embedder(), HashEmbedder)
    finally:
        _restore(old)


def test_unreachable_falls_back_to_hash():
    old = _env(PHYSIS_URL="http://127.0.0.1:1", PHYSIS_API_TOKEN="x")
    try:
        from brain.concepts import HashEmbedder

        assert isinstance(best_embedder(timeout=1.0), HashEmbedder)
    finally:
        _restore(old)


def test_physis_embedder_caches():
    srv = _serve(FakePro)
    old = _env(PHYSIS_URL=_url(srv), PHYSIS_API_TOKEN="dev-token")
    try:
        PRO_CALLS["n"] = 0
        pe = PhysisEmbedder()
        a, b = pe.embed("same text"), pe.embed("same text")
        assert a == b and PRO_CALLS["n"] == 1, PRO_CALLS
        assert pe.dim == 8
    finally:
        _restore(old)
        srv.shutdown()


def test_concept_search_with_remote_embedder():
    from brain.concepts import ConceptIndex
    from brain.extractor import Note
    from brain.store import NoteStore

    srv = _serve(FakePro)
    old = _env(PHYSIS_URL=_url(srv), PHYSIS_API_TOKEN="dev-token")
    path = tempfile.mktemp(suffix=".jsonl")
    try:
        st = NoteStore(path)
        st.add(Note(id="n0", type="task", text="ship the firmware by friday"))
        st.add(Note(id="n1", type="task", text="buy milk tomorrow"))
        hits = ConceptIndex(store=st, embedder=PhysisEmbedder()).search("firmware", k=2)
        assert hits and hits[0]["kind"] == "note"
    finally:
        _restore(old)
        srv.shutdown()
        os.remove(path)


# ------------------------------------------------ physis-next bridge (live path)

def test_next_client_status_and_search():
    from brain import physis_next as pn

    srv = _serve(FakeMCP)
    old = _env(PHYSIS_URL=_url(srv), PHYSIS_ROOT="/tmp/fake-workspace")
    try:
        st = pn.status()
        assert st["reachable"] is True, st
        assert st["workspace"] == "/tmp/fake-workspace", st
        hits = pn.search("hud", limit=3)
        assert hits and hits[0]["entity_id"] == "file:hud.h", hits
        assert MCP_CALLS[-1]["name"] == "physis.search"
        assert MCP_CALLS[-1]["args"]["limit"] == 3
    finally:
        _restore(old)
        srv.shutdown()


def test_next_client_unreachable_raises():
    from brain import physis_next as pn

    old = _env(PHYSIS_URL="http://127.0.0.1:1")
    try:
        try:
            pn.search("x", timeout=1.0)
            assert False, "expected PhysisNextUnavailable"
        except pn.PhysisNextUnavailable:
            pass
        st = pn.status(timeout=1.0)
        assert st["reachable"] is False and st["detail"], st
    finally:
        _restore(old)


def _cyclops(tmp):
    home = os.path.join(tmp, "home")
    os.makedirs(home, exist_ok=True)
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = home
    store = os.path.join(tmp, "notes.jsonl")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), appserver.H)
    appserver.STORE_PATH = store
    appserver.pipeline = appserver.build_pipeline(store_path=store)
    appserver.pipeline.store.clear()
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port, old_home


def test_api_physis_status_offline():
    old = _env(PHYSIS_URL="http://127.0.0.1:1")
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _cyclops(d)
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/physis/status", timeout=5) as r:
                body = json.loads(r.read())
            assert body["reachable"] is False, body
            assert body["transport"] == "mcp-http", body
        finally:
            srv.shutdown()
            _restore(old)
            if home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = home


def test_api_physis_search_and_remember():
    fake = _serve(FakeMCP)
    old = _env(PHYSIS_URL=_url(fake), PHYSIS_ROOT="/tmp/fake-workspace")
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _cyclops(d)
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/physis/search?q=hud&limit=2",
                    timeout=5) as r:
                body = json.loads(r.read())
            assert body["results"][0]["entity_id"] == "file:hud.h", body
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/physis/remember",
                data=json.dumps({"text": "one-button port", "outcome": "success",
                                 "actor": "test"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=5) as r:
                posted = json.loads(r.read())
            assert posted["recorded"] is True, posted
            assert MCP_CALLS[-1]["name"] == "physis.remember"
            assert MCP_CALLS[-1]["args"]["outcome"] == "success"
        finally:
            srv.shutdown()
            fake.shutdown()
            _restore(old)
            if home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = home


def test_api_physis_unreachable_is_503():
    old = _env(PHYSIS_URL="http://127.0.0.1:1")
    with tempfile.TemporaryDirectory() as d:
        srv, port, home = _cyclops(d)
        try:
            try:
                urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/physis/search?q=x", timeout=5)
                assert False, "expected 503"
            except urllib.error.HTTPError as e:
                assert e.code == 503, e.code
                body = json.loads(e.read())
                assert "unreachable" in body["error"], body
        finally:
            srv.shutdown()
            _restore(old)
            if home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = home


def test_agent_physis_tool_offline_is_honest():
    import agent.tools.physis as tp

    old = _env(PHYSIS_URL="http://127.0.0.1:1", PATH="/nonexistent")
    saved = tp._PHYSIS_BIN
    tp._PHYSIS_BIN = "/nonexistent/physis"
    try:
        tool = tp.make_physis_tool()
        assert tool.run({"action": "recall", "text": "hud"}).startswith("offline:")
        assert tool.run({"action": "remember", "text": "x",
                         "outcome": "success"}).startswith("offline:")
    finally:
        tp._PHYSIS_BIN = saved
        _restore(old)


def test_physis_mcp_cli_reports_offline():
    old = _env(PHYSIS_URL="http://127.0.0.1:1")
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO, "scripts", "physis_mcp.py"), "status"],
            capture_output=True, text=True, timeout=30)
        assert proc.returncode == 2, proc
        assert "unreachable" in (proc.stdout + proc.stderr), proc
    finally:
        _restore(old)


# ----------------------------------------------------- entity enrichment (local)

def test_enrich_off_by_default():
    from brain.pipeline import Pipeline
    from brain.store import NoteStore

    with tempfile.TemporaryDirectory() as d:
        home = os.path.join(d, "home")
        os.makedirs(home, exist_ok=True)
        old = _env(HOME=home, CYCLOPS_ENRICH_ENTITIES=None,
                   CYCLOPS_PHYSIS_ENRICH=None)
        try:
            store = NoteStore(os.path.join(d, "notes.jsonl"))
            Pipeline(store).process_text("ship the firmware by friday")
            assert len(store.all()) >= 1
            from brain.entities import EntityStore

            assert EntityStore().all() == []
        finally:
            _restore(old)


def _enrich_and_find(var: str, value: str) -> list[dict]:
    from brain.entities import EntityStore
    from brain.pipeline import Pipeline
    from brain.store import NoteStore

    with tempfile.TemporaryDirectory() as d:
        home = os.path.join(d, "home")
        os.makedirs(home, exist_ok=True)
        old = _env(HOME=home, **{var: value})
        try:
            store = NoteStore(os.path.join(d, "notes.jsonl"))
            Pipeline(store).process_text("ship the firmware by friday")
            return EntityStore().search("firmware")
        finally:
            _restore(old)


def test_enrich_tags_entities_locally():
    found = _enrich_and_find("CYCLOPS_ENRICH_ENTITIES", "1")
    assert any(r.get("key") == "firmware" for r in found), found


def test_enrich_legacy_env_alias_still_works():
    # docs/43 §9.4: CYCLOPS_PHYSIS_ENRICH stays accepted after the physis-pro
    # classifier it used to trigger was replaced by local keyword tagging.
    found = _enrich_and_find("CYCLOPS_PHYSIS_ENRICH", "1")
    assert any(r.get("key") == "firmware" for r in found), found


if __name__ == "__main__":
    test_embed_roundtrip()
    test_auth_failure_surfaces()
    test_unconfigured_falls_back_to_hash()
    test_unreachable_falls_back_to_hash()
    test_physis_embedder_caches()
    test_concept_search_with_remote_embedder()
    test_next_client_status_and_search()
    test_next_client_unreachable_raises()
    test_api_physis_status_offline()
    test_api_physis_search_and_remember()
    test_api_physis_unreachable_is_503()
    test_agent_physis_tool_offline_is_honest()
    test_physis_mcp_cli_reports_offline()
    test_enrich_off_by_default()
    test_enrich_tags_entities_locally()
    test_enrich_legacy_env_alias_still_works()
    print("ALL PHYSIS TESTS PASSED")
