"""Claims with evidence (34 Phase 2): the belief layer.

A claim is a statement plus the events that support it, with a lifecycle
(active / contradicted / superseded) and bi-temporal validity (valid_at =
when it became true in the world, invalid_at = when it stopped; distinct
from created_at, which is when we recorded it).

Contradiction handling is DETERMINISTIC, never an LLM judge (same condition
as physis PH-019). Similarity is cosine over bag-of-words term frequencies —
stdlib, offline, testable. It is a heuristic with a known ceiling (no
synonyms, no negation); the threshold pair is the `recall` prior art:

    sim >= REINFORCE   -> same claim, add evidence, raise confidence
    SUPERSEDE <= sim < REINFORCE -> newer wins, old marked superseded
    sim <  SUPERSEDE   -> independent claim

Every change to a claim is a Revision (append-only), so the belief state is
auditable and a model swap that changes structure shows up as a hash diff.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

REINFORCE = 0.92
SUPERSEDE = 0.85
DEFAULT_CONFIDENCE = 0.5
CONFIDENCE_STEP = 0.1
DEFAULT_PATH = os.path.expanduser("~/.cyclops/claims.jsonl")
DEFAULT_REVISIONS = os.path.expanduser("~/.cyclops/revisions.jsonl")

_WORD = re.compile(r"[a-z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _tokens(text: str) -> Counter:
    return Counter(_WORD.findall((text or "").lower()))


def similarity(a: str, b: str) -> float:
    """Cosine similarity of bag-of-words TF vectors, in [0, 1]."""
    ca, cb = _tokens(a), _tokens(b)
    if not ca or not cb:
        return 0.0
    common = set(ca) & set(cb)
    dot = sum(ca[w] * cb[w] for w in common)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class Claim:
    statement: str
    evidence: list[str] = field(default_factory=list)
    status: str = "active"          # active | contradicted | superseded
    confidence: float = DEFAULT_CONFIDENCE
    valid_at: str | None = None     # world time (when it became true)
    invalid_at: str | None = None   # world time (when it stopped being true)
    created_at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    superseded_by: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "statement": self.statement, "status": self.status,
            "confidence": round(self.confidence, 4), "evidence": list(self.evidence),
            "valid_at": self.valid_at, "invalid_at": self.invalid_at,
            "created_at": self.created_at, "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(
            statement=d.get("statement", ""),
            evidence=list(d.get("evidence", [])),
            status=d.get("status", "active"),
            confidence=float(d.get("confidence", DEFAULT_CONFIDENCE)),
            valid_at=d.get("valid_at"),
            invalid_at=d.get("invalid_at"),
            created_at=d.get("created_at", _now()),
            id=d.get("id") or uuid.uuid4().hex[:8],
            superseded_by=d.get("superseded_by"),
        )


class ClaimStore:
    """Append-only JSONL of claim snapshots + a revisions log.

    The file is a log of full claim snapshots (not a mutable table), so a
    claim's history is the sequence of snapshots sharing its id; `all()`
    folds them to the latest state per id. Nothing is ever rewritten, which
    makes the store trivially syncable (35 Phase E) and auditable.
    """

    def __init__(self, path: str = DEFAULT_PATH,
                 revisions_path: str = DEFAULT_REVISIONS):
        self.path = os.path.expanduser(path)
        self.revisions_path = os.path.expanduser(revisions_path)

    # -- io ------------------------------------------------------------------

    def _append(self, path: str, obj: dict) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj) + "\n")

    def _read_snapshots(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        return out

    def all(self) -> list[Claim]:
        """Latest snapshot per claim id, oldest-created first."""
        latest: dict[str, Claim] = {}
        order: list[str] = []
        for snap in self._read_snapshots():
            c = Claim.from_dict(snap)
            if c.id not in latest:
                order.append(c.id)
            latest[c.id] = c
        return [latest[i] for i in order]

    def active(self) -> list[Claim]:
        return [c for c in self.all() if c.status == "active"]

    def revisions(self) -> list[dict]:
        if not os.path.exists(self.revisions_path):
            return []
        out = []
        with open(self.revisions_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
        return out

    def _save(self, c: Claim, reason: str, before_hash: str) -> None:
        self._append(self.path, c.to_dict())
        after = structure_hash(self.all())
        self._append(self.revisions_path, {
            "ts": _now(), "claim_id": c.id, "reason": reason,
            "hash_before": before_hash, "hash_after": after,
        })

    # -- belief ops ----------------------------------------------------------

    def assert_claim(self, statement: str, evidence: list[str] | None = None,
                     valid_at: str | None = None,
                     now: str | None = None) -> tuple[Claim, str]:
        """Add or reconcile a claim. Returns (claim, action) where action is
        one of reinforced/superseded/independent. Newer wins on supersede."""
        before = structure_hash(self.all())
        now = now or _now()
        ev = list(evidence or [])
        best, best_sim = None, 0.0
        for c in self.active():
            s = similarity(statement, c.statement)
            if s > best_sim:
                best, best_sim = c, s
        if best is not None and best_sim >= REINFORCE:
            merged = [e for e in ev if e not in best.evidence]
            best.evidence.extend(merged)
            best.confidence = min(1.0, best.confidence + CONFIDENCE_STEP)
            self._save(best, "reinforced", before)
            return best, "reinforced"
        if best is not None and best_sim >= SUPERSEDE:
            new = Claim(statement=statement, evidence=ev, valid_at=valid_at,
                        created_at=now)
            best.status, best.invalid_at, best.superseded_by = "superseded", now, new.id
            self._save(best, "superseded", before)
            self._save(new, "created", before)
            return new, "superseded"
        new = Claim(statement=statement, evidence=ev, valid_at=valid_at,
                    created_at=now)
        self._save(new, "created", before)
        return new, "independent"

    def contradict(self, claim_id: str, by_evidence: str = "",
                   now: str | None = None) -> Claim | None:
        """Mark a claim contradicted by new evidence (no replacement)."""
        before = structure_hash(self.all())
        for c in self.all():
            if c.id == claim_id:
                c.status = "contradicted"
                c.invalid_at = now or _now()
                c.confidence = max(0.0, c.confidence - CONFIDENCE_STEP)
                if by_evidence and by_evidence not in c.evidence:
                    c.evidence.append(by_evidence)
                self._save(c, "contradicted", before)
                return c
        return None

    # -- W9: contradiction on the wrist -------------------------------------

    def latest_supersede(self) -> dict | None:
        """The newest supersede that has no resolution yet, as
        {old_id, old_statement, new_id, new_statement}. The wearable shows
        this as one line and resolves it with A (new holds) / B (old holds)."""
        resolved: set[str] = set()
        latest: dict | None = None
        for r in self.revisions():
            if r["reason"].startswith("resolved_keep_new") or r["reason"].startswith("resolved_revert"):
                resolved.add(r["claim_id"])
            elif r["reason"] == "superseded":
                latest = {"old_id": r["claim_id"]}
        if latest is None:
            return None
        # find the new claim that superseded old_id, and whether it is resolved
        by_id = {c.id: c for c in self.all()}
        old = by_id.get(latest["old_id"])
        if old is None or old.status != "superseded" or old.id in resolved:
            return None
        new = by_id.get(old.superseded_by or "")
        return {
            "old_id": old.id, "old_statement": old.statement,
            "new_id": old.superseded_by, "new_statement": new.statement if new else "",
        }

    def resolve_supersede(self, old_id: str, keep_new: bool,
                          now: str | None = None) -> Claim | None:
        """W9 resolution from the wrist. keep_new=True accepts the newer
        claim (status quo); keep_new=False reverts — the old claim is
        re-activated and the new one contradicted. Both evidence sets stay."""
        before = structure_hash(self.all())
        now = now or _now()
        by_id = {c.id: c for c in self.all()}
        old = by_id.get(old_id)
        if old is None or old.status != "superseded":
            return None
        new = by_id.get(old.superseded_by or "")
        if keep_new:
            reason = "resolved_keep_new"
        else:
            reason = "resolved_revert"
            old.status, old.invalid_at, old.superseded_by = "active", None, None
            self._save(old, reason, before)
            if new is not None:
                new.status, new.invalid_at = "contradicted", now
                self._save(new, "contradicted", before)
            return old
        self._append(self.revisions_path, {
            "ts": now, "claim_id": old.id, "reason": reason,
            "hash_before": before, "hash_after": structure_hash(self.all()),
        })
        return new


def structure_hash(claims: list[Claim]) -> str:
    """Stable hash of claim structure (34 Phase 2d): statements, status,
    confidence, and temporal boundaries — NOT ids or timestamps, so the same
    belief state hashes equal across sessions and model swaps. A change in
    this hash without a Revision is a bug, not an update."""
    rows = sorted(
        (c.statement.strip().lower(), c.status, round(c.confidence, 3),
         c.valid_at or "", c.invalid_at or "")
        for c in claims
    )
    blob = json.dumps(rows, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
