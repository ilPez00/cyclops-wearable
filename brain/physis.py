"""Physis **legacy** bridge — embedder adapter for a physis-pro-web instance.

Reality check (2026-09-28, docs/43 §6): physis-pro is retired. Its web server
is not running anywhere in this deployment, and physis-next — the canonical
line — exposes **no** embed endpoint (its `physis embed` CLI prints a label
and the first dims, it does not return a vector). So this module is no longer
the app's memory path: `brain/physis_next.py` is (MCP over HTTP). What is left
here is the drop-in embedder that keeps the *interface* honest — when a
semantic embedder service answers on PHYSIS_URL, ConceptIndex uses it; when
nothing answers, `best_embedder()` returns the hashing fallback and every
caller degrades locally. `tests/test_physis.py` pins both halves.

Legacy contract (physis-pro-web, physis-pro/src/web/mod.rs):
  POST /api/v1/embed {text} -> {embedding, dim}
  PHYSIS_URL        base URL, default http://127.0.0.1:19876
  PHYSIS_API_TOKEN  Bearer token; without it protected routes answer 401

The retired classify/lifeos/goals/coherence wrappers were deleted with the
routes that served them (they had zero callers once app/server.py dropped the
/api/physis/* proxies — dead surface per docs/41 item 5).

Every call is best-effort: short timeout, exceptions surface as
PhysisUnavailable so callers degrade to local behavior. Stdlib only.
"""

from __future__ import annotations

import json
import os
import urllib.request


class PhysisUnavailable(Exception):
    pass


def base_url() -> str:
    return (os.environ.get("PHYSIS_URL") or "http://127.0.0.1:19876").rstrip("/")


def api_token() -> str:
    return os.environ.get("PHYSIS_API_TOKEN") or ""


def configured() -> bool:
    return bool(api_token())


def _call(method: str, path: str, body: dict | None = None, timeout: float = 8.0) -> dict:
    url = base_url() + path
    data = json.dumps(body or {}).encode() if method == "POST" else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    if api_token():
        req.add_header("Authorization", "Bearer " + api_token())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except Exception as e:
        raise PhysisUnavailable(f"{method} {path}: {e}")


def embed(text: str, timeout: float = 8.0) -> list[float]:
    """Single text -> unit-ish vector (bge-base 768-d on the live server)."""
    out = _call("POST", "/api/v1/embed", {"text": text or ""}, timeout)
    vec = out.get("embedding") or []
    if not vec:
        raise PhysisUnavailable("empty embedding")
    return [float(x) for x in vec]


class PhysisEmbedder:
    """Drop-in `embedder` for ConceptIndex.search (concepts.py).

    Same `.embed(text)` shape as HashEmbedder, but vectors come from
    physis over HTTP with an in-memory cache (one call per unique text;
    a 200-note search warms once, then stays local). Any failure raises
    PhysisUnavailable — callers catch it and fall back to HashEmbedder.
    """

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self._cache: dict[str, list[float]] = {}
        self.dim = 0

    def embed(self, text: str) -> list[float]:
        key = text or ""
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        vec = embed(key, self.timeout)
        if not self.dim:
            self.dim = len(vec)
        self._cache[key] = vec
        return vec

    def similarity(self, a: str, b: str) -> float:
        import math

        va, vb = self.embed(a), self.embed(b)
        dot = sum(x * y for x, y in zip(va, vb))
        na = math.sqrt(sum(x * x for x in va))
        nb = math.sqrt(sum(y * y for y in vb))
        return dot / (na * nb + 1e-9)


def best_embedder(timeout: float = 8.0):
    """Physis when reachable (probe call), else hashing fallback. Never raises."""
    from .concepts import HashEmbedder

    if not configured():
        return HashEmbedder()
    try:
        probe = PhysisEmbedder(timeout=timeout)
        probe.embed("connectivity probe")
        return probe
    except PhysisUnavailable:
        return HashEmbedder()


__all__ = ["PhysisUnavailable", "base_url", "api_token", "configured",
           "embed", "PhysisEmbedder", "best_embedder"]
