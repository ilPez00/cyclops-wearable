"""XIAO physis notes — minimal local app.

Auto record (VAD-gated) + notebook + dictation + memory.
Runs physis locally: no server, no deps, stdlib only.

Donor patterns (copied, not imported):
- physis: ngram-hash embed + cosine rank (see physis-pro embed_ngram)
- praxis notebook: daily markdown + frontmatter (see brain/obsidian.py)
- hermes loop: observe -> extract -> store (see brain/pipeline.py)

Usage:
  python3 app/physis_notes.py dictate "remind me to call marco tomorrow"
  python3 app/physis_notes.py notebook --limit 10
  python3 app/physis_notes.py memory "invoice marco"
  python3 app/physis_notes.py auto --chunks 5   # VAD-gated stub audio
  python3 app/physis_notes.py export --out /tmp/notes.md
"""
from __future__ import annotations
import argparse
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, REPO)

from brain.factory import build_pipeline
from brain.store import NoteStore
from brain.vad import EnergyVAD

STORE = os.path.expanduser("~/.cyclops/notes.jsonl")


def _embed(text: str, dim: int = 128) -> list[float]:
    """Physis-ngram pattern: hash tokens into fixed vector, L2 norm."""
    v = [0.0] * dim
    for tok in re.findall(r"\w+", text.lower()):
        v[hash(tok) % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def memory_search(store: NoteStore, q: str, k: int = 5):
    """Local physis: semantic rank over NoteStore, stdlib only."""
    qv = _embed(q)
    scored = []
    for n in store.all():
        scored.append((_cos(qv, _embed(n.text)), n))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for s, n in scored[:k] if s > 0]


def cmd_dictate(args):
    p = build_pipeline(store_path=args.store)
    notes = p.process_text(args.text)
    for n in notes:
        print(f"[{n.type}] {n.text}" + (f" (due {n.due})" if n.due else ""))
    return 0


def cmd_notebook(args):
    s = NoteStore(args.store)
    notes = s.all()[-args.limit :]
    for n in notes:
        print(f"{n.created[:16]} [{n.type}] {n.text}")
    print(f"total={len(s.all())} vault={os.environ.get('CYCLOPS_OBSIDIAN_VAULT','off')}")
    return 0


def cmd_memory(args):
    s = NoteStore(args.store)
    for n in memory_search(s, args.query, args.limit):
        print(f"[{n.type}] {n.text} _{n.created[:10]}_")
    return 0


def cmd_auto(args):
    """Auto record: VAD-gated stub PCM -> Pipeline. USB test path."""
    import struct
    p = build_pipeline(store_path=args.store)
    vad = EnergyVAD()
    # loud chunk = 440Hz sine, quiet = zeros. Deterministic, no mic needed.
    loud = b"".join(struct.pack("<h", int(12000 * math.sin(i / 8))) for i in range(2048))
    quiet = b"\x00" * 4096
    fired = 0
    for i in range(args.chunks):
        chunk = loud if i % 2 == 0 else quiet
        if vad.is_active(chunk):
            p.process_audio(chunk)
            fired += 1
    print(f"auto: {fired}/{args.chunks} speech segments stored -> {args.store}")
    return 0


def cmd_export(args):
    s = NoteStore(args.store)
    txt = s.dump_markdown(args.out)
    print(f"exported {len(s.all())} notes -> {args.out} ({len(txt)} chars)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="XIAO physis notes (local)")
    ap.add_argument("--store", default=STORE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dictate")
    d.add_argument("text")
    d.set_defaults(fn=cmd_dictate)
    n = sub.add_parser("notebook")
    n.add_argument("--limit", type=int, default=10)
    n.set_defaults(fn=cmd_notebook)
    m = sub.add_parser("memory")
    m.add_argument("query")
    m.add_argument("--limit", type=int, default=5)
    m.set_defaults(fn=cmd_memory)
    a = sub.add_parser("auto")
    a.add_argument("--chunks", type=int, default=5)
    a.set_defaults(fn=cmd_auto)
    e = sub.add_parser("export")
    e.add_argument("--out", default="/tmp/physis_notes.md")
    e.set_defaults(fn=cmd_export)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
