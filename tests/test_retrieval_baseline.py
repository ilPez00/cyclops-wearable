"""Phase 0a retrieval baseline: what ships today vs the BM25+RRF bar.

docs/34 requires a recorded retrieval number before Phase 1, and requires it to
be a harness rather than a claim. This file is that harness:

  * fixtures are fixed in tests/fixtures/ so the number is reproducible
  * ranker `current` is the SHIPPING code path (brain/store.py NoteStore.search),
    not a reimplementation, so the number describes what users get
  * rankers `bm25` and `rrf` are hand-rolled in-test (zero new dependencies;
    pytest, rank_bm25 etc. are all unavailable/undesired in this repo)
  * physis-next is recorded UNAVAILABLE with its measured reason, never skipped
    silently (it answers 404 on the default port -- see docs/34-measurements.md)

Honest scope, stated in the file that holds the number: the corpus is authored
with planted facts, so absolute scores are generous. It measures the GAP between
rankers and pins that gap as a regression floor. It is not evidence about
retrieval over a year of real notes. The real-corpus figure stays NOT MEASURED
until ~/.cyclops holds real stores.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain.extractor import Note
from brain.store import NoteStore

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
CORPUS = os.path.join(FIX, "retrieval_corpus.jsonl")
QUERIES = os.path.join(FIX, "retrieval_queries.json")
FLOOR = os.path.join(FIX, "retrieval_baseline_floor.json")

K = 10


def load_corpus():
    docs = []
    with open(CORPUS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(json.loads(line))
    return docs


def load_queries():
    with open(QUERIES, encoding="utf-8") as f:
        return json.load(f)


def note_store(docs):
    """A NoteStore over the fixture, with no write to ~/.cyclops."""
    tmp = os.path.join(tempfile.mkdtemp(prefix="cyclops-rb-"), "notes.jsonl")
    st = NoteStore(path=tmp)
    st.notes = [
        Note(id=d["id"], type="summary", text=d["text"], created="2026-01-01")
        for d in docs
    ]
    return st


def rank_current(docs, query, k=K):
    """Exactly what ships: brain/store.py token overlap."""
    st = note_store(docs)
    return [n.id for n in st.search(query, k=k)]


_WORD = re.compile(r"[a-z0-9]+")


def words(text):
    return _WORD.findall(text.lower())


def rank_bm25(docs, query, k=K, k1=1.2, b=0.75):
    """Textbook BM25, standard tokenisation, zero dependencies."""
    toks = [words(d["text"]) for d in docs]
    n = len(toks)
    df = {}
    for t in toks:
        for w in set(t):
            df[w] = df.get(w, 0) + 1
    avgdl = sum(len(t) for t in toks) / n
    q = words(query)
    scored = []
    for i, t in enumerate(toks):
        tf = {}
        for w in t:
            tf[w] = tf.get(w, 0) + 1
        dl = len(t) or 1
        s = 0.0
        for w in q:
            if w not in tf:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * (tf[w] * (k1 + 1)) / (tf[w] + k1 * (1 - b + b * dl / avgdl))
        scored.append((-s, i))
    scored.sort()  # ties keep corpus order, matching the shipping sort
    return [docs[i]["id"] for _, i in scored[:k]]


def rrf(rank_lists, k=60):
    """Reciprocal rank fusion. Lower-bounds the real bar: with no embedder
    available offline there is no semantic third arm to fuse in."""
    score = {}
    for ids in rank_lists:
        for pos, doc_id in enumerate(ids):
            score[doc_id] = score.get(doc_id, 0.0) + 1.0 / (k + pos + 1)
    return sorted(score, key=lambda d: (-score[d], d))


def rank_rrf(docs, query, k=K):
    return rrf([rank_current(docs, query, k=k), rank_bm25(docs, query, k=k)])[:k]


def metrics(docs, query_spec, ranker):
    gold = set(query_spec["gold"])
    ranked = ranker(docs, query_spec["q"])[:K]
    rr = 0.0
    for pos, doc_id in enumerate(ranked, start=1):
        if doc_id in gold:
            rr = 1.0 / pos
            break
    recall = len(gold & set(ranked)) / len(gold)
    return rr, recall


def score_all(ranker, docs=None, queries=None):
    docs = docs or load_corpus()
    queries = queries or load_queries()
    rrs, recalls = [], []
    for q in queries:
        rr, rc = metrics(docs, q, ranker)
        rrs.append(rr)
        recalls.append(rc)
    m = len(rrs)
    return sum(rrs) / m, sum(recalls) / m


def test_corpus_and_queries_are_wellformed():
    docs = load_corpus()
    queries = load_queries()
    ids = [d["id"] for d in docs]
    assert len(docs) >= 30, "corpus too small to rank meaningfully"
    assert len(set(ids)) == len(ids), "duplicate doc id in corpus"
    assert len(queries) >= 10, "too few queries for a stable MRR"
    for d in docs:
        assert d["text"].strip(), "empty document %s" % d["id"]
    for q in queries:
        assert q["gold"], "query without gold: %r" % q["q"]
        for g in q["gold"]:
            assert g in ids, "gold id %s not in corpus" % g


def test_current_ranker_meets_recorded_floor():
    """The regression gate. If retrieval degrades, CI fails instead of a human
    noticing. Floor lives in fixtures so there is one machine-readable source;
    docs/34-measurements.md cites it."""
    with open(FLOOR, encoding="utf-8") as f:
        floor = json.load(f)
    mrr, recall = score_all(rank_current)
    assert mrr >= floor["current_mrr"], (
        f"current MRR {mrr:.4f} below recorded floor {floor['current_mrr']:.4f} "
        f"({floor['source']})"
    )
    assert recall >= floor["current_recall"], (
        f"current recall {recall:.4f} below floor {floor['current_recall']:.4f}"
    )


def test_best_reference_ranker_is_ahead_of_shipping():
    """The point of the exercise: document the gap.

    docs/34 names "BM25+RRF" as the bar. Measured here, a two-arm RRF of
    {token-overlap, BM25} scores BELOW BM25 alone -- fusing a weak arm in costs
    accuracy, and with no embedder available offline there is no semantic third
    arm to rescue it. So the reference is the best measured arm (BM25 alone on
    this corpus), and the true BM25+RRF bar stays NOT MEASURED rather than being
    claimed from a fusion that does not earn it.
    """
    with open(FLOOR, encoding="utf-8") as f:
        floor = json.load(f)
    cur_mrr, cur_recall = score_all(rank_current)
    arms = {
        "bm25": score_all(rank_bm25),
        "rrf": score_all(rank_rrf),
    }
    best = max(arms.items(), key=lambda kv: kv[1][0])
    ref_mrr, ref_recall = best[1]
    assert ref_mrr >= floor["reference_mrr"] - 1e-9, (
        f"reference ({best[0]}) MRR {ref_mrr:.4f} below recorded {floor['reference_mrr']:.4f}"
    )
    assert ref_mrr > cur_mrr, (
        f"no measured arm beats shipping code any more: {ref_mrr:.4f} vs {cur_mrr:.4f}"
    )
    assert ref_recall > cur_recall, (
        f"reference recall no longer ahead: {ref_recall:.4f} vs {cur_recall:.4f}"
    )


def test_every_query_is_retrievable_at_all():
    """Guards a degenerate fixture: if BM25 returns nothing for a query, the
    comparison is measuring zero-vs-zero rather than rankers."""
    docs, queries = load_corpus(), load_queries()
    for q in queries:
        assert rank_bm25(docs, q["q"]), "bm25 returned nothing for %r" % q["q"]


def test_physis_next_arm_is_recorded_unavailable_not_skipped():
    """docs/34 asks for four arms. The physis arm is unreachable, and that fact
    must be pinned here so it cannot quietly become a fifth claim later.
    Asserted from code/config only -- this test performs no network call."""
    from brain import physis_next as px

    assert px.DEFAULT_URL.endswith("127.0.0.1:19876"), (
        "physis-next default moved; re-measure the availability finding"
    )
    assert hasattr(px, "PhysisNextUnavailable"), "bridge lost its degrade contract"