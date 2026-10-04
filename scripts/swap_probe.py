#!/usr/bin/env python3
"""Phase 0c model-swap probe: does belief STRUCTURE survive an interpreter swap?

docs/34 0c asks for the same evidence through two interpreters, then hashing
structure (entities + topology + grades) and diffing prose. If structure is
stable, prose may sit BESIDE the state with attribution, never become the thing
contradiction is computed against.

Scope correction, found while building this and recorded rather than papered
over: entities/topology are NOT model-derived in this codebase today. Entity
extraction is deterministic keyword tagging (STATUS 2026-09-28: it replaced the
dead physis-pro classify call with CYCLOPS_ENRICH_ENTITIES). A model swap
therefore cannot perturb entity structure at all, so that part of the 0c
question is DEFERRED until an LLM entity path exists. What the model actually
drives is Note extraction via brain.llm_extractor.LLMExtractor, so that is what
this probe measures:

  structure = the multiset of (note.type, note.due) the model emitted, hashed.
              Confidence is a raw float and is NOT hashed -- it is reported as a
              bucketed comparison instead, so float noise cannot masquerade as
              structural agreement or disagreement.
  prose     = note.text, written out side by side for human diffing.

Manual, never in CI: it needs network egress and both endpoints are rate
limited. Results are committed to docs/34-measurements.md; CI asserts only the
recorded numbers.

Usage:
    python3 scripts/swap_probe.py                 # both arms, writes results
    python3 scripts/swap_probe.py --only zen      # one arm
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from brain.llm_extractor import LLMExtractor  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "swap_probe_transcripts.jsonl")
OUT_JSON = os.path.join(ROOT, "docs", "34-swap-probe-results.json")
OUT_PROSE = os.path.join(ROOT, "docs", "34-swap-probe-prose.md")

# A User-Agent is mandatory on the Zen edge: without one Cloudflare answers 403
# code 1010 and every model looks broken for entirely the wrong reason.
UA = "cyclops-swap-probe/1.0"


class ProbeDegraded(RuntimeError):
    """The model did not return usable content. Distinct so it is never confused
    with a transport error, and never silently replaced by rule-based output."""


class HttpChat:
    """Minimal OpenAI-compatible client. Injected into LLMExtractor so no repo
    code needs changing to point the pipeline at a new endpoint."""

    def __init__(self, url, model, api_key=None, max_tokens=512, timeout=120, extra=None):
        self.url = url
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra = extra or {}
        self.last_error = None

    def complete(self, messages, model=None, temperature=0.0):
        body = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            "max_tokens": self.max_tokens,
        }
        body.update(self.extra)
        payload = json.dumps(body).encode()
        headers = {"Content-Type": "application/json", "User-Agent": UA}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        req = urllib.request.Request(self.url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            body = json.loads(r.read().decode())
        try:
            msg = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            self.last_error = "no choices[0].message: %s" % str(body)[:160]
            raise ProbeDegraded(self.last_error) from e
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            # A reasoning-only reply looks exactly like this. Never let it turn
            # into rule-based notes wearing the model's name.
            self.last_error = "empty content (keys=%s)" % sorted(msg.keys())
            raise ProbeDegraded(self.last_error)
        return content


def arms():
    """Two genuinely different model families, both free.

    Zen's free tier refuses external callers with 403 "free tier can only be
    used from within OpenCode" for every model except space-bunny-free, so the
    Zen arm is fixed. Nemotron comes from OpenRouter's :free tier (cost 0
    confirmed) rather than Zen, where it is blocked.
    """
    from brain.aikeys import AiKeys

    or_key = AiKeys().provider("openrouter").get("key")
    return [
        {
            "arm": "space-bunny-free",
            "family": "zen-keyless",
            "client": HttpChat(
                "https://opencode.ai/zen/v1/chat/completions",
                "space-bunny-free",
                max_tokens=2048,
            ),
        },
        {
            "arm": "nvidia/nemotron-3.5-lightning:free",
            "family": "openrouter-free",
            "client": HttpChat(
                "https://openrouter.ai/api/v1/chat/completions",
                "nvidia/nemotron-3.5-lightning:free",
                api_key=or_key,
                # reasoning model: ~175+ tokens thinking before answering, so
                # a small budget truncates before any content is emitted.
                # effort=low bounds the thinking instead of truncating.
                max_tokens=4096,
                extra={"reasoning": {"effort": "low"}},
            ),
        },
    ] if or_key else []


def load_evidence():
    rows = []
    with open(FIXTURE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def structure(notes):
    """The part that must not depend on who interpreted the text."""
    return sorted((n.type or "summary", n.due or "") for n in notes)


def run_arm(arm, evidence, retries=3):
    ex = LLMExtractor(client=arm["client"], provider="openrouter", model=arm["arm"])
    # CRITICAL: LLMExtractor falls back to the rule-based extractor on ANY
    # exception. Left alone, a flaky endpoint yields a hash of rule output that
    # looks like a model result. Make the fallback record itself and return
    # nothing, so a degraded transcript is visible as zero notes instead.
    degraded = []

    def _sentinel(text):
        degraded.append("%s | %s" % (text[:44], arm["client"].last_error))
        return []

    ex._fallback = _sentinel

    per_transcript, all_notes = [], []
    for row in evidence:
        notes = []
        for _ in range(retries):
            try:
                notes = ex.extract(row["text"])
                break
            except Exception:  # noqa: BLE001
                time.sleep(3)
        all_notes.extend(notes)
        per_transcript.append({
            "id": row["id"],
            "count": len(notes),
            "structure": structure(notes),
        })
    struct = structure(all_notes)
    conf = [float(getattr(n, "confidence", 0.0) or 0.0) for n in all_notes]
    buckets = sorted(round(c, 1) for c in conf)
    hist = {}
    for t, _ in struct:
        hist[t] = hist.get(t, 0) + 1
    return {
        "arm": arm["arm"],
        "family": arm["family"],
        "valid": not degraded,          # False => hash is NOT a model-only result
        "degraded_transcripts": len(degraded),
        "degraded_detail": degraded,
        "notes_total": len(all_notes),
        "type_histogram": dict(sorted(hist.items())),
        "dues_resolved": sum(1 for _, d in struct if d),
        "confidence_buckets": buckets,
        "confidence_mean": round(sum(conf) / len(conf), 4) if conf else None,
        "structure_sha256": hashlib.sha256(
            json.dumps(struct, sort_keys=True).encode()
        ).hexdigest(),
        "per_transcript": per_transcript,
        "prose": [{"text": n.text, "type": n.type} for n in all_notes],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    evidence = load_evidence()
    results = []
    for arm in arms():
        if args.only and args.only not in arm["arm"]:
            continue
        print("running arm %s ..." % arm["arm"], flush=True)
        results.append(run_arm(arm, evidence))

    if len(results) == 2:
        a, b = results
        print("\nvalidity: %s=%s (%d degraded)  %s=%s (%d degraded)"
              % (a["arm"][:20], a["valid"], a["degraded_transcripts"],
                 b["arm"][:20], b["valid"], b["degraded_transcripts"]))
        if not (a["valid"] and b["valid"]):
            print("STRUCTURE COMPARISON INVALID: an arm fell back to rules; "
                  "hash would not be model-only. Re-run before recording.")
            same = None
        else:
            same = a["structure_sha256"] == b["structure_sha256"]
            print("structure match: %s" % same)
            print("  %-34s %s" % (a["arm"], a["structure_sha256"][:16]))
            print("  %-34s %s" % (b["arm"], b["structure_sha256"][:16]))
            print("  notes %d vs %d ; dues %d vs %d"
                  % (a["notes_total"], b["notes_total"], a["dues_resolved"], b["dues_resolved"]))
    else:
        same = None

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "probe": "docs/34 phase 0c model-swap",
            "evidence": "tests/fixtures/swap_probe_transcripts.jsonl (%d transcripts)" % len(evidence),
            "structure_definition": "sorted multiset of (note.type, note.due); confidence excluded (float noise)",
            "deferred": "entities/topology/grades: entity extraction is deterministic keyword tagging, not model-derived, so a swap cannot perturb them yet",
            "arms": results,
        }, f, indent=2, ensure_ascii=False)

    with open(OUT_PROSE, "w", encoding="utf-8") as f:
        f.write("# 0c prose diff -- generated by scripts/swap_probe.py\n\n")
        f.write("Structure is hashed; this file is the human-readable half.\n\n")
        for r in results:
            f.write("## %s (`%s`)\n\n" % (r["arm"], r["family"]))
            f.write("notes: %d, dues resolved: %d, confidence mean: %s\n\n"
                    % (r["notes_total"], r["dues_resolved"], r["confidence_mean"]))
            for p in r["prose"]:
                f.write("- **[%s]** %s\n" % (p["type"], p["text"]))
            f.write("\n")
    print("wrote %s and %s" % (OUT_JSON, OUT_PROSE))
    return 0


if __name__ == "__main__":
    sys.exit(main())