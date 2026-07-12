"""Per-provider token + cost accounting (merlin CostTracker port).

The router fires calls across many providers (see agent/cascade.py); this
tallies tokens and estimated USD per provider so the user can see spend.
Offline-safe: unknown providers/models cost 0, tallies still accrue tokens.
JSONL-persisted under ~/.cyclops/ following the NoteStore pattern.
"""

from __future__ import annotations

import json
import os
import threading

# Rough $/1M tokens (input, output). Coarse on purpose — a ballpark, not a bill.
PRICING = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.0),
    "groq": (0.10, 0.10),
    "openrouter": (0.50, 1.50),
    "anthropic": (1.00, 5.00),
    "deepinfra": (0.10, 0.10),
    "together": (0.20, 0.20),
    "gemini": (0.10, 0.40),
    "mistral": (0.25, 0.25),
}


def _price(provider: str, model: str) -> tuple[float, float]:
    if model in PRICING:
        return PRICING[model]
    return PRICING.get((provider or "").lower(), (0.0, 0.0))


class CostTracker:
    def __init__(self, path: str = "~/.cyclops/costs.jsonl"):
        self.path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.Lock()

    def record(self, provider: str, model: str, in_tok: int, out_tok: int) -> float:
        """Log one call; returns its estimated USD."""
        pin, pout = _price(provider, model)
        usd = (in_tok / 1_000_000) * pin + (out_tok / 1_000_000) * pout
        row = {
            "provider": provider or "",
            "model": model or "",
            "in": int(in_tok),
            "out": int(out_tok),
            "usd": round(usd, 6),
        }
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        return usd

    def summary(self) -> dict:
        """Totals per provider + grand total."""
        by: dict[str, dict] = {}
        total = {"in": 0, "out": 0, "usd": 0.0, "calls": 0}
        if not os.path.exists(self.path):
            return {"providers": {}, "total": total}
        with self._lock, open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                p = r.get("provider", "")
                b = by.setdefault(p, {"in": 0, "out": 0, "usd": 0.0, "calls": 0})
                for k in ("in", "out"):
                    b[k] += int(r.get(k, 0))
                    total[k] += int(r.get(k, 0))
                b["usd"] += float(r.get("usd", 0.0))
                total["usd"] += float(r.get("usd", 0.0))
                b["calls"] += 1
                total["calls"] += 1
        for b in by.values():
            b["usd"] = round(b["usd"], 4)
        total["usd"] = round(total["usd"], 4)
        return {"providers": by, "total": total}


__all__ = ["CostTracker", "PRICING"]
