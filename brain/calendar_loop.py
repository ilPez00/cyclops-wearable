"""Calendar trigger engine (W8): close the loop between calendar entries and
capture, so meetings arm/file themselves and late departures get a nudge.

Pure function over (events, now, state) -> actions, so it is fully testable
without a scheduler, a network, or a real calendar feed. The server applies
the actions (arms transcription, files notes, emits a HUD line) on a tick;
the calendar source is whatever wrote ~/cyclops_data/calendar.jsonl, so a
real Google/IMAP feed later needs no change here.

Entry shape (agent/tools/calendar.py + optional fields):
    {"when": "2026-09-18", "at": "14:30", "duration_min": 30,
     "title": "Standup", "kind": "event", "place": "office"}

`at` and `duration_min` are optional; an entry without `at` is all-day and
never arms (nothing to time). `place` enables the leave-now prediction.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

DEFAULT_CALENDAR = os.path.expanduser("~/cyclops_data/calendar.jsonl")
DEFAULT_DURATION_MIN = 30
DEFAULT_TRAVEL_MIN = 20


def _eid(e: dict) -> str:
    return f"{e.get('when','')}T{e.get('at','')}|{e.get('title','')}"


def _start(e: dict) -> datetime | None:
    when, at = e.get("when", ""), e.get("at", "")
    if not when or not at:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{when} {at}", fmt)
        except ValueError:
            continue
    return None


def load_events(path: str = DEFAULT_CALENDAR) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def due_actions(
    events: list[dict],
    now: datetime,
    state: dict | None = None,
    travel_min: int = DEFAULT_TRAVEL_MIN,
    lead_min: int = 1,
) -> tuple[list[dict], dict]:
    """Return (actions, new_state). state keys: armed/filed/left -> set of ids.

    Rules, in priority order per event:
      leave  now >= start - travel_min (only when `place` set, once)
      arm    now >= start - lead_min     (start capture)
      file   now >= end                  (stop capture, file notes)
    An event without `at` is skipped. State is never mutated; the returned
    copy is what the caller persists, so a tick is idempotent.
    """
    st = {
        "armed": set((state or {}).get("armed", [])),
        "filed": set((state or {}).get("filed", [])),
        "left": set((state or {}).get("left", [])),
    }
    actions: list[dict] = []
    for e in events:
        start = _start(e)
        if start is None:
            continue
        eid = _eid(e)
        dur = int(e.get("duration_min", DEFAULT_DURATION_MIN) or DEFAULT_DURATION_MIN)
        end = start + timedelta(minutes=dur)
        title = e.get("title", "(untitled)")
        if e.get("place") and eid not in st["left"] and now >= start - timedelta(minutes=travel_min):
            if now < end:
                st["left"].add(eid)
                actions.append({"action": "leave", "id": eid, "title": title,
                                "at": (start - timedelta(minutes=travel_min)).isoformat(timespec="minutes"),
                                "reason": f"{travel_min} min to {e['place']}"})
        if eid not in st["armed"] and now >= start - timedelta(minutes=lead_min):
            st["armed"].add(eid)
            actions.append({"action": "arm", "id": eid, "title": title,
                            "at": start.isoformat(timespec="minutes")})
        if eid not in st["filed"] and now >= end:
            st["filed"].add(eid)
            actions.append({"action": "file", "id": eid, "title": title,
                            "at": end.isoformat(timespec="minutes")})
    return actions, st


DEFAULT_STATE = os.path.expanduser("~/.cyclops/calendar_state.json")


def load_state(path: str = DEFAULT_STATE) -> dict:
    """Sets are persisted as sorted lists (JSON has no set type)."""
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return {"armed": [], "filed": [], "left": []}
    return {k: list(raw.get(k, [])) for k in ("armed", "filed", "left")}


def save_state(state: dict, path: str = DEFAULT_STATE) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({k: sorted(state.get(k, [])) for k in ("armed", "filed", "left")}, f)
    os.replace(tmp, path)


def apply_actions(actions: list[dict], bridge) -> list[str]:
    """Apply tick actions to a HudBridge: arm starts capture, file stops it,
    leave only surfaces a HUD line (the wearer decides). Returns the human
    lines emitted, so the caller can log/relay them."""
    from .protocol_v2 import ACT_TRANSCRIBE_START

    out = []
    for a in actions:
        if a["action"] == "arm":
            bridge.dispatch(ACT_TRANSCRIBE_START, "")
            line = f"armed: {a['title']}"
        elif a["action"] == "file":
            if getattr(bridge, "recording", False):
                bridge.recording = False
            line = f"filed: {a['title']}"
        else:
            line = f"leave now: {a['title']} ({a.get('reason','')})"
        bridge.last_banner = line
        out.append(line)
    return out

