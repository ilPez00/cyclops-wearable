"""Tools: ingest the user's media context — photos, voice recordings, places.

Scans configurable roots for images / audio / location history (JSON or GPX)
and returns a condensed index the model can reason over. On Android these map
to the MediaStore (photos/voice) and location history; on desktop to folders.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from ..loop import Tool
from ..config import AgentConfig


def make_media_tool(config: AgentConfig) -> Tool:
    photo_root = os.path.expanduser("~/Pictures")
    audio_root = os.path.expanduser("~/VoiceRecorder")
    places_root = os.path.expanduser("~/Locations")

    def run(args: dict) -> str:
        kind = (args.get("kind") or "all").lower()
        limit = int(args.get("limit", 20))
        out = []
        if kind in ("all", "photos"):
            out += _recent(photo_root, (".jpg", ".jpeg", ".png", ".webp"), "photo", limit)
        if kind in ("all", "voice"):
            out += _recent(audio_root, (".m4a", ".mp3", ".wav", ".ogg"), "voice", limit)
        if kind in ("all", "places"):
            out += _places(places_root, limit)
        return "\n".join(out) or "no media found"

    def _recent(root: str, exts, label, limit) -> list[str]:
        p = Path(root)
        if not p.exists():
            return []
        files = [f for f in p.rglob("*") if f.suffix.lower() in exts]
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        res = []
        for f in files[:limit]:
            res.append(f"{label}: {f.name} ({_ts(f)})")
        return res

    def _places(root: str, limit) -> list[str]:
        p = Path(root)
        if not p.exists():
            return []
        res = []
        for f in p.glob("*.json"):
            try:
                data = json.loads(f.read_text(errors="ignore"))
                if isinstance(data, list):
                    res.append(f"places file {f.name}: {len(data)} points")
                elif isinstance(data, dict) and "features" in data:
                    res.append(f"places file {f.name}: {len(data['features'])} features")
            except Exception:
                pass
        return res[:limit]

    def _ts(f: Path) -> str:
        import datetime
        return datetime.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")

    return Tool(
        name="media_ingest",
        description="List recent photos, voice recordings and places visited to feed the AI.",
        parameters={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["all", "photos", "voice", "places"]},
                "limit": {"type": "integer", "default": 20},
            },
        },
        run=run,
    )
