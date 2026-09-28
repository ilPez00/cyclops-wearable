"""Jev oracle (docs/41 §2): TypeSafe System One as a read-only decision aid.

Jev answers typed questions about a state — noul/choice/score with calibrated
probabilities — and scores claims. It NEVER authors: no create, contradict,
supersede, or resolve. Its outputs feed thresholds in code; the ledger's
deterministic machinery + human confirm own all authorship.

Key absent (waitlisted as of 2026-09) -> every method returns None and the
caller proceeds without the oracle. All paths are offline-testable with an
injected transport. Endpoint: POST https://api.typesafe.ai/v1/systemone.
"""

from __future__ import annotations

import json

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"

# Thresholds live here, named, next to the numbers they gate.
SCORE_THRESHOLD = 0.9
AUTO_ROUTE_CONFIDENCE = 0.85


def _default_session():
    from brain.http_session import stdlib_session

    return stdlib_session()


class JevOracle:
    def __init__(self, keys=None, session=None):
        from .aikeys import AiKeys

        self._keys = keys or AiKeys()
        self.session = session or _default_session()

    @property
    def key(self) -> str | None:
        return self._keys.get_key("typesafe")

    @property
    def available(self) -> bool:
        return bool(self.key)

    def _post(self, state, questions: dict) -> dict | None:
        """Raw system-one call. Returns the `answers` map, or None."""
        if not self.available:
            return None
        body = json.dumps(
            {"model": JEV_MODEL, "state": state, "questions": questions}
        ).encode()
        try:
            resp = self.session.post(
                JEV_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.key}",
                },
                timeout=60,
            )
        except Exception:
            return None
        status = getattr(resp, "status", 200)
        if status and status >= 400:
            return None
        try:
            return (resp.json() or {}).get("answers")
        except Exception:
            return None

    def noul(self, state, instructions: str, true: str, false: str) -> float | None:
        """Yes/no probability that the state matches `true` over `false`."""
        ans = self._post(
            state,
            {"q": {"type": "noul", "instructions": instructions,
                   "criteria": {"true": true, "false": false}}},
        )
        try:
            return float(ans["q"]["noul"])
        except (TypeError, KeyError, ValueError):
            return None

    def choice(self, state, instructions: str,
               options: dict[str, str]) -> tuple[str, float] | None:
        """(winning option, confidence) from the named options."""
        ans = self._post(
            state,
            {"q": {"type": "choice", "instructions": instructions,
                   "criteria": options}},
        )
        try:
            q = ans["q"]
            return str(q["choice"]), float(q.get("confidence", 0.0))
        except (TypeError, KeyError, ValueError):
            return None

    def score(self, state, instructions: str,
              levels: list[str]) -> float | None:
        """Probability-weighted position across the ordered levels."""
        ans = self._post(
            state,
            {"q": {"type": "score", "instructions": instructions,
                   "criteria": levels}},
        )
        try:
            return float(ans["q"]["score"])
        except (TypeError, KeyError, ValueError):
            return None

    def score_claim(self, statement: str, evidence: list[str]) -> float | None:
        """Calibrated support probability for a claim given its evidence.

        Read-only: the caller decides what the number means (confidence
        adjust within [0,1], never authorship).
        """
        state = {"statement": statement, "evidence": evidence or []}
        return self.noul(
            state,
            instructions="Is the statement supported by the listed evidence?",
            true="evidence directly supports the statement",
            false="evidence is unrelated, missing, or contradicts it",
        )
