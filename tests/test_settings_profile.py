"""Offline: T3.2 companion settings — per-tool overrides + profile persistence.

- AgentConfig.save/load_json round-trips tool_overrides (persona, provider, key).
- ModelRouter.chat honors a per-tool override (provider/model/endpoint/key) via a
  fake session that records the request it would have made (no network).
- Brain server /api/settings GET/POST merges + persists a profile (uses stdlib
  BaseHTTPRequestHandler via a live ThreadingHTTPServer on a free port).
"""
import json
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.config import AgentConfig
from agent.models import ChatResult, ModelRouter


def test_profile_roundtrip():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "profile.json")
    cfg = AgentConfig(system_note="be terse", provider="groq",
                      tool_overrides={"vision": {"provider": "openai", "model": "gpt-4o"},
                                      "web_search": {"model": "sonar"}})
    cfg.save(p)
    cfg2 = AgentConfig.load_json(p)
    assert cfg2.system_note == "be terse"
    assert cfg2.provider == "groq"
    assert cfg2.tool_overrides["vision"]["model"] == "gpt-4o"
    assert cfg2.tool_overrides["web_search"]["model"] == "sonar"
    print("OK profile round-trips with per-tool overrides")


def test_router_per_tool_override():
    class FakeSession:
        def __init__(s): s.calls = []
        def post(s, url, data=None, headers=None, timeout=0):
            s.calls.append((url, data, headers))
            class R:
                def json(self): return {"choices":[{"message":{"content":"ok","tool_calls":[]}}]}
            return R()
    sess = FakeSession()
    cfg = AgentConfig(provider="groq", api_key="sk-base",
                      tool_overrides={"vision": {"provider": "openai", "model": "gpt-4o",
                                                 "endpoint": "https://api.openai.com/v1",
                                                 "key": "sk-vision"}})
    r = ModelRouter(cfg, session=sess)
    # a vision tool call should hit openai endpoint with the vision key + model
    r.chat([{"role": "user", "content": "x"}], tool="vision")
    url, payload, headers = sess.calls[0]
    assert "api.openai.com/v1/chat/completions" in url, url
    assert json.loads(payload)["model"] == "gpt-4o"
    assert headers["Authorization"] == "Bearer sk-vision"
    # a non-overridden tool call falls back to base config
    r.chat([{"role": "user", "content": "y"}], tool="web_search")
    url2, payload2, headers2 = sess.calls[1]
    assert "openrouter.ai/api/v1" in url2, url2
    assert headers2["Authorization"] == "Bearer sk-base"
    print("OK router applies per-tool override, else base config")


def test_server_settings_endpoint():
    # live stdlib server on a free port, POST a profile then GET it back
    from http.server import ThreadingHTTPServer

    import app.server as srv  # main() is guarded, safe to import
    d = tempfile.mkdtemp(); prof = os.path.join(d, "profile.json")
    srv.PROFILE_PATH = prof
    srv.pipeline = None; srv.agent = None; srv.bridge = None
    import socket
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); free = s.getsockname()[1]
    httpd = ThreadingHTTPServer(("127.0.0.1", free), srv.H)
    t = threading.Thread(target=httpd.serve_forever, daemon=True); t.start()
    try:
        import urllib.request
        body = json.dumps({"system_note": "p", "provider": "groq",
                           "tool_overrides": {"vision": {"model": "gpt-4o"}}}).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{free}/api/settings", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        resp = json.loads(urllib.request.urlopen(req).read())
        assert resp["ok"] is True
        assert resp["profile"]["system_note"] == "p"
        got = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{free}/api/settings").read())
        assert got["provider"] == "groq"
        assert got["tool_overrides"]["vision"]["model"] == "gpt-4o"
    finally:
        httpd.shutdown()
    print("OK /api/settings GET/POST persists profile")


if __name__ == "__main__":
    test_profile_roundtrip()
    test_router_per_tool_override()
    test_server_settings_endpoint()
    print("PASS tests/test_settings_profile.py")
