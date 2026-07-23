"""Human-in-the-loop approval gates for risky wearable-driven actions.

The wearable's MSG_CMD can trigger actions the brain fulfills on the phone's
behalf (see hud_bridge.HudBridge.dispatch). Most are harmless (transcribe,
translate, health readout). A few are not (ACT_SSH). GateBook makes those
wait for an explicit ACT_CONFIRM_YES/ACT_CONFIRM_NO before running — the
same "never auto-commit" principle the app already applies to candidate
notes (see MainActivity's doc comment), extended to remote command exec.

Fail-closed: an expired, unresolved gate reads as rejected, never approved.
No network/asyncio here — /api/hud_cmd is a synchronous one-shot HTTP call,
so there is no blocking wait; a gate is opened and the caller is told to
poll (via /api/status) until it's resolved by a later confirm action.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

GATE_TIMEOUT_S = 120.0


@dataclass
class Gate:
    id: str
    action: str
    arg: str
    created_at: float = field(default_factory=time.monotonic)
    resolved: bool = False
    approved: bool = False

    def is_expired(self, now: float | None = None) -> bool:
        return (now or time.monotonic()) - self.created_at > GATE_TIMEOUT_S

    def to_dict(self) -> dict:
        return {"id": self.id, "action": self.action, "arg": self.arg}


class GateBook:
    """Pure in-memory gate state. One process-wide instance (get_gatebook())."""

    def __init__(self) -> None:
        self._gates: dict[str, Gate] = {}

    def request(self, action: str, arg: str = "") -> Gate:
        g = Gate(id=uuid.uuid4().hex[:8], action=action, arg=arg)
        self._gates[g.id] = g
        return g

    def pending(self) -> list[Gate]:
        now = time.monotonic()
        out = []
        for g in self._gates.values():
            if g.resolved:
                continue
            if g.is_expired(now):
                g.resolved, g.approved = True, False  # fail-closed
                continue
            out.append(g)
        return out

    def has_pending(self) -> bool:
        return len(self.pending()) > 0

    def latest_pending(self) -> Gate | None:
        p = self.pending()
        return p[-1] if p else None

    def resolve(self, gate_id: str, approved: bool) -> bool:
        g = self._gates.get(gate_id)
        if g is None or g.resolved:
            return False
        g.resolved, g.approved = True, approved
        return True

    def resolve_latest(self, approved: bool) -> Gate | None:
        g = self.latest_pending()
        if g is None:
            return None
        self.resolve(g.id, approved)
        return g

    def clear_resolved(self) -> None:
        self._gates = {k: v for k, v in self._gates.items() if not v.resolved}


_book = GateBook()


def get_gatebook() -> GateBook:
    return _book
