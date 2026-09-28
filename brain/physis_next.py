"""Physis-next bridge — cyclops brain as a client of the physis-next MCP server.

Successor of `brain/physis.py`, which spoke the *retired* physis-pro-web REST
API (`/api/v1/*` on port 19876). physis-next exposes the same kind of surface as
MCP: JSON-RPC 2.0 over stdio, or over HTTP with

    physis serve --http 127.0.0.1:19876 --path <ROOT>

(POST /mcp, one JSON-RPC request per call, NDJSON body; raw TcpListener in
crates/physis-mcp/src/transport.rs — loopback only, never 0.0.0.0). The HTTP
transport loads a fresh `Server::load(root)` per request, so there is no
session/initialize state to keep: a bare `tools/call` is a complete exchange.

Config is env-only, never committed:
  PHYSIS_URL   base URL, default http://127.0.0.1:19876 (same port physis-pro
               used, so existing deployments keep working)
  PHYSIS_ROOT  tree physis-next indexes — informational here; the server owns it

Every call is best-effort: short timeout, failures surface as
PhysisNextUnavailable so callers degrade to local behaviour (same contract
brain/physis.py had). Stdlib only.
"""

from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_URL = "http://127.0.0.1:19876"
_PROTOCOL = "2025-06-18"   # what physis-mcp advertises; informational for calls
_ids = {"n": 0}


class PhysisNextUnavailable(Exception):
    pass


def base_url() -> str:
    return (os.environ.get("PHYSIS_URL") or DEFAULT_URL).rstrip("/")


def root() -> str:
    """The tree physis-next indexes. Informational: the server owns the bind."""
    return os.environ.get("PHYSIS_ROOT") or ""


def configured() -> bool:
    """physis-next is loopback-only, so there is no token — only a URL."""
    return bool(base_url())


def rpc(name: str, args: dict | None = None, timeout: float = 8.0) -> dict:
    """One MCP `tools/call` over POST /mcp. Raises PhysisNextUnavailable.

    Returns the tool's structured payload with the text rendering added under
    `_text` (the human form the MCP server ships in content[0].text).
    """
    _ids["n"] += 1
    body = {
        "jsonrpc": "2.0",
        "id": _ids["n"],
        "method": "tools/call",
        "params": {"name": name, "arguments": args or {}},
    }
    req = urllib.request.Request(
        base_url() + "/mcp",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except Exception as e:  # connection refused, timeout, bad HTTP status…
        raise PhysisNextUnavailable(f"POST /mcp {name}: {e}")
    try:
        # NDJSON: the response line first, queued notifications after.
        first = (raw.decode() or "").strip().split("\n")[0]
        out = json.loads(first) if first else {}
    except ValueError as e:
        raise PhysisNextUnavailable(f"{name}: unparseable response ({e})")
    if out.get("error"):
        raise PhysisNextUnavailable(f"{name}: {out['error']}")
    res = out.get("result") or {}
    text = ""
    for part in res.get("content") or []:
        if part.get("type") == "text":
            text = part.get("text", "")
            break
    if res.get("isError"):
        raise PhysisNextUnavailable(f"{name}: {text or 'tool error'}")
    sc = res.get("structuredContent")
    payload = dict(sc) if isinstance(sc, dict) else {"structured": sc}
    payload["_text"] = text
    return payload


def status(timeout: float = 2.0) -> dict:
    """Reachability + identity probe (never raises). Used by /api/physis/status."""
    out = {"reachable": False, "url": base_url(), "root": root(),
           "transport": "mcp-http", "detail": ""}
    try:
        caps = rpc("physis.capabilities", {}, timeout=timeout)
    except PhysisNextUnavailable as e:
        out["detail"] = str(e)
        return out
    out["reachable"] = True
    out["workspace"] = caps.get("workspace", "")
    out["api_version"] = caps.get("api_version", "")
    return out


def search(q: str, limit: int = 10, timeout: float = 8.0) -> list[dict]:
    out = rpc("physis.search", {"q": q or "", "limit": int(limit)}, timeout)
    hits = out.get("results") or out.get("hits") or []
    return hits if isinstance(hits, list) else []


def context_stats(query: str, budget: int = 800, timeout: float = 8.0) -> dict:
    """Bounded context with receipts (per-candidate scores, dropped, strategies)."""
    return rpc("physis.context_stats", {"query": query or "",
                                        "budget": int(budget)}, timeout)


def remember(text: str, outcome: str = "unverified", actor: str = "cyclops",
             timeout: float = 8.0) -> dict:
    return rpc("physis.remember", {"text": text or "", "outcome": outcome,
                                   "actor": actor}, timeout)


def history(query: str = "", limit: int = 10, timeout: float = 8.0) -> dict:
    return rpc("physis.history", {"query": query, "limit": int(limit)}, timeout)


def predict(argv: list[str], timeout: float = 8.0) -> dict:
    return rpc("physis.predict", {"argv": [str(a) for a in argv]}, timeout)


def capabilities(timeout: float = 8.0) -> dict:
    return rpc("physis.capabilities", {}, timeout)
