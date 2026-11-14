"""Zero-photo semantic visual memory (#1).

Fetches one JPEG from the wearable's on-demand capture endpoint
(firmware/xiao/src/camera_capture.{h,cpp} — brought up only when a photo is
requested, announced back as the ACT_PHOTO cmd's arg), tags it via the
vision model, and discards the bytes immediately. Only short text tags
persist: "2:00 PM: office desk, laptop, coffee cup." No photo library, no
battery/storage cost of keeping images, and nothing to leak if the log
itself is ever exposed — that's the privacy trade this feature is built on.

vision_fn is injected (not imported) so this stays testable with a fake —
mirrors device/camera.py's CameraSource injection pattern. The real one is
wired in app/server.py from agent/tools/vision.py's make_vision_tool.
"""

from __future__ import annotations

import base64
import http.client
import ipaddress
import json
import os
import socket
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Optional

# _fetch's url comes from the wearable's ACT_PHOTO arg, relayed over BLE ->
# app/server.py's /api/hud_cmd?a=16&arg=<url> -- an unauthenticated LAN
# client can hit that endpoint directly with ANY url, not just the real
# capture URL the firmware would announce. This is deliberately built on
# http.client, not urllib.request.build_opener(): an opener still wires in
# FileHandler/FTPHandler/HTTPRedirectHandler by default unless you pass
# overrides for those exact classes too (an earlier version of this file
# claimed passing HTTPHandler/HTTPSHandler alone was a second defense layer
# against file:// -- that was false; FileHandler was still present). And
# resolve-then-fetch-by-hostname is DNS-rebinding TOCTOU: whatever passed
# the check can resolve to something else by the time the connection
# actually opens. Fixed here by resolving+validating once, then connecting
# directly to that literal IP -- nothing left to re-resolve. There is also
# no redirect-following at all (a non-2xx response is just a failure), so a
# 3xx to an unvalidated target is never chased.


def _resolve_allowed_ip(hostname: str) -> Optional[str]:
    """Resolve hostname once and require the result be a private,
    non-loopback, non-link-local address (rejects the 169.254.169.254 cloud
    metadata endpoint specifically, plus localhost and public hosts)."""
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except (OSError, ValueError):
        return None
    if ip.is_private and not ip.is_loopback and not ip.is_link_local:
        return ip_str
    return None


DEFAULT_LOG = os.path.expanduser("~/.cyclops/sightings.jsonl")

TAG_PROMPT = (
    "List 3-6 short tags for what's in this image: objects, scene, "
    "activity. No prose, no sentences — comma-separated tags only."
)


class SightingLog:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or DEFAULT_LOG)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, tags: str, ts: Optional[float] = None) -> dict:
        entry = {"ts": ts if ts is not None else time.time(), "tags": tags}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def all(self) -> list:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    def search(self, query: str) -> list:
        q = query.lower().strip()
        if not q:
            return []
        return [e for e in self.all() if q in e.get("tags", "").lower()]


def _fetch(url: str, timeout: float = 10.0) -> Optional[bytes]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.hostname:
        return None
    ip = _resolve_allowed_ip(parsed.hostname)
    if ip is None:
        return None
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    conn_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    # Connect to the validated IP literal, not the hostname -- see module
    # docstring. Host header carries the original hostname for correctness;
    # for https this also means TLS validates the cert against the IP, not
    # the hostname, which fails closed for any normal cert rather than
    # reopening a rebinding path via SNI-hostname override.
    conn = conn_cls(ip, port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"Host": parsed.hostname})
        resp = conn.getresponse()
        body = resp.read()
        if resp.status != 200:
            return None
        return body
    except Exception:
        return None
    finally:
        conn.close()


def capture_and_tag(
    url: str,
    vision_fn: Callable[[str, str], str],
    log: Optional[SightingLog] = None,
    fetch: Callable[[str], Optional[bytes]] = _fetch,
) -> Optional[dict]:
    """Fetch one JPEG from `url`, tag it via `vision_fn(image_b64, prompt)`,
    discard the bytes, and persist only the tags. Returns the log entry, or
    None if capture/tagging failed (network error, camera busy, offline
    vision stub, etc.) — a miss here is silent, not an error surfaced to
    the wearer; this is background/proactive, not a requested action."""
    frame = fetch(url)
    if not frame:
        return None
    b64 = base64.b64encode(frame).decode()
    del frame  # tagged or not, the image itself is never persisted
    try:
        tags = vision_fn(b64, TAG_PROMPT)
    except Exception:
        return None
    tags = (tags or "").strip()
    if not tags or tags.startswith("error:") or tags.startswith("offline:"):
        return None
    return (log or SightingLog()).add(tags)
