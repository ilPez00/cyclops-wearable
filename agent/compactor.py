"""Memory compaction — distill old cards into a few durable facts.

merlin's MemoryCompressor port. The learning loop appends one card per turn,
so MEMORY.md grows without bound (the FIFO cap in MemoryStore just drops the
oldest — losing information). Compaction instead *distills*: an LLM folds a
batch of older cards into <=N durable facts, writes one compressed card, and
removes the originals. Offline-safe: no router -> no-op (nothing lost).
"""

from __future__ import annotations

import json

# NB: contains literal JSON braces, so substitute with replace, not .format()
_COMPACT_PROMPT = (
    "You compress an AI's long-term memory. Given many small memory cards, "
    "distill them into AT MOST __N__ durable, high-value facts — merge "
    "duplicates, drop the ephemeral, keep what stays true. Each fact one "
    "declarative sentence under 200 chars. Return STRICT JSON only: "
    '{"facts":["...","..."]}.'
)


def _extract_facts(text: str) -> list[str]:
    if not text:
        return []
    t = text.strip()
    s, e = t.find("{"), t.rfind("}")
    if s == -1 or e <= s:
        return []
    try:
        obj = json.loads(t[s : e + 1])
    except Exception:
        return []
    facts = obj.get("facts", []) if isinstance(obj, dict) else []
    return [str(f).strip()[:200] for f in facts if str(f).strip()][:12]


def compact(
    store,
    target: str = "agent",
    router=None,
    keep_recent: int = 20,
    batch_min: int = 30,
    max_facts: int = 8,
) -> dict:
    """Distill old cards for `target` into <=max_facts durable cards.

    Only runs when there are more than keep_recent + batch_min cards, so the
    newest `keep_recent` are never touched. Returns a summary; no-op (and no
    data loss) when there's no router or too little to compact.
    """
    cards = [c.text for c in store.list(target=target)]
    n = len(cards)
    if router is None or n < keep_recent + batch_min:
        return {"compacted": 0, "removed": 0, "cards": n}
    old = cards[: n - keep_recent]  # everything except the newest keep_recent
    try:
        prompt = _COMPACT_PROMPT.replace("__N__", str(max_facts))
        res = router.chat(
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": "\n".join(f"- {c}" for c in old)},
            ]
        )
        facts = _extract_facts(getattr(res, "text", "") or "")
    except Exception:
        return {"compacted": 0, "removed": 0, "cards": n, "error": "review failed"}
    if not facts:
        return {"compacted": 0, "removed": 0, "cards": n}
    # remove the old cards (highest index first so positions stay valid), then
    # append the distilled facts as new cards
    for i in range(len(old) - 1, -1, -1):
        store.delete(i, target=target)
    for f in facts:
        store.append(f, target=target)
    return {
        "compacted": len(facts),
        "removed": len(old),
        "cards": len(facts) + keep_recent,
    }


__all__ = ["compact"]
