"""Captured-media store for the Cyclops companion app.

Everything lives host-side under ~/.cyclops/captures/{images,audio,video}/ so
the app is the single source of truth: the media browser works even when the
wearable is asleep or offline. No device-served pages, no SD dependency at
read time — captures are pushed into the app (via /api/vision frames or an
explicit POST /api/media) and served back from here.

Pure stdlib, no third-party deps (matches app/server.py).
"""
from __future__ import annotations

import base64
import os
import re
import time
from typing import Optional

CAPTURES_DIR = os.path.expanduser("~/.cyclops/captures")

# category -> (allowed extensions, default extension). The browser always shows
# all three categories even when a folder is empty.
CATS: dict[str, tuple[set[str], str]] = {
    "images": ({"jpg", "jpeg", "png", "gif", "webp"}, "jpg"),
    "audio": ({"wav", "mp3", "ogg", "webm", "m4a", "opus", "aac"}, "wav"),
    "video": ({"mp4", "webm", "mjpeg", "mov", "avi", "mkv"}, "mp4"),
}

_MIME = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "webp": "image/webp",
    "wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg",
    "m4a": "audio/mp4", "opus": "audio/opus", "aac": "audio/aac",
    "mp4": "video/mp4", "webm": "video/webm", "mjpeg": "video/x-motion-jpeg",
    "mov": "video/quicktime", "avi": "video/x-msvideo", "mkv": "video/x-matroska",
}

# map a raw MIME type (e.g. from a data: URL) back to (category, extension).
_MIME_TO_CAT = {v: (cat, ext) for ext, v in _MIME.items()
                for cat, (exts, _d) in CATS.items() if ext in exts}

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _cat_dir(cat: str) -> str:
    d = os.path.join(CAPTURES_DIR, cat)
    os.makedirs(d, exist_ok=True)
    return d


def _ext_ok(cat: str, ext: str) -> bool:
    return ext.lower() in CATS[cat][0]


def category_from_mime(mime: str) -> Optional[tuple[str, str]]:
    """(category, extension) for a MIME type, or None if unsupported."""
    return _MIME_TO_CAT.get((mime or "").split(";")[0].strip().lower())


def _decode_payload(payload: str, cat: Optional[str], ext: Optional[str]):
    """Accept a `data:<mime>;base64,<...>` URL or a bare base64 string.

    Returns (raw_bytes, category, extension). The data: URL's own MIME wins
    for category/extension inference; explicit cat/ext args are the fallback.
    """
    inferred_cat = inferred_ext = None
    if payload.startswith("data:"):
        header, _, b64 = payload.partition(",")
        m = re.match(r"data:([^;,]+)", header)
        if m:
            hit = category_from_mime(m.group(1))
            if hit:
                inferred_cat, inferred_ext = hit
        payload = b64
    raw = base64.b64decode(payload, validate=False)
    final_cat = cat or inferred_cat
    final_ext = (ext or inferred_ext or (CATS[final_cat][1] if final_cat else None))
    return raw, final_cat, final_ext


def save_media(payload: str, cat: Optional[str] = None,
               ext: Optional[str] = None) -> dict:
    """Persist a base64 / data-URL payload into the right category folder.

    Raises ValueError on an unknown/mismatched category or extension so the
    caller can return a 400 rather than silently dropping the capture.
    """
    raw, cat, ext = _decode_payload(payload, cat, ext)
    if cat not in CATS:
        raise ValueError(f"unknown category: {cat!r}")
    ext = (ext or CATS[cat][1]).lower().lstrip(".")
    if not _ext_ok(cat, ext):
        raise ValueError(f"extension .{ext} not allowed for {cat}")
    if not raw:
        raise ValueError("empty payload")
    # millisecond timestamp keeps names sortable and collision-free.
    name = f"{time.strftime('%Y%m%d-%H%M%S')}-{int(time.time() * 1000) % 1000:03d}.{ext}"
    path = os.path.join(_cat_dir(cat), name)
    with open(path, "wb") as f:
        f.write(raw)
    return _entry(cat, name, os.stat(path))


def _entry(cat: str, name: str, st: os.stat_result) -> dict:
    ext = name.rsplit(".", 1)[-1].lower()
    return {
        "name": name,
        "cat": cat,
        "size": st.st_size,
        "mtime": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime)),
        "mime": _MIME.get(ext, "application/octet-stream"),
        "url": f"/media/{cat}/{name}",
    }


def list_media(cat: str) -> list[dict]:
    """Newest-first listing of one category. Empty list if the folder is bare."""
    if cat not in CATS:
        raise ValueError(f"unknown category: {cat!r}")
    d = _cat_dir(cat)
    out = []
    for name in os.listdir(d):
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if not _ext_ok(cat, ext):
            continue
        try:
            out.append(_entry(cat, name, os.stat(os.path.join(d, name))))
        except OSError:
            continue
    out.sort(key=lambda e: e["mtime"], reverse=True)
    return out


def counts() -> dict:
    """Per-category file counts for the tab badges."""
    return {cat: len(list_media(cat)) for cat in CATS}


def read_media(cat: str, name: str) -> Optional[tuple[bytes, str]]:
    """(bytes, mime) for one file, or None if missing / rejected.

    Rejects any name that isn't a plain basename to block path traversal.
    """
    if cat not in CATS or not _SAFE_NAME.match(name or ""):
        return None
    path = os.path.join(_cat_dir(cat), name)
    # defence in depth: the resolved path must stay inside the category dir.
    if os.path.dirname(os.path.realpath(path)) != os.path.realpath(_cat_dir(cat)):
        return None
    if not os.path.isfile(path):
        return None
    ext = name.rsplit(".", 1)[-1].lower()
    with open(path, "rb") as f:
        return f.read(), _MIME.get(ext, "application/octet-stream")
