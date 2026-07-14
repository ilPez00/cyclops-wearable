"""Cyclops web dashboard — stdlib http.server, zero dependencies.

Serves notes + transcripts via a small JSON API and a live HTML page.
Usage:  python3 app/server.py [port] [store_path]
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

REPO = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, REPO)
from agent.config import AgentConfig  # noqa: E402
from agent.loop import Agent  # noqa: E402
from agent.tools import build_registry  # noqa: E402
from brain.factory import build_pipeline  # noqa: E402
from brain.store import NoteStore  # noqa: E402

STORE_PATH = os.path.expanduser("~/.cyclops/notes.jsonl")
PROFILE_PATH = os.path.expanduser("~/.cyclops/profile.json")
PORT = 8080
pipeline = None
agent = None
bridge = None
# serializes access to the shared agent (ThreadingHTTPServer handles requests
# concurrently; agent.run() mutates history/cfg with no locking of its own)
_AGENT_LOCK = threading.Lock()

_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
_HTML: str | None = None


def _load_html() -> str:
    global _HTML
    if _HTML is None:
        try:
            with open(_TEMPLATE_PATH) as f:
                _HTML = f.read()
        except FileNotFoundError:
            _HTML = "<html><body><h1>Cyclops</h1><p>template missing</p></body></html>"
    return _HTML


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/" or p.path == "/index.html":
            return self._send(200, _load_html(), "text/html")
        if p.path == "/api/notes":
            notes = [n.to_dict() for n in pipeline.store.all()] if pipeline else []
            return self._send(200, json.dumps(notes))
        if p.path == "/api/search":
            q = parse_qs(p.query)
            query = q.get("q", [""])[0]
            k = int(q.get("k", ["5"])[0] or 5)
            res = pipeline.store.search(query, k=k) if pipeline else []
            return self._send(200, json.dumps([n.to_dict() for n in res]))
        if p.path == "/api/ingest":
            q = parse_qs(p.query)
            text = q.get("text", [""])[0]
            if text and pipeline:
                pipeline.process_text(text)
            return self._send(200, json.dumps({"ok": True}))
        if p.path == "/api/transcript":
            # in-session conversation turns (role/content) from the running agent
            global agent
            with _AGENT_LOCK:
                hist = list(getattr(agent, "history", [])) if agent is not None else []
            out = [
                {"role": m.get("role", ""), "content": m.get("content", "")}
                for m in hist
                if isinstance(m, dict)
            ]
            return self._send(200, json.dumps(out))
        if p.path == "/api/extract":
            # LLM-aware extraction of arbitrary text -> candidate notes (premortem #5)
            q = parse_qs(p.query)
            text = q.get("text", [""])[0]
            if not text:
                return self._send(400, json.dumps({"error": "missing text"}))
            from brain.extractor import get_extractor

            extr = get_extractor()
            notes = extr.extract(text) if hasattr(extr, "extract") else extr(text)
            return self._send(200, json.dumps([n.to_dict() for n in notes]))
        if p.path == "/api/chat":
            # Thin LLM chat endpoint backed by the AI-stack key store.
            q = parse_qs(p.query)
            text = q.get("text", [""])[0]
            if not text:
                return self._send(400, json.dumps({"error": "missing text"}))
            from brain.llm_extractor import LLMClient, LLMClientError

            try:
                client = LLMClient()
                reply = client.complete([{"role": "user", "content": text}])
                return self._send(200, json.dumps({"reply": reply}))
            except LLMClientError as e:
                # no LLM configured (or endpoint missing) — degrade cleanly
                return self._send(
                    200,
                    json.dumps(
                        {"reply": None, "error": "no LLM configured", "detail": str(e)}
                    ),
                )
            except Exception as e:
                return self._send(200, json.dumps({"reply": None, "error": str(e)}))
        if p.path == "/api/agent":
            # Full agent router: text -> tools (terminal/whatsapp/media/device/brain) -> model.
            q = parse_qs(p.query)
            text = q.get("text", [""])[0]
            if not text:
                return self._send(400, json.dumps({"error": "missing text"}))
            try:
                # honor per-request local/transport/persona/provider toggles from the app
                cfg = AgentConfig.load(env=dict(os.environ))
                if q.get("local", ["0"])[0] in ("1", "true", "yes"):
                    cfg.local_mode = True
                if q.get("transport", [""])[0] in ("wifi", "bt", "cable"):
                    cfg.device_transport = q["transport"][0]
                persona = q.get("persona", [""])[0].strip()
                if persona:
                    cfg.system_note = persona
                # per-call provider/endpoint/key (the companion-app settings UI)
                if q.get("provider", [""])[0]:
                    cfg.provider = q["provider"][0]
                if q.get("endpoint", [""])[0]:
                    if cfg.local_mode:
                        cfg.local_base_url = q["endpoint"][0]
                    else:
                        cfg.base_url = q["endpoint"][0]
                if q.get("api_key", [""])[0]:
                    cfg.api_key = q["api_key"][0]
                reg = build_registry(cfg)
                # build a fresh agent when per-call config differs (persona/provider),
                # otherwise reuse the shared instance (which already pushes HUD).
                use_shared = not (
                    persona
                    or q.get("provider", [""])[0]
                    or q.get("endpoint", [""])[0]
                    or q.get("api_key", [""])[0]
                )
                if use_shared and agent is not None:
                    with _AGENT_LOCK:
                        res = agent.run(text)
                else:
                    res = Agent(cfg, registry=reg).run(text)
                # push the glanceable answer to the wearable HUD (Omi/G2 style)
                if bridge is not None:
                    try:
                        bridge.push_hud(res.text or "")
                    except Exception:
                        pass
                return self._send(
                    200,
                    json.dumps(
                        {
                            "text": res.text,
                            "tool_calls": res.tool_calls,
                            "steps": res.steps,
                        }
                    ),
                )
            except Exception as e:
                return self._send(200, json.dumps({"text": None, "error": str(e)}))
        if p.path == "/api/hud_cmd":
            # Fulfill a wearable MSG_CMD locally (transcribe/translate/health/...).
            q = parse_qs(p.query)
            act = int(q.get("a", ["0"])[0])
            arg = q.get("arg", [""])[0]
            try:
                from brain.hud_bridge import HudBridge

                class _Cap:
                    def __init__(self):
                        self.frames = []

                    def write(self, b):
                        self.frames.append(b)

                cap = _Cap()
                br = HudBridge(
                    cap,
                    store=getattr(pipeline, "store", None) if pipeline else None,
                    transcriber=getattr(pipeline, "trans", None) if pipeline else None,
                    health=None,
                )
                res = br.dispatch(act, arg)
                return self._send(
                    200,
                    json.dumps(
                        {
                            "action": res[0],
                            "frames": [
                                f.decode("latin1", "replace") for f in cap.frames
                            ],
                        }
                    ),
                )
            except Exception as e:
                return self._send(200, json.dumps({"action": None, "error": str(e)}))
        if p.path == "/api/settings":
            # current persisted profile (or defaults) for the companion UI
            cfg = (
                AgentConfig.load_json(PROFILE_PATH)
                if os.path.exists(PROFILE_PATH)
                else AgentConfig()
            )
            return self._send(200, json.dumps(cfg.to_dict()))
        if p.path == "/api/memory":
            # Hermes-style memory view: both targets with stable indices.
            try:
                from agent.memory import MemoryStore

                store = MemoryStore(AgentConfig.load(env=dict(os.environ)))
                out = {
                    "agent": [c.to_dict() for c in store.list("agent")],
                    "user": [c.to_dict() for c in store.list("user")],
                }
                return self._send(200, json.dumps(out))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        if p.path == "/api/learn":
            # Trigger a learning review of recent turns (the app's "Learn" btn).
            # Offline-safe: returns {"learned": 0} when no LLM is configured.
            try:
                from agent import learning as learning_mod
                from agent.memory import MemoryStore

                cfg = AgentConfig.load(env=dict(os.environ))
                store = MemoryStore(cfg)
                written = {"user": 0, "agent": 0}
                if agent is not None:
                    with _AGENT_LOCK:
                        hist = list(getattr(agent, "history", []))
                    written = learning_mod.learn_recent(
                        hist, store, router=agent.router
                    )
                return self._send(200, json.dumps({"learned": written}))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        p = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        if p.path == "/api/settings":
            # merge + persist the profile (persona, provider, per-tool overrides, ...)
            cfg = (
                AgentConfig.load_json(PROFILE_PATH)
                if os.path.exists(PROFILE_PATH)
                else AgentConfig()
            )
            # accept 'persona' as an alias for system_note (companion UI naming)
            if "persona" in data and "system_note" not in data:
                data["system_note"] = data.pop("persona")
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            # keep persona + system_note in sync (single source of truth)
            if getattr(cfg, "persona", ""):
                cfg.system_note = cfg.persona
            os.makedirs(os.path.dirname(PROFILE_PATH), exist_ok=True)
            cfg.save(PROFILE_PATH)
            # refresh the running agent to pick up the new profile
            global agent
            if agent is not None:
                try:
                    with _AGENT_LOCK:
                        agent.cfg = cfg
                except Exception:
                    pass
            return self._send(200, json.dumps({"ok": True, "profile": cfg.to_dict()}))
        if p.path == "/api/memory":
            # Manage memory: action=append|edit|delete, target=agent|user.
            from agent.memory import MemoryStore

            store = MemoryStore(AgentConfig.load(env=dict(os.environ)))
            action = (data.get("action") or "append").lower()
            target = (data.get("target") or "agent").lower()
            if target not in ("agent", "user"):
                return self._send(
                    400, json.dumps({"error": "target must be agent|user"})
                )
            try:
                if action == "append":
                    note = (data.get("note") or "").strip()
                    if not note:
                        return self._send(400, json.dumps({"error": "note required"}))
                    idx = store.append(note, target=target)
                    return self._send(
                        200, json.dumps({"ok": True, "index": idx, "target": target})
                    )
                if action in ("edit", "delete"):
                    idx = int(data.get("index", -1))
                    if action == "edit":
                        ok = store.edit(
                            idx, (data.get("note") or "").strip(), target=target
                        )
                    else:
                        ok = store.delete(idx, target=target)
                    return self._send(
                        200, json.dumps({"ok": ok, "target": target, "index": idx})
                    )
                return self._send(
                    400, json.dumps({"error": "action must be append|edit|delete"})
                )
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *a):
        pass


def main():
    global pipeline, agent, PORT, STORE_PATH
    if len(sys.argv) > 1:
        PORT = int(sys.argv[1])
    if len(sys.argv) > 2:
        STORE_PATH = sys.argv[2]
    store = NoteStore(STORE_PATH)
    # build_pipeline auto-selects cloud transcription + LLM extraction when the
    # AI-stack key store (/home/gio/ai_api.txt, ~/.env) provides credentials,
    # otherwise falls back to the deterministic local stub + rule engine.
    pipeline = build_pipeline(store_path=STORE_PATH)
    # Shared live context assembler (P2-B) — fused notes/health/calendar. The
    # ring/omi vitals are fed in via the health relay; here we start with the
    # agent's own note store so the fused block is never empty-crashes.
    from brain.context import ContextAssembler

    assembler = ContextAssembler()
    try:
        ns = NoteStore(STORE_PATH)
        assembler.add_notes([n for n in ns.all()][-20:])
    except Exception:
        pass
    # Agent core: Hermes-style loop with tools (terminal/whatsapp/media/device/brain).
    # Local-first; uses CYCLOPS_LOCAL / provider env to pick cloud vs local model.
    agent = Agent(
        AgentConfig.load(env=dict(os.environ)),
        registry=build_registry(AgentConfig.load(), context_assembler=assembler),
        context=assembler,
    )
    # HUD bridge: fulfills wearable MSG_CMD locally and pushes glanceable banners
    # back to the glasses. Wired with the agent so the device's AGENT command uses
    # the real core. Sink is a no-op here; the phone/BLE side swaps in a real writer.
    from brain.hud_bridge import HudBridge

    class _NullSink:
        def write(self, b):
            pass

        def render_text(self, t):
            pass

    global bridge
    bridge = HudBridge(
        _NullSink(),
        store=store,
        transcriber=getattr(pipeline, "trans", None) if pipeline else None,
        health=None,
        agent=agent,
    )
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    # LAN discovery beacon so clients can find us without typing an IP.
    # Convenience only: a taken UDP port degrades to "no beacon", never blocks.
    from brain.discovery import DiscoveryBeacon

    beacon = DiscoveryBeacon(http_port=PORT)
    if beacon.start():
        print(f"Discovery beacon on udp/{beacon.listen_port}")
    print(f"Cyclops dashboard on http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        beacon.stop()


if __name__ == "__main__":
    main()
