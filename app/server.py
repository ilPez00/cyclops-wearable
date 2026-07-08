"""Cyclops web dashboard — stdlib http.server, zero dependencies.

Serves notes + transcripts via a small JSON API and a live HTML page.
Usage:  python3 app/server.py [port] [store_path]
"""
from __future__ import annotations
import sys, os, json, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

REPO = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, REPO)
from brain.store import NoteStore
from brain.pipeline import Pipeline
from brain.factory import build_pipeline
from brain.aikeys import AiKeys
from agent.config import AgentConfig
from agent.tools import build_registry
from agent.loop import Agent

STORE_PATH = os.path.expanduser("~/.cyclops/notes.jsonl")
PORT = 8080
pipeline = None
agent = None
bridge = None

HTML = """<!doctype html><html><head><meta charset=utf-8>
<title>Cyclops</title><style>
body{font-family:system-ui;background:#0e1116;color:#e6e6e6;margin:0;padding:1rem}
h1{font-size:1.1rem} .sec{margin-top:1rem} h2{font-size:.9rem;color:#7fd1ff;border-bottom:1px solid #222}
.note{padding:.3rem .5rem;margin:.2rem 0;background:#161b22;border-radius:6px;font-size:.85rem}
.due{color:#ffb454;font-size:.75rem} .live{color:#7CFFB2}
</style></head><body>
<h1>CYCLOPS <span class=live id=rec></span></h1>
<div id=last></div>
<div class=sec><h2>Tasks</h2><div id=task></div></div>
<div class=sec><h2>Reminders</h2><div id=reminder></div></div>
<div class=sec><h2>Decisions</h2><div id=decision></div></div>
<div class=sec><h2>Ideas</h2><div id=idea></div></div>
<div class=sec><h2>Summary</h2><div id=summary></div></div>
<script>
async function load(){
  const r=await fetch('/api/notes'); const d=await r.json();
  const by=t=>d.filter(n=>n.type===t);
  const render=(id,arr)=>document.getElementById(id).innerHTML=arr.map(n=>
    `<div class=note>${n.text}${n.due?`<span class=due> (due ${n.due})</span>`:''}</div>`).join('');
  ['task','reminder','decision','idea','summary'].forEach(t=>render(t,by(t)));
  document.getElementById('last').innerHTML = d.length?`<div class=note>last: ${d[d.length-1].text}</div>`:'';
}
setInterval(load,1500); load();
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, str): body = body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/" or p.path == "/index.html":
            return self._send(200, HTML, "text/html")
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
            if text and pipeline: pipeline.process_text(text)
            return self._send(200, json.dumps({"ok": True}))
        if p.path == "/api/extract":
            # LLM-aware extraction of arbitrary text -> candidate notes (premortem #5)
            q = parse_qs(p.query)
            text = q.get("text", [""])[0]
            if not text:
                return self._send(400, json.dumps({"error": "missing text"}))
            from brain.factory import build_extractor
            extr = build_extractor()
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
                return self._send(200, json.dumps(
                    {"reply": None, "error": "no LLM configured",
                     "detail": str(e)}))
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
                use_shared = not (persona or q.get("provider", [""])[0] or q.get("endpoint", [""])[0] or q.get("api_key", [""])[0])
                res = (agent if use_shared else Agent(cfg, registry=reg)).run(text)
                # push the glanceable answer to the wearable HUD (Omi/G2 style)
                if bridge is not None:
                    try: bridge.push_hud(res.text or "")
                    except Exception: pass
                return self._send(200, json.dumps({
                    "text": res.text,
                    "tool_calls": res.tool_calls,
                    "steps": res.steps,
                }))
            except Exception as e:
                return self._send(200, json.dumps({"text": None, "error": str(e)}))
        if p.path == "/api/hud_cmd":
            # Fulfill a wearable MSG_CMD locally (transcribe/translate/health/...).
            q = parse_qs(p.query)
            act = int(q.get("a", ["0"])[0]); arg = q.get("arg", [""])[0]
            try:
                from brain.hud_bridge import HudBridge
                from brain.protocol_v2 import encode, MSG
                class _Cap:
                    def __init__(self): self.frames = []
                    def write(self, b): self.frames.append(b)
                cap = _Cap()
                br = HudBridge(cap, store=getattr(pipeline, "store", None) if pipeline else None,
                               transcriber=getattr(pipeline, "trans", None) if pipeline else None,
                               health=None)
                res = br.dispatch(act, arg)
                return self._send(200, json.dumps({
                    "action": res[0], "frames": [f.decode("latin1", "replace") for f in cap.frames]}))
            except Exception as e:
                return self._send(200, json.dumps({"action": None, "error": str(e)}))
        self._send(404, json.dumps({"error": "not found"}))
    def log_message(self, *a): pass

def main():
    global pipeline, agent, PORT, STORE_PATH
    if len(sys.argv) > 1: PORT = int(sys.argv[1])
    if len(sys.argv) > 2: STORE_PATH = sys.argv[2]
    store = NoteStore(STORE_PATH)
    # build_pipeline auto-selects cloud transcription + LLM extraction when the
    # AI-stack key store (/home/gio/ai_api.txt, ~/.env) provides credentials,
    # otherwise falls back to the deterministic local stub + rule engine.
    pipeline = build_pipeline(store_path=STORE_PATH)
    # Agent core: Hermes-style loop with tools (terminal/whatsapp/media/device/brain).
    # Local-first; uses CYCLOPS_LOCAL / provider env to pick cloud vs local model.
    agent = Agent(AgentConfig.load(env=dict(os.environ)), registry=build_registry(AgentConfig.load()))
    # HUD bridge: fulfills wearable MSG_CMD locally and pushes glanceable banners
    # back to the glasses. Wired with the agent so the device's AGENT command uses
    # the real core. Sink is a no-op here; the phone/BLE side swaps in a real writer.
    from brain.hud_bridge import HudBridge
    class _NullSink:
        def write(self, b): pass
        def render_text(self, t): pass
    global bridge
    bridge = HudBridge(_NullSink(), store=store,
                       transcriber=getattr(pipeline, "trans", None) if pipeline else None,
                       health=None, agent=agent)
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    print(f"Cyclops dashboard on http://localhost:{PORT}")
    try: srv.serve_forever()
    except KeyboardInterrupt: srv.shutdown()

if __name__ == "__main__":
    main()
