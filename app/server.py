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

try:
    from app import media  # noqa: E402  captured-media store (images/audio/video)
except ImportError:  # launched from inside app/ (script dir on sys.path)
    import media  # type: ignore  # noqa: E402

STORE_PATH = os.path.expanduser("~/.cyclops/notes.jsonl")
PROFILE_PATH = os.path.expanduser("~/.cyclops/profile.json")
# Auto-save frames that pass through /api/vision into captures/images.
# On by default; set CYCLOPS_SAVE_CAPTURES=0 to disable.
SAVE_CAPTURES = os.environ.get("CYCLOPS_SAVE_CAPTURES", "1") != "0"
PORT = 8080
pipeline = None
agent = None
bridge = None
_vision_fn = None  # lazy-built plain (image_b64, prompt) -> str callable
# In-flight OAuth attempts (both device-flow and PKCE), keyed by provider
# name -- /api/oauth/poll needs the device_code/status from the matching
# /api/oauth/start call, but the client only has the provider name. One
# request server-does-one-poll design for device flow (see
# brain/oauth_device.py's poll_once docstring): a device code can be
# outstanding for ~15 min (RFC 8628), and a ThreadingHTTPServer request
# thread blocking that long per in-flight auth would be a real resource risk
# -- the phone re-polls on an interval instead, server does one upstream
# check per phone request. PKCE entries don't poll upstream at all --
# completion is event-driven from the browser hitting /api/oauth/callback,
# which just flips pending["status"].
_oauth_pending: dict = {}
# PKCE's redirect only carries back `state`, not the provider name -- this
# maps state -> provider so /api/oauth/callback can find the pending entry.
_oauth_state_index: dict = {}
# serializes access to the shared agent (ThreadingHTTPServer handles requests
# concurrently; agent.run() mutates history/cfg with no locking of its own)
_AGENT_LOCK = threading.Lock()
DREAM_INTERVAL_S = 1800  # background review cadence (30 min)


def _get_vision_fn():
    """Lazily build the (image_b64, prompt) -> str callable HudBridge uses
    to tag sightings (#1). Built once, cached module-level -- constructing
    a Tool + HTTP session per request would be wasteful given /api/hud_cmd
    already builds a throwaway HudBridge per call.

    NOTE: make_vision_tool()'s offline-stub check reads its own `session`
    parameter, not the `session or _urllib_session()` fallback it computes
    internally -- omitting session (as app/server.py's /api/vision handler
    does) leaves it permanently stubbed regardless of configured API keys.
    session must be passed explicitly to get a real vision backend, same as
    agent/tools/__init__.py's build_registry already does for every other
    tool wired into the conversational agent.
    """
    global _vision_fn
    if _vision_fn is None:
        from agent.models import _urllib_session
        from agent.tools.vision import make_vision_tool

        cfg = AgentConfig.load(env=dict(os.environ))
        tool = make_vision_tool(cfg, session=_urllib_session())
        _vision_fn = lambda b64, prompt: tool.run({"image": b64, "prompt": prompt})
    return _vision_fn


def _run_dream_review():
    """One dream/proposal review over recent notes + graded experiences.
    Uses the agent's router when available; falls back to rules offline."""
    from brain.dreams import review
    from brain.experiences import ExperienceStore

    notes = []
    try:
        if pipeline is not None and getattr(pipeline, "store", None):
            notes = [getattr(n, "text", "") for n in pipeline.store.all()][-15:]
    except Exception:
        pass
    domains = []
    try:
        domains = ExperienceStore().domains()
    except Exception:
        pass
    router = getattr(agent, "router", None) if agent is not None else None
    return review(notes, domains, router=router)


def _start_dream_scheduler():
    """Periodic background reviewer (AURA DreamEngine cadence). Daemon thread,
    swallows errors so a bad review never takes the server down."""

    def _loop():
        import time as _t

        while True:
            _t.sleep(DREAM_INTERVAL_S)
            try:
                _run_dream_review()
            except Exception:
                pass

    t = threading.Thread(target=_loop, name="cyclops-dreams", daemon=True)
    t.start()
    return t


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
        if p.path == "/health":
            # liveness probe: the companion app's status pill + the web
            # dashboard poll this. It never existed, so `configured` clients
            # showed "offline" even when the brain was up. (bug found 2026-07-13)
            return self._send(200, json.dumps({"ok": True}))
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
        if p.path == "/api/feed":
            # Unified reverse-chron activity stream (AURA sync-feed idea):
            # merge the events Cyclops already produces — notes, agent turns,
            # the last HUD banner — into one time-sorted list. Pure aggregation
            # over sources that already exist; nothing new is stored.
            limit = int((parse_qs(p.query).get("limit", ["50"])[0]) or 50)
            events = []
            try:
                if pipeline is not None and getattr(pipeline, "store", None):
                    for n in pipeline.store.all():
                        events.append(
                            {
                                "ts": getattr(n, "created", "") or "",
                                "kind": getattr(n, "type", "note"),
                                "message": getattr(n, "text", ""),
                            }
                        )
            except Exception:
                pass
            try:
                with _AGENT_LOCK:
                    hist = (
                        list(getattr(agent, "history", [])) if agent is not None else []
                    )
                for m in hist:
                    if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
                        c = m.get("content", "")
                        if isinstance(c, str) and c.strip():
                            events.append(
                                {"ts": "", "kind": m["role"], "message": c[:200]}
                            )
            except Exception:
                pass
            if bridge is not None and getattr(bridge, "last_banner", ""):
                events.append({"ts": "", "kind": "hud", "message": bridge.last_banner})
            try:
                from brain.dreams import DreamStore

                for d in DreamStore().active():
                    events.append(
                        {
                            "ts": d.get("ts", ""),
                            "kind": "dream",
                            "message": d.get("message", ""),
                        }
                    )
            except Exception:
                pass
            # newest first: dated events by timestamp desc, undated keep order
            events.sort(key=lambda e: e.get("ts") or "", reverse=True)
            return self._send(200, json.dumps(events[:limit]))
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
                    vision=_get_vision_fn(),
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
        if p.path == "/api/cost":
            # Per-provider token + estimated USD spend (merlin CostTracker).
            try:
                from agent.cost import CostTracker

                return self._send(200, json.dumps(CostTracker().summary()))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        if p.path == "/api/experiences":
            # graded self-review log (AURA/Praxis PDCA); optional ?domain= filter
            from brain.experiences import ExperienceStore

            dom = parse_qs(p.query).get("domain", [""])[0]
            store = ExperienceStore()
            rows = store.for_domain(dom) if dom else store.all()
            return self._send(200, json.dumps(list(reversed(rows))))
        if p.path == "/api/domains":
            from brain.experiences import ExperienceStore

            return self._send(200, json.dumps(ExperienceStore().domains()))
        if p.path == "/api/dreams":
            # active proactive insights/proposals (the "dream" loop)
            from brain.dreams import DreamStore

            return self._send(200, json.dumps(DreamStore().active()))
        if p.path == "/api/entities":
            # deduplicated registry of seen things (AURA EntityStore)
            from brain.entities import EntityStore

            etype = parse_qs(p.query).get("type", [""])[0]
            return self._send(200, json.dumps(EntityStore().all(etype)))
        if p.path == "/api/entities/search":
            from brain.entities import EntityStore

            q = parse_qs(p.query).get("q", [""])[0]
            return self._send(200, json.dumps(EntityStore().search(q)))
        if p.path == "/api/oauth/providers":
            # Device-flow-capable providers the user has configured (see
            # brain/oauth_store.py's load_provider_configs -- reads
            # ~/.cyclops/oauth_providers.json, user-supplied, not committed).
            # Never returns client secrets, just names -- the app shows a picker.
            from brain.oauth_store import load_provider_configs

            names = sorted(load_provider_configs().keys())
            return self._send(200, json.dumps(names))
        if p.path == "/api/oauth/catalog":
            # The curated provider picker (GitHub/OpenRouter/Google/...) --
            # see brain/oauth_catalog.py for what's real vs. unsupported and
            # why. redirect_uri is derived from this request's own Host
            # header so it's correct for whatever host:port this install is
            # actually reached at (LAN IP, hostname, adb-reverse tunnel).
            from brain.oauth_catalog import CATALOG
            from brain.oauth_store import OAuthStore

            connected = set(OAuthStore().available_providers())
            host = self.headers.get("Host", "")
            out = []
            for entry in CATALOG:
                e = dict(entry)
                e["connected"] = e["id"] in connected
                if e.get("needs_client_id") and host:
                    e["redirect_uri"] = f"http://{host}/api/oauth/callback"
                out.append(e)
            return self._send(200, json.dumps(out))
        if p.path == "/api/oauth/callback":
            # Browser lands here after the user approves on the provider's
            # site (PKCE/openrouter flows only -- device flow has no
            # redirect). Exchanges the code server-side and flips the
            # matching _oauth_pending entry's status; the phone discovers
            # the result via its next /api/oauth/poll, same as device flow.
            qs = parse_qs(p.query)
            state = qs.get("state", [""])[0]
            provider = _oauth_state_index.pop(state, None)
            pending = _oauth_pending.get(provider) if provider else None
            if not pending:
                return self._send(400, "Unknown or expired sign-in request. Close this tab and try again.", "text/html")
            if qs.get("error"):
                pending["status"] = "denied"
                return self._send(200, "Sign-in was denied. You can close this tab.", "text/html")
            code = qs.get("code", [""])[0]
            from brain.oauth_device import (
                OAuthError,
                exchange_openrouter_code,
                exchange_pkce_code,
            )
            from brain.oauth_store import OAuthStore

            try:
                if pending["flow"] == "openrouter":
                    tok = exchange_openrouter_code(code, pending["code_verifier"], pending["session"])
                else:
                    tok = exchange_pkce_code(
                        pending["cfg"], code, pending["redirect_uri"],
                        pending["code_verifier"], pending["session"],
                    )
            except OAuthError as e:
                pending["status"] = "error"
                pending["error"] = str(e)
                return self._send(200, f"Sign-in failed: {e}. You can close this tab.", "text/html")
            OAuthStore().save(provider, tok.access_token, tok.refresh_token, tok.expires_in)
            pending["status"] = "complete"
            return self._send(200, "Connected — you can close this tab.", "text/html")
        if p.path == "/api/oauth/poll":
            # One poll attempt for a provider with an in-flight
            # /api/oauth/start (see _oauth_pending). Non-blocking by design.
            provider = parse_qs(p.query).get("provider", [""])[0]
            pending = _oauth_pending.get(provider)
            if not pending:
                return self._send(404, json.dumps({"status": "not_started"}))
            if pending["flow"] in ("pkce", "openrouter"):
                # Event-driven from /api/oauth/callback, not an upstream
                # poll -- there's nothing to ask the provider until the
                # browser redirect has happened.
                status = pending.get("status", "pending")
                if status in ("complete", "denied", "expired"):
                    _oauth_pending.pop(provider, None)
                    return self._send(200, json.dumps({"status": status}))
                if status == "error":
                    _oauth_pending.pop(provider, None)
                    return self._send(200, json.dumps({"status": "error", "error": pending.get("error", "")}))
                return self._send(200, json.dumps({"status": "pending", "retry_after": 2}))
            from brain.oauth_device import poll_once
            from brain.oauth_store import OAuthStore

            try:
                r = poll_once(
                    pending["cfg"], pending["device_code"], pending["session"],
                    default_interval=pending["interval"],
                )
            except Exception as e:
                _oauth_pending.pop(provider, None)
                return self._send(200, json.dumps({"status": "error", "error": str(e)}))
            if r.status == "complete":
                OAuthStore().save(
                    provider, r.token.access_token, r.token.refresh_token, r.token.expires_in
                )
                _oauth_pending.pop(provider, None)
                return self._send(200, json.dumps({"status": "complete"}))
            if r.status in ("expired", "denied"):
                _oauth_pending.pop(provider, None)
                return self._send(200, json.dumps({"status": r.status}))
            # RFC 8628 3.5: on slow_down, use the bumped interval going
            # forward, not just for this one response.
            pending["interval"] = r.retry_after
            return self._send(200, json.dumps({"status": "pending", "retry_after": r.retry_after}))
        if p.path == "/api/sightings":
            # Zero-photo memory (#1): "when did I last see my keys" queries
            # the text-tag log, never a photo library. ?q= filters; omitted
            # returns everything, newest last (same order as the JSONL).
            from brain.sightings import SightingLog

            q = parse_qs(p.query).get("q", [""])[0]
            log = SightingLog()
            return self._send(200, json.dumps(log.search(q) if q else log.all()))
        if p.path == "/api/status":
            # Glanceable HUD state for the companion mirror (and the wearable
            # status frame shape, t=8). Reflects the brain's own view when no
            # device is streaming, so the HUD mirror is never a dead demo.
            note_count = 0
            try:
                if pipeline is not None and getattr(pipeline, "store", None):
                    note_count = len(pipeline.store.all())
            except Exception:
                pass
            b = bridge
            from brain.hitl import get_gatebook

            gate = get_gatebook().latest_pending()
            st = {
                "t": 8,
                "rec": 1 if (b and b.recording) else 0,
                "mode": (b.mode if b else "HOME"),
                "notes": note_count,
                "banner": (b.last_banner if b else ""),
                "online": True,
                "gate": gate.to_dict() if gate else None,
            }
            return self._send(200, json.dumps(st))
        if p.path == "/api/media":
            # ?cat=images|audio|video -> newest-first listing for that folder.
            cat = parse_qs(p.query).get("cat", ["images"])[0]
            try:
                return self._send(200, json.dumps(media.list_media(cat)))
            except ValueError as e:
                return self._send(400, json.dumps({"error": str(e)}))
        if p.path == "/api/media/counts":
            return self._send(200, json.dumps(media.counts()))
        if p.path.startswith("/media/"):
            # /media/<cat>/<name> -> raw bytes with the right content-type.
            parts = p.path.split("/", 3)  # ['', 'media', cat, name]
            if len(parts) == 4:
                got = media.read_media(parts[2], parts[3])
                if got is not None:
                    raw, mime = got
                    return self._send(200, raw, mime)
            return self._send(404, json.dumps({"error": "not found"}))
        self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        p = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        if p.path == "/api/oauth/start":
            # Begin an OAuth authentication, either against an already-
            # configured provider ({"provider": "kimi"}, the original
            # hand-edited-oauth_providers.json path) or a catalog entry
            # ({"catalog_id": "github", "client_id": "...", "client_secret"?:
            # "..."} -- the GUI picker path, see brain/oauth_catalog.py).
            # Does NOT block waiting for the user to complete it in a
            # browser -- returns the code/URL to show immediately; the app
            # polls /api/oauth/poll?provider=... afterward.
            from brain.oauth_device import OAuthError, ProviderConfig, start_device_flow
            from brain.oauth_store import load_provider_configs, save_provider_config

            provider = data.get("provider", "")
            catalog_id = data.get("catalog_id", "")
            if catalog_id:
                from brain.oauth_catalog import get as catalog_get

                entry = catalog_get(catalog_id)
                if entry is None or entry["flow"] == "unsupported":
                    return self._send(404, json.dumps({"error": f"unknown or unsupported provider: {catalog_id}"}))
                provider = catalog_id
                client_id = data.get("client_id", "")
                client_secret = data.get("client_secret", "")
                if entry.get("needs_client_id") and not client_id:
                    return self._send(400, json.dumps({"error": "client_id required"}))
                cfg = ProviderConfig(
                    name=provider,
                    device_auth_url=entry.get("device_auth_url", ""),
                    token_url=entry.get("token_url", ""),
                    client_id=client_id,
                    scope=entry.get("scope", ""),
                    api_base_url=entry.get("api_base_url", ""),
                    flow=entry["flow"],
                    authorize_url=entry.get("authorize_url", ""),
                    client_secret=client_secret,
                )
                if client_id:  # remember it for next time (refresh, reconnect)
                    save_provider_config(
                        provider, device_auth_url=cfg.device_auth_url, token_url=cfg.token_url,
                        client_id=client_id, scope=cfg.scope, api_base_url=cfg.api_base_url,
                        flow=cfg.flow, authorize_url=cfg.authorize_url,
                        client_secret=client_secret or None,
                    )
            else:
                cfg = load_provider_configs().get(provider)
                if cfg is None:
                    return self._send(404, json.dumps({"error": f"unknown provider: {provider}"}))

            from agent.models import _urllib_session

            session = _urllib_session()

            if cfg.flow in ("pkce", "openrouter"):
                from brain.oauth_device import (
                    build_openrouter_authorize_url,
                    build_pkce_authorize_url,
                    generate_pkce_pair,
                    generate_state,
                )

                redirect_uri = f"http://{self.headers.get('Host', '')}/api/oauth/callback"
                verifier, challenge = generate_pkce_pair()
                state = generate_state()
                if cfg.flow == "openrouter":
                    # OpenRouter's callback_url has no separate `state`
                    # concept (see oauth_device.py) -- embed our own
                    # correlation token in the callback_url's query string
                    # instead, so /api/oauth/callback can find this pending
                    # entry the same way it does for standard PKCE (which
                    # gets `state` echoed back per the OAuth2 spec).
                    authorize_url = build_openrouter_authorize_url(
                        f"{redirect_uri}?state={state}", challenge
                    )
                else:
                    authorize_url = build_pkce_authorize_url(cfg, redirect_uri, state, challenge)
                _oauth_pending[provider] = {
                    "flow": cfg.flow,
                    "cfg": cfg,
                    "session": session,
                    "code_verifier": verifier,
                    "redirect_uri": redirect_uri,
                    "status": "pending",
                }
                _oauth_state_index[state] = provider
                return self._send(200, json.dumps({"flow": cfg.flow, "authorize_url": authorize_url}))

            try:
                dc = start_device_flow(cfg, session)
            except OAuthError as e:
                return self._send(200, json.dumps({"error": str(e)}))
            _oauth_pending[provider] = {
                "flow": "device",
                "cfg": cfg,
                "device_code": dc.device_code,
                "session": session,
                "interval": dc.interval,
            }
            return self._send(
                200,
                json.dumps(
                    {
                        "flow": "device",
                        "user_code": dc.user_code,
                        "verification_uri": dc.verification_uri,
                        "verification_uri_complete": dc.verification_uri_complete,
                        "expires_in": dc.expires_in,
                        "interval": dc.interval,
                    }
                ),
            )
        if p.path == "/api/oauth/disconnect":
            from brain.oauth_store import OAuthStore

            provider = data.get("provider", "")
            OAuthStore().clear(provider)
            return self._send(200, json.dumps({"ok": True}))
        if p.path == "/api/experience":
            # record a graded experience: {domain, action, grade(0..1), note}
            from brain.experiences import ExperienceStore

            row = ExperienceStore().record(
                data.get("domain", "general"),
                data.get("action", ""),
                float(data.get("grade", 0.0) or 0.0),
                data.get("note", ""),
            )
            return self._send(200, json.dumps(row))
        if p.path == "/api/dream/review":
            try:
                return self._send(200, json.dumps({"dreams": _run_dream_review()}))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
        if p.path == "/api/dream/dismiss":
            from brain.dreams import DreamStore

            return self._send(
                200, json.dumps({"ok": DreamStore().dismiss(data.get("id", ""))})
            )
        if p.path == "/api/entity":
            # upsert-and-increment a seen entity: {name, type, note}
            from brain.entities import EntityStore

            r = EntityStore().touch(
                data.get("name", ""), data.get("type", "thing"), data.get("note", "")
            )
            return self._send(200, json.dumps(r))
        if p.path == "/api/vision":
            # Describe an image: {"image": "<data:base64|url>", "prompt": "..."}.
            # Uses the agent's vision tool (offline-safe stub → local/cloud VLM).
            img = data.get("image", "")
            # Record the frame to captures/images so the Files tab has history.
            # Only inline data (base64/data:) is saved, never a remote URL.
            saved = None
            if SAVE_CAPTURES and img and not img.lstrip().lower().startswith(("http://", "https://")):
                try:
                    saved = media.save_media(img, cat="images")
                except Exception:
                    saved = None
            try:
                out = _get_vision_fn()(
                    img,
                    data.get("prompt", "Describe this image concisely."),
                )
                return self._send(200, json.dumps({"result": out, "saved": saved}))
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)}))
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
        if p.path == "/api/media":
            # Explicit capture push: {"data":"data:<mime>;base64,..."|"<b64>",
            #                         "cat"?:images|audio|video, "ext"?:"jpg"}.
            # cat/ext are inferred from a data: URL's MIME when omitted.
            try:
                entry = media.save_media(
                    data.get("data", ""), cat=data.get("cat"), ext=data.get("ext")
                )
                return self._send(200, json.dumps({"ok": True, "file": entry}))
            except ValueError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            except Exception as e:
                return self._send(500, json.dumps({"error": str(e)}))
        if p.path == "/api/capture":
            # Record the wearable's stream to SD-style captures via ffmpeg:
            # {"cat":"audio"|"video", "url":"http://<device>/stream", "secs":5}.
            try:
                entry = media.capture_stream(
                    data.get("url", ""),
                    data.get("cat", "video"),
                    data.get("secs", 5),
                )
                return self._send(200, json.dumps({"ok": True, "file": entry}))
            except ValueError as e:
                return self._send(400, json.dumps({"error": str(e)}))
            except RuntimeError as e:
                return self._send(502, json.dumps({"error": str(e)}))
            except Exception as e:
                return self._send(500, json.dumps({"error": str(e)}))
        self._send(404, json.dumps({"error": "not found"}))

    def log_message(self, *a):
        pass


def main():
    global pipeline, agent, bridge, PORT, STORE_PATH
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
    with _AGENT_LOCK:
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

    with _AGENT_LOCK:
        bridge = HudBridge(
            _NullSink(),
            store=store,
            transcriber=getattr(pipeline, "trans", None) if pipeline else None,
            health=None,
            agent=agent,
            vision=_get_vision_fn(),
        )
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    # LAN discovery beacon so clients can find us without typing an IP.
    # Convenience only: a taken UDP port degrades to "no beacon", never blocks.
    from brain.discovery import DiscoveryBeacon

    beacon = DiscoveryBeacon(http_port=PORT)
    if beacon.start():
        print(f"Discovery beacon on udp/{beacon.listen_port}")
    _start_dream_scheduler()  # periodic proactive review (dreams/proposals)
    print(f"Cyclops dashboard on http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        beacon.stop()


if __name__ == "__main__":
    main()
