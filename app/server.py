"""Cyclops web dashboard — stdlib http.server, zero dependencies.

Serves notes + transcripts via a small JSON API and a live HTML page.
Usage:  python3 app/server.py [port] [store_path]
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
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

# ---------------------------------------------------------------------------
# Auth (premortem P0). This server binds 0.0.0.0 by design -- the phone is
# meant to reach it -- and POST /api/agent hands the caller an agent holding
# the terminal tool. Unauthenticated, that is remote code execution for anyone
# on the WiFi; /api/notes reads everything ever captured, and /api/settings can
# repoint provider/api_key/endpoint at an attacker's server. The SSRF guard in
# sightings.py was a locked window next to this open door.
#
# Model: the PEER decides, not the bind address. Loopback callers (the local
# dashboard, tests, adb-reverse tunnels) stay frictionless; anything arriving
# over the network must present the shared secret in ~/.cyclops/token as
# ?token=, the cyclops_token cookie, or the X-Cyclops-Token header.
# ---------------------------------------------------------------------------
TOKEN_PATH = os.path.expanduser("~/.cyclops/token")
TOKEN_HEADER = "X-Cyclops-Token"
TOKEN_COOKIE = "cyclops_token"
TOKEN = ""
# /health is a liveness probe returning only {"ok": true}. It stays open so
# discovery and the companion's status pill work before pairing.
OPEN_PATHS = {"/health"}
# Escape hatch for a network you already trust end-to-end. Loud on purpose.
ALLOW_INSECURE_LAN = os.environ.get("CYCLOPS_ALLOW_INSECURE_LAN") == "1"


def load_or_create_token() -> str:
    """The shared secret guarding every non-loopback request.

    Generated once, stored 0600, mirroring aion's ~/.aion/token. Override with
    CYCLOPS_TOKEN to share one secret across hosts without copying files.
    """
    env = os.environ.get("CYCLOPS_TOKEN", "").strip()
    if env:
        return env
    try:
        existing = open(TOKEN_PATH).read().strip()
        if existing:
            return existing
    except OSError:
        pass
    token = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)
    # right mode from the start -- never leave a world-readable window
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(token + "\n")
    return token
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


def _event_log():
    """The event ledger that belongs to the current store (same directory).

    Deriving the path from STORE_PATH keeps tests and multi-profile setups from
    writing into each other's ~/.cyclops — in the default deployment both are
    ~/.cyclops/events.jsonl, so the dashboard sees one ledger.
    """
    from brain.events import EventLog

    return EventLog(os.path.join(os.path.dirname(STORE_PATH), "events.jsonl"))


def _timeline_rows(limit: int = 60) -> list[dict]:
    """Timeline tab / /api/timeline (docs/34 §4a): the event ledger plus the
    legacy stores on ONE time axis. Every row carries source + locator, so the
    UI can show where it came from — nothing is presented as more than it is."""
    rows: list[dict] = []
    # 1. the ledger (docs/34 Phase 1a) — the preferred source
    try:
        for e in _event_log().recent(limit):
            d = e.to_dict()
            rows.append({"ts": d["ts"], "kind": d["kind"], "source": d["source"],
                         "body": d["body"], "duration_s": d["duration_s"],
                         "locator": d["locator"] or "events.jsonl"})
    except Exception:
        pass
    # 2. legacy stores, so the tab is useful before every writer emits Events
    #    (docs/34 §1b: migrate writers, not readers)
    try:
        for n in (pipeline.store.all() if pipeline is not None else []):
            rows.append({"ts": n.created or "", "kind": "note",
                         "source": n.source or "capture", "body": n.text,
                         "duration_s": 0.0, "locator": f"notes.jsonl#{n.id}",
                         "type": n.type, "due": n.due})
    except Exception:
        pass
    try:
        from brain.sightings import SightingLog

        for s in SightingLog().all():
            ts = s.get("ts", "")
            if isinstance(ts, (int, float)):      # epoch -> the same ISO shape
                import time as _t

                ts = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(float(ts)))
            rows.append({"ts": str(ts), "kind": "sighting", "source": "camera",
                         "body": str(s.get("tags", "")), "duration_s": 0.0,
                         "locator": "sightings.jsonl"})
    except Exception:
        pass
    try:
        if bridge is not None and getattr(bridge, "claims", None) is not None:
            for c in bridge.claims.all():
                rows.append({"ts": c.created_at, "kind": "claim", "source": "brain",
                             "body": c.statement, "duration_s": 0.0,
                             "locator": f"claims.jsonl#{c.id}", "status": c.status,
                             "confidence": round(c.confidence, 3)})
    except Exception:
        pass
    # ISO-8601 UTC sorts lexically; rows with no ts sink to the bottom.
    rows.sort(key=lambda r: r.get("ts") or "", reverse=True)
    return rows[:limit]


def _evidence_for(query: str, limit: int = 6) -> list[dict]:
    """Rows that could support an answer (docs/34 §4b). Retrieve FIRST, then let
    the model talk — an answer with no citation is a UI bug, not prose."""
    toks = [t for t in (query or "").lower().split() if len(t) > 2]
    out: list[dict] = []
    if bridge is not None and getattr(bridge, "claims", None) is not None:
        try:
            for c in bridge.claims.all():
                hay = c.statement.lower()
                if any(t in hay for t in toks):
                    out.append({"id": c.id, "kind": "claim", "text": c.statement,
                                "source": "brain", "locator": f"claims.jsonl#{c.id}",
                                "confidence": round(c.confidence, 3)})
        except Exception:
            pass
    try:
        for e in _event_log().search(query or "", limit=limit):
            out.append({"id": f"{e.locator or 'event'}@{e.ts}", "kind": e.kind,
                        "text": e.body or e.kind, "source": e.source,
                        "locator": e.locator or "events.jsonl"})
    except Exception:
        pass
    try:
        for n in (pipeline.store.search(query, k=3) if pipeline is not None else []):
            out.append({"id": n.id, "kind": "note", "text": n.text,
                        "source": n.source or "capture",
                        "locator": f"notes.jsonl#{n.id}"})
    except Exception:
        pass
    return out[:limit]


def _answer_question(text: str) -> dict:
    """Cited answer (docs/34 §4b). The model may only reason over the evidence it
    is handed; `cited` is False when it ignored it, and the UI must show that
    instead of hiding it as prose."""
    cites = _evidence_for(text)
    lines = [f"[{c['id']}] ({c['kind']}) {c['text']}" for c in cites]
    answer, error = None, None
    if agent is not None and lines:
        prompt = ("Answer using ONLY the evidence rows below. Cite every row you "
                  "use as [id]. If they do not answer the question, say so.\n\n"
                  f"question: {text}\n\nevidence:\n" + "\n".join(lines))
        try:
            with _AGENT_LOCK:
                res = agent.run(prompt)
            answer = getattr(res, "text", None)
        except Exception as e:
            error = str(e)
    degraded = not answer
    if degraded:
        # No model (or it failed): cite, never invent — same shape as the other
        # offline stubs, so the UI needs no special case.
        answer = ("no model configured" if agent is None
                  else f"model failed: {error}")
        answer += " — ledger only: " + ("; ".join(lines[:3]) if lines
                                        else "nothing matched")
    cited = any(c["id"] in answer for c in cites)
    return {"q": text, "answer": answer, "citations": cites, "cited": cited,
            "degraded": degraded, "error": error,
            "note": "" if cited else "answer carries no citation — unverified"}


def _firmware_image() -> dict:
    """OTA source image when a build exists on this box. The push itself is the
    APK's OtaSender over BLE (brain/ota_push.py); the dashboard only reports what
    is available, and where."""
    import glob
    import time as _t

    newest, best = 0.0, ""
    for pat in (os.path.join(REPO, "firmware", ".pio", "build", "*", "firmware.bin"),
                os.path.join(REPO, "firmware", "dist", "*.bin")):
        for path in glob.glob(pat):
            try:
                m = os.path.getmtime(path)
            except OSError:
                continue
            if m > newest:
                newest, best = m, path
    if not best:
        return {"available": False, "note": "build one: cd firmware && make compile"}
    return {"available": True, "path": os.path.relpath(best, REPO),
            "bytes": os.path.getsize(best),
            "built": _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime(newest))}


def _device_state() -> dict:
    """Device tab (docs/43 §7): the last status frame the wearable sent, the HUD
    mirror rows, the capture endpoints, and OTA availability. Everything is a
    frame we received or a file we can see — nothing is inferred."""
    st = dict(getattr(bridge, "last_status", {}) or {}) if bridge is not None else {}
    digest: list[str] = []
    try:
        digest = bridge.digest_lines(3) if bridge is not None else []
    except Exception:
        pass
    counts = {}
    try:
        counts = media.counts()
    except Exception:
        pass
    return {
        "device": {
            "linked": bool(st),
            "mode": st.get("mode") or (bridge.mode if bridge else "HOME"),
            "batt_mv": st.get("batt"),
            "charging": bool(st.get("chg")) if "chg" in st else None,
            "recording": bool(st.get("rec")) if "rec" in st else None,
            # docs/43 C5: these two are why the firmware grew pres/pos
            "presence": (None if "pres" not in st else bool(st.get("pres"))),
            "posture": (None if "pos" not in st
                        else ("slouch" if st.get("pos") else "ok")),
            "toast": st.get("toast") or "",
        },
        "hud": {
            "mode": (bridge.mode if bridge else "HOME"),
            "banner": (bridge.last_banner if bridge else ""),
            "digest": digest,
            "hint": "tap:ok 2x:back hold:ask",
            "recording": bool(bridge.recording) if bridge else False,
        },
        "capture": {
            "counts": counts,
            "status_path": "/status", "stream_path": "/stream",
            "audio_path": "/audio.wav", "snap_path": "/snap",
            "url_hint": "http://<wearable-ip>/stream",
        },
        "ota": _firmware_image(),
    }


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


CALENDAR_TICK_S = 60  # minute cadence: calendar triggers are minute-granular


def _calendar_tick(now=None) -> list[str]:
    """One W8 tick: read calendar.jsonl, compute due actions, apply them to
    the bridge (arm/file capture, leave nudge), persist state. Returns the
    human lines emitted. Safe to call with no calendar file (no-op)."""
    from brain.calendar_loop import (
        apply_actions,
        due_actions,
        load_events,
        load_state,
        save_state,
    )

    from datetime import datetime

    events = load_events()
    if not events:
        return []
    now = now or datetime.now()
    actions, st = due_actions(events, now, load_state())
    if not actions:
        return []
    lines = apply_actions(actions, bridge) if bridge is not None else []
    save_state(st)
    if pipeline is not None:
        for ln in lines:
            try:
                pipeline.process_text(ln)
            except Exception:
                pass
    return lines


def _start_calendar_scheduler():
    """Minute-cadence W8 loop. Daemon thread; a bad tick never takes the
    server down (same discipline as the dream scheduler)."""

    def _loop():
        import time as _t

        while True:
            _t.sleep(CALENDAR_TICK_S)
            try:
                _calendar_tick()
            except Exception:
                pass

    t = threading.Thread(target=_loop, name="cyclops-calendar", daemon=True)
    t.start()
    return t


_TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
_HTML: str | None = None


def _claim_store():
    """Process-wide belief store (34 Phase 2). Best-effort: a failure here
    leaves W9 off rather than taking the server down."""
    from brain.claims import ClaimStore

    return ClaimStore()


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
    def _send(self, code, body, ctype="application/json", headers=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    # ---- auth ------------------------------------------------------------
    def _peer_is_local(self) -> bool:
        try:
            return self.client_address[0] in ("127.0.0.1", "::1")
        except (AttributeError, IndexError):
            return False

    def _presented_token(self, query: str):
        """(token, came_from_url) -- query beats cookie beats header."""
        got = (parse_qs(query).get("token") or [""])[0]
        if got:
            return got, True
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == TOKEN_COOKIE and v:
                return v, False
        return self.headers.get(TOKEN_HEADER, ""), False

    def _authorized(self, p):
        """(ok, set_cookie) for a parsed URL. Loopback and /health are exempt."""
        if ALLOW_INSECURE_LAN or not TOKEN or self._peer_is_local():
            return True, False
        if p.path in OPEN_PATHS:
            return True, False
        got, from_url = self._presented_token(p.query)
        ok = hmac.compare_digest(got, TOKEN)
        return ok, (ok and from_url)

    def _deny(self):
        self._send(401, json.dumps(
            {"error": "unauthorized",
             "hint": "append ?token=<~/.cyclops/token> or send X-Cyclops-Token"}))

    def _cookie_header(self, set_cookie):
        if not set_cookie:
            return None
        # SameSite=Strict: a hostile page on the same WiFi cannot ride the
        # cookie into /api/agent.
        return {"Set-Cookie": f"{TOKEN_COOKIE}={TOKEN}; Path=/; "
                              "SameSite=Strict; Max-Age=31536000"}

    def do_GET(self):
        p = urlparse(self.path)
        ok, set_cookie = self._authorized(p)
        if not ok:
            return self._deny()
        if p.path == "/" or p.path == "/index.html":
            return self._send(200, _load_html(), "text/html",
                              headers=self._cookie_header(set_cookie))
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
                # docs/34 §1b: writers append an Event IN ADDITION to what they
                # already store; readers of the old JSONL keep working.
                try:
                    _event_log().append(kind="capture", body=text[:200],
                                        source="app", locator="api/ingest")
                except Exception:
                    pass
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
                from agent.memory import MemoryStore, _as_json_payload

                store = MemoryStore(AgentConfig.load(env=dict(os.environ)))
                return self._send(200, _as_json_payload(store))
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
        if p.path == "/api/world":
            # Bridge-to-world registry: GET lists (or ?tag= looks up).
            # Teaching is POST and forgetting is DELETE (see below).
            from brain.world import WorldRegistry

            reg = WorldRegistry()
            q = parse_qs(p.query).get("tag", [""])[0]
            if q:
                hit = reg.lookup(q)
                if hit is None:
                    return self._send(404, json.dumps({"error": "unknown tag"}))
                return self._send(200, json.dumps({"tag": q, **hit}))
            return self._send(200, json.dumps(reg.all()))
        if p.path == "/api/calendar/tick":
            # W8: run one calendar tick now (the scheduler does this every
            # minute). Idempotent by state file, so a manual poke is safe.
            lines = _calendar_tick()
            return self._send(200, json.dumps({"ok": True, "lines": lines}))
        if p.path == "/api/claims":
            # W9 belief state: active claims + any unresolved contradiction
            # the wearable should surface ("X vs Y — which holds?").
            if bridge is None or bridge.claims is None:
                return self._send(200, json.dumps({"active": [], "contradiction": None}))
            return self._send(200, json.dumps({
                "active": [c.to_dict() for c in bridge.claims.active()],
                "contradiction": bridge.claims.latest_supersede(),
            }))
        if p.path == "/api/status":
            # Glanceable HUD state for the companion mirror (and the wearable
            # status frame shape, t=8). Reflects the brain's own view when no
            # device is streaming, so the HUD mirror is never a dead demo.
            # docs/42: the digest is claims-driven, so the mirror shows the
            # same ANSWER/DIGEST/HINT rows the wrist renders.
            note_count = 0
            try:
                if pipeline is not None and getattr(pipeline, "store", None):
                    note_count = len(pipeline.store.all())
            except Exception:
                pass
            b = bridge
            from brain.hitl import get_gatebook

            gate = get_gatebook().latest_pending()
            digest = []
            try:
                if b is not None:
                    digest = b.digest_lines(3)
            except Exception:
                pass
            st = {
                "t": 8,
                "rec": 1 if (b and b.recording) else 0,
                "mode": (b.mode if b else "HOME"),
                "notes": note_count,
                "banner": (b.last_banner if b else ""),
                "digest": digest,
                "hint": "tap:ok 2x:back hold:ask",
                "online": True,
                "gate": gate.to_dict() if gate else None,
            }
            return self._send(200, json.dumps(st))
        if p.path == "/api/device":
            # Device tab (docs/43 §7). /api/status stays the glanceable mirror
            # (docs/42 rows); this adds what the DEVICE itself reported: battery,
            # presence, posture, mode, and where capture/OTA live.
            return self._send(200, json.dumps(_device_state()))
        if p.path == "/api/timeline":
            # docs/34 §4a: events + claims + notes on one time axis.
            limit = int(parse_qs(p.query).get("limit", ["60"])[0] or 60)
            return self._send(200, json.dumps(_timeline_rows(limit)))
        if p.path == "/api/ask":
            # docs/34 §4b: answer WITH citations (GET form for the dashboard;
            # POST form below for the app). No citation => `cited: false`, and
            # the UI shows that as an unverified answer.
            q = parse_qs(p.query)
            text = (q.get("q", [""])[0] or q.get("text", [""])[0]).strip()
            if not text:
                return self._send(400, json.dumps({"error": "missing q"}))
            return self._send(200, json.dumps(_answer_question(text)))
        if p.path == "/api/concepts":
            # Unified retrieval over notes + memory cards + entities (docs/15
            # mini4's endpoint matrix). Offline: ConceptIndex falls back to its
            # keyword leg when no semantic embedder is reachable.
            q = parse_qs(p.query)
            from brain.concepts import ConceptIndex

            idx = ConceptIndex(store=getattr(pipeline, "store", None) if pipeline else None)
            return self._send(200, json.dumps(
                idx.search(q.get("q", [""])[0], k=int(q.get("k", ["10"])[0] or 10))))
        if p.path == "/api/concepts/groups":
            from brain.concepts import ConceptIndex

            idx = ConceptIndex(store=getattr(pipeline, "store", None) if pipeline else None)
            return self._send(200, json.dumps(idx.groups()))
        if p.path == "/api/truth/log":
            # Audited truth edits: before/after log, newest last.
            from brain.concepts import read_truth_log

            limit = int(parse_qs(p.query).get("limit", ["50"])[0] or 50)
            return self._send(200, json.dumps(read_truth_log(limit)))
        if p.path.startswith("/api/physis/"):
            # physis-next MCP bridge (docs/43 §6). Replaces the retired
            # physis-pro-web /api/v1/* proxies that used to live here and had
            # silently gone missing (4 tests red). The upstream is loopback
            # only: `physis serve --http 127.0.0.1:PORT` never binds 0.0.0.0.
            from brain import physis_next as px

            q = parse_qs(p.query)
            try:
                if p.path == "/api/physis/status":
                    return self._send(200, json.dumps(px.status()))
                if p.path == "/api/physis/search":
                    hits = px.search(q.get("q", [""])[0],
                                     int(q.get("limit", ["10"])[0]))
                    return self._send(200, json.dumps({"results": hits}))
                if p.path == "/api/physis/context":
                    return self._send(200, json.dumps(px.context_stats(
                        q.get("q", [""])[0], int(q.get("budget", ["800"])[0]))))
                if p.path == "/api/physis/history":
                    return self._send(200, json.dumps(px.history(
                        q.get("q", [""])[0], int(q.get("limit", ["10"])[0]))))
                if p.path == "/api/physis/predict":
                    argv = [a for a in q.get("argv", [""])[0].split() if a]
                    return self._send(200, json.dumps(px.predict(argv)))
                if p.path == "/api/physis/capabilities":
                    return self._send(200, json.dumps(px.capabilities()))
            except px.PhysisNextUnavailable as e:
                return self._send(503, json.dumps({
                    "error": "physis-next unreachable", "detail": str(e),
                    "hint": "physis serve --http 127.0.0.1:19876 --path <ROOT>"}))
            except (ValueError, TypeError) as e:
                return self._send(400, json.dumps({"error": str(e)}))
            return self._send(404, json.dumps({"error": "not found"}))
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

    def do_DELETE(self):
        # Only route: forget a bridge-to-world registry tag (?tag=).
        p = urlparse(self.path)
        ok, _ = self._authorized(p)
        if not ok:
            return self._deny()
        if p.path == "/api/world":
            from brain.world import WorldRegistry

            q = parse_qs(p.query).get("tag", [""])[0]
            if WorldRegistry().forget(q):
                return self._send(200, json.dumps({"ok": True}))
            return self._send(404, json.dumps({"error": "unknown tag"}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        p = urlparse(self.path)
        ok, _ = self._authorized(p)
        if not ok:
            return self._deny()
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body or b"{}")
        except Exception:
            data = {}
        if p.path == "/api/ask":
            text = str(data.get("q") or data.get("text") or "").strip()
            if not text:
                return self._send(400, json.dumps({"error": "missing q"}))
            return self._send(200, json.dumps(_answer_question(text)))
        if p.path == "/api/events":
            # Explicit event append (docs/34 §1a): writers outside the brain
            # (phone app, scripts) post rows here instead of appending the JSONL
            # themselves, so the ledger keeps one writer per process.
            kind = str(data.get("kind", "")).strip()
            if not kind:
                return self._send(400, json.dumps({"error": "missing kind"}))
            try:
                ev = _event_log().append(
                    kind=kind, body=str(data.get("body", "")),
                    duration_s=float(data.get("duration_s", 0) or 0),
                    source=str(data.get("source", "app")),
                    locator=str(data.get("locator", "api")))
            except (TypeError, ValueError) as e:
                return self._send(400, json.dumps({"error": str(e)}))
            return self._send(200, json.dumps(ev.to_dict()))
        if p.path == "/api/truth":
            # Audited truth editing (docs/15 mini4 matrix): edit/delete a note,
            # every mutation logged with before/after in ~/.cyclops/truth_log.jsonl.
            from brain.concepts import delete_note, edit_note_text

            store = getattr(pipeline, "store", None) if pipeline else None
            if store is None:
                return self._send(400, json.dumps({"error": "no note store"}))
            action = str(data.get("action", ""))
            if action == "edit_note":
                ok, entry = edit_note_text(store, data.get("ref", ""),
                                           str(data.get("text", "")))
            elif action == "delete_note":
                ok, entry = delete_note(store, data.get("ref", ""))
            else:
                return self._send(400, json.dumps(
                    {"error": f"unknown action: {action or '(none)'}",
                     "known": ["edit_note", "delete_note"]}))
            if not ok:
                return self._send(404, json.dumps(
                    {"error": "note not found, or empty replacement text"}))
            return self._send(200, json.dumps({"ok": True, "entry": entry}))
        if p.path == "/api/physis/remember":
            # Record an outcome in physis-next (docs/43 §6). Reported evidence,
            # never certified truth — the MCP tool's own contract.
            from brain import physis_next as px

            try:
                out = px.remember(str(data.get("text", "")),
                                  str(data.get("outcome", "unverified")),
                                  str(data.get("actor", "cyclops")))
                return self._send(200, json.dumps(out))
            except px.PhysisNextUnavailable as e:
                return self._send(503, json.dumps({
                    "error": "physis-next unreachable", "detail": str(e)}))
        if p.path == "/api/claims/resolve":
            # W9 resolution from the wrist: {"keep_new": true|false}.
            if bridge is None or bridge.claims is None:
                return self._send(200, json.dumps({"ok": False, "reason": "no claims store"}))
            keep_new = bool(data.get("keep_new", True))
            got = bridge.resolve_contradiction(keep_new=keep_new)
            if got is None:
                return self._send(404, json.dumps({"error": "no pending contradiction"}))
            return self._send(200, json.dumps({"ok": True, "kept": keep_new,
                                               "claim": got.to_dict()}))
        if p.path == "/api/notify":
            # W7 notification triage: the phone already classified (pure rules
            # in :core). Record the event; when buzz is set, put the line on
            # the wearable HUD. Silence is the default — a non-buzz here is a
            # ledger entry, not a display.
            line = (data.get("line") or "").strip()
            pkg = (data.get("pkg") or "").strip()
            buzz = bool(data.get("buzz"))
            if not line:
                return self._send(400, json.dumps({"error": "line required"}))
            if pipeline is not None:
                try:
                    pipeline.process_text(f"[notify {pkg}] {line}")
                except Exception:
                    pass
            if buzz and bridge is not None:
                bridge.last_banner = line
            return self._send(200, json.dumps(
                {"ok": True, "buzzed": bool(buzz and bridge is not None)}))
        if p.path == "/api/activity":
            # Phone activity classification (UsageStats tier): the phone
            # already classified foreground sessions on-device; each session
            # becomes a ledger event (source: phone, locator = package).
            # Opt-in on the phone; no pixels, no view text ever leaves it.
            # Body: {"sessions": [{"package":..., "label":..., "started_at":...,
            # "duration_s": n}]}. Short (<30s) sessions are noise, skipped.
            from datetime import datetime, timezone

            sessions = data.get("sessions") or []
            kept = 0
            if pipeline is not None:
                from brain.extractor import Note

                for s in sessions:
                    try:
                        dur = int(s.get("duration_s", 0))
                    except (TypeError, ValueError):
                        continue
                    if dur < 30:
                        continue
                    pkg = str(s.get("package") or "").strip()
                    if not pkg:
                        continue
                    label = str(s.get("label") or pkg).strip()
                    started = str(s.get("started_at") or "").strip()
                    if not started:
                        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    nid = "n_" + started.replace(":", "").replace("-", "").replace(".", "")
                    try:
                        pipeline.store.add(Note(
                            id=f"{nid}_{kept}", type="activity",
                            text=f"{label} ({dur // 60}m {dur % 60}s)",
                            created=started, source="phone:" + pkg,
                        ))
                        kept += 1
                    except Exception:
                        pass
            return self._send(200, json.dumps({"ok": True, "kept": kept}))
        if p.path == "/api/world":
            # Teach path of the bridge-to-world registry (GET side lives in
            # do_GET so listing stays a safe GET; both are auth-gated).
            from brain.world import WorldRegistry

            tag, answer = (data.get("tag") or "").strip(), (data.get("answer") or "").strip()
            if not tag or not answer:
                return self._send(400, json.dumps({"error": "tag and answer required"}))
            return self._send(200, json.dumps({"ok": True, "tag": tag, **WorldRegistry().teach(tag, answer)}))
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
    global pipeline, agent, bridge, PORT, STORE_PATH, TOKEN
    if not ALLOW_INSECURE_LAN:
        TOKEN = load_or_create_token()
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
            claims=_claim_store(),
        )
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    # LAN discovery beacon so clients can find us without typing an IP.
    # Convenience only: a taken UDP port degrades to "no beacon", never blocks.
    from brain.discovery import DiscoveryBeacon

    beacon = DiscoveryBeacon(http_port=PORT)
    if beacon.start():
        print(f"Discovery beacon on udp/{beacon.listen_port}")
    _start_dream_scheduler()  # periodic proactive review (dreams/proposals)
    _start_calendar_scheduler()  # W8: arm/file meetings, leave nudges
    print(f"Cyclops dashboard on http://localhost:{PORT}")
    if ALLOW_INSECURE_LAN:
        print("  !! CYCLOPS_ALLOW_INSECURE_LAN=1 — every route is open to the")
        print("     whole network, including POST /api/agent (terminal tool).")
        print("     Only for a network you control end to end.")
    else:
        print(f"  Off-host clients need a token: ?token={TOKEN}")
        print(f"  (stored 0600 in {TOKEN_PATH}; loopback is exempt)")
        print("  Plain HTTP — the token crosses the LAN in clear. Front it with")
        print("  tailscale/TLS on any network you do not control.")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
        beacon.stop()


if __name__ == "__main__":
    main()
