"""Concept-based memory: fast retrieval, auto-organization, truth editing.

The phone APK's "Jarvis" surface needs three things the brain didn't have
as a unit:

1. **Fast concept retrieval** — one ranked search across notes, memory
   cards and entities. Embedding is a deterministic hashing embedder
   (zero deps, offline, no model download), the same role physis's
   RandomProjection fallback plays when no ONNX model is present. When a
   real embedder is configured it can be injected via `embedder=`.
2. **Auto-organization** — `groups()` clusters everything ever streamed or
   saved into labeled concept groups (salient-term clustering, no model),
   so the UI can render a live map instead of a flat list.
3. **Truth editing** — every correction (note text, memory card) is applied
   *plus* appended to `~/.cyclops/truth_log.jsonl` with before/after, so a
   fix is auditable and never silent.

All offline-safe. All stdlib.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time

_STOP = {
    "the", "a", "an", "of", "to", "in", "is", "it", "and", "or", "for",
    "on", "at", "with", "my", "i", "you", "me", "this", "that", "be",
    "was", "are", "as", "by", "from", "have", "has", "had", "will",
    "would", "can", "should", "about", "into", "over", "after", "up",
    "out", "its", "our", "your", "their", "his", "her", "we", "they",
    "he", "she", "them", "then", "than", "so", "if", "but", "not", "no",
}


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w not in _STOP]


class HashEmbedder:
    """Deterministic hashing embedder (hashing trick with signed buckets).

    Same input -> same unit vector, always. No model, no download, no
    network. Cosine similarity on these vectors ranks *concept overlap*
    (shared and morphologically-adjacent terms hash near each other only
    by chance — but shared exact terms dominate, which is what we want
    for a fast first-pass over notes/memory/entities).
    """

    def __init__(self, dim: int = 256):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _tokens(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if h & 1 else -1.0
            # cheap morphology: 4-char prefix shares a bucket so
            # "battery"/"batteries" partly overlap
            if len(tok) > 4:
                p = int(hashlib.md5(tok[:4].encode()).hexdigest(), 16)
                v[p % self.dim] += 0.3 if p & 1 else -0.3
        n = math.sqrt(sum(x * x for x in v))
        if n > 0:
            v = [x / n for x in v]
        return v

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed(a), self.embed(b)
        return sum(x * y for x, y in zip(va, vb))


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class ConceptIndex:
    """Unified retrieval over notes + memory cards + entities."""

    def __init__(self, store=None, memory=None, entities=None, embedder=None):
        self.store = store
        self.memory = memory
        self.entities = entities
        self.embedder = embedder or HashEmbedder()

    def items(self) -> list[dict]:
        out = []
        if self.store is not None:
            try:
                for i, n in enumerate(self.store.all()):
                    out.append({
                        "kind": "note",
                        "id": getattr(n, "id", str(i)),
                        "index": i,
                        "text": getattr(n, "text", ""),
                        "sub": getattr(n, "type", ""),
                    })
            except Exception:
                pass
        if self.memory is not None:
            for target in ("agent", "user"):
                try:
                    cards = self.memory.list(target)
                except Exception:
                    continue
                for i, c in enumerate(cards):
                    text = c.get("text") if isinstance(c, dict) else getattr(c, "text", "")
                    out.append({"kind": "memory", "id": f"{target}:{i}",
                                "index": i, "target": target, "text": text or "", "sub": target})
        if self.entities is not None:
            try:
                for r in self.entities.all():
                    notes = " ".join(r.get("notes", []) or [])
                    out.append({"kind": "entity", "id": r.get("key", ""),
                                "text": f"{r.get('name', '')} {notes}".strip(),
                                "sub": r.get("type", "thing"),
                                "seen": r.get("seen_count", 0)})
            except Exception:
                pass
        return [it for it in out if it.get("text")]

    def search(self, query: str, k: int = 10) -> list[dict]:
        """Ranked concept hits. Empty query -> most recent notes."""
        docs = self.items()
        q = (query or "").strip()
        if not q:
            notes = [d for d in docs if d["kind"] == "note"]
            return notes[-k:] if k > 0 else []
        emb = self.embedder.embed if hasattr(self.embedder, "embed") else None
        scored = []
        if emb is not None:
            try:
                qv = emb(q)
            except Exception:
                qv = []
            if qv and any(qv):
                for d in docs:
                    try:
                        dv = emb(d["text"])
                    except Exception:
                        continue
                    s = _cos(qv, dv)
                    if s > 0:
                        scored.append((s, d))
        if not scored:
            # keyword fallback (offline, exact): token overlap
            qt = set(_tokens(q))
            for d in docs:
                s = float(len(qt & set(_tokens(d["text"]))))
                if s > 0:
                    scored.append((s, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        out = []
        for s, d in scored[: max(0, k)]:
            out.append({**d, "score": round(float(s), 4)})
        return out

    def groups(self, max_groups: int = 8, max_items: int = 5) -> list[dict]:
        """Auto-organization: cluster items by salient terms.

        Salient = frequent across docs but not everywhere (df-weighted).
        Each doc joins its best group; groups ranked by size. Deterministic.
        """
        docs = self.items()
        if not docs:
            return []
        toks = [_tokens(d["text"]) for d in docs]
        n = len(docs)
        df: dict[str, int] = {}
        for t in toks:
            for w in set(t):
                df[w] = df.get(w, 0) + 1
        # salient terms: appear in >=2 docs but <=60% of docs, top by tf
        tf: dict[str, int] = {}
        for t in toks:
            for w in t:
                tf[w] = tf.get(w, 0) + 1
        cands = [w for w, c in df.items()
                 if 2 <= c <= max(2, int(n * 0.6))]
        cands.sort(key=lambda w: tf[w] / df[w], reverse=True)
        labels = cands[:max_groups]
        groups: dict[str, list[dict]] = {label: [] for label in labels}
        ungrouped = []
        for d, t in zip(docs, toks):
            best = None
            for label in labels:
                if label in t:
                    best = label
                    break
            if best is None:
                ungrouped.append(d)
            else:
                groups[best].append(d)
        out = []
        for label in labels:
            members = groups[label]
            if not members:
                continue
            out.append({
                "label": label,
                "count": len(members),
                "items": [{"kind": m["kind"], "id": m["id"],
                           "text": m["text"][:160]} for m in members[:max_items]],
            })
        out.sort(key=lambda g: g["count"], reverse=True)
        if ungrouped:
            out.append({"label": "misc", "count": len(ungrouped),
                        "items": [{"kind": m["kind"], "id": m["id"],
                                   "text": m["text"][:160]} for m in ungrouped[:max_items]]})
        return out


TRUTH_LOG = "~/.cyclops/truth_log.jsonl"


def _audit(action: str, record: dict, log_path: str = TRUTH_LOG) -> dict:
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, **record}
    try:
        path = os.path.expanduser(log_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass
    return entry


def edit_note_text(store, ref, new_text: str, log_path: str = TRUTH_LOG) -> tuple[bool, dict]:
    """Truth-edit a note by id (or int index). Rewrites the JSONL store."""
    notes = store.all()
    target = None
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        i = int(ref)
        if 0 <= i < len(notes):
            target = notes[i]
    else:
        for nn in notes:
            if getattr(nn, "id", "") == ref:
                target = nn
                break
    if target is None or not (new_text or "").strip():
        return False, {}
    before = target.text
    target.text = new_text.strip()
    try:
        store._rewrite()
    except Exception:
        return False, {}
    return True, _audit("edit_note", {"id": getattr(target, "id", ""),
                                     "before": before, "after": target.text}, log_path)


def delete_note(store, ref, log_path: str = TRUTH_LOG) -> tuple[bool, dict]:
    notes = store.all()
    idx = -1
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        idx = int(ref)
    else:
        for i, nn in enumerate(notes):
            if getattr(nn, "id", "") == ref:
                idx = i
                break
    if not 0 <= idx < len(notes):
        return False, {}
    gone = notes[idx]
    del store.notes[idx]
    try:
        store._rewrite()
    except Exception:
        return False, {}
    return True, _audit("delete_note",
                        {"id": getattr(gone, "id", ""), "before": gone.text, "after": ""},
                        log_path)


def edit_memory_card(memory, target: str, index: int, new_text: str,
                     log_path: str = TRUTH_LOG) -> tuple[bool, dict]:
    before = ""
    try:
        cards = memory.list(target)
        if 0 <= index < len(cards):
            c = cards[index]
            before = c.get("text") if isinstance(c, dict) else getattr(c, "text", "")
    except Exception:
        pass
    ok = bool(memory.edit(index, new_text, target=target)) if hasattr(memory, "edit") else False
    if not ok:
        return False, {}
    return True, _audit("edit_memory", {"target": target, "index": index,
                                       "before": before, "after": new_text.strip()}, log_path)


def read_truth_log(limit: int = 50, log_path: str = TRUTH_LOG) -> list[dict]:
    path = os.path.expanduser(log_path)
    if not os.path.exists(path):
        return []
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except Exception:
        return []
    return rows[-limit:]


__all__ = ["HashEmbedder", "ConceptIndex", "edit_note_text", "delete_note",
           "edit_memory_card", "read_truth_log", "TRUTH_LOG"]
