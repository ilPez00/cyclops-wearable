# docs/34-measurements — Phase 0 baseline numbers

Status: **complete, 3 of 3** (2026-10-04). Satisfies the `docs/34` Phase 0 gate
("no gate, no Phase 1"). Every number here is reproducible: fixtures are fixed in
`tests/fixtures/`, floors are machine-readable, and CI asserts them.

Method note that governs all three: these are **harnesses, not claims about the
real world.** Where a number comes from an authored fixture rather than real data,
it says so in the same breath, because a comfortable fixture number quoted without
its caveat is worse than no number at all.

| # | item | result | where |
|---|---|---|---|
| 0a | retrieval baseline | shipping **MRR@10 0.6771** / recall 0.9375; best reference (BM25) **0.8750** / 1.0000 | `tests/test_retrieval_baseline.py` |
| 0b | declared-never-called | **736 symbols swept, 0 confirmed dead** after allowlist (1 real find, 6 false positives) | `scripts/dead_calls.py` |
| 0c | model-swap invariance | **structure does NOT survive the swap** (5 of 10 transcripts diverge) | `scripts/swap_probe.py` |

---

## 0a — Retrieval

Corpus: `tests/fixtures/retrieval_corpus.jsonl` (44 docs, 28 chatter + 16 planted
facts). Queries: `retrieval_queries.json` (16, each with gold ids). k=10.

| ranker | MRR@10 | recall@10 |
|---|---|---|
| **current** — `brain/store.py:61` token overlap, what ships | **0.6771** | 0.9375 |
| BM25 — hand-rolled, `k1=1.2 b=0.75`, zero deps | **0.8750** | 1.0000 |
| RRF(2 arms) — token-overlap + BM25 | 0.7031 | 1.0000 |
| physis-next MCP | **unavailable** — see below | — |

Floors: `tests/fixtures/retrieval_baseline_floor.json`. CI fails if shipping
retrieval drops below 0.6771, and fails if no reference arm stays ahead of it.

**Two findings that correct the plan rather than confirm it:**

1. **"BM25+RRF is the bar" (docs/34) does not hold as written.** A two-arm RRF
   scored *below* BM25 alone (0.7031 vs 0.8750): fusing a weak arm in costs
   accuracy, and there is no embedder available offline to add a semantic third
   arm. So the reference is BM25 alone, and the real BM25+RRF bar remains
   **NOT MEASURED** — claimed from a fusion that does not earn it.
2. **The first fixture was too easy and inverted the result.** An initial
   planted-facts-only corpus scored current 0.9688 vs BM25 0.9375 — shipping code
   "winning". That fixture measured nothing, because every query word appeared
   only in its gold document. Rebuilt with process chatter carrying the topic
   words and the distinguishing token (name, date, serial) in the short note,
   which is what real notes look like.

**Honest scope.** The corpus is authored, so absolute scores are generous. This
number measures the *gap* between rankers and pins that gap as a regression
floor. It is **not** evidence about retrieval over a year of real notes —
`~/.cyclops` held **no** `notes/sightings/experiences/events` stores at all when
this ran, so the real-corpus figure stays **NOT MEASURED** until it does.

**physis-next arm: unavailable, not skipped.** Port 19876 is held by the retired
`physis-pro-web` (pid 8360, bound 0.0.0.0), so every `POST /mcp` returns
`404 Not Found` and `brain/physis_next.py:status()` reports
`reachable: False`. The CLI fallback runs but finds an empty observation log
(cyclops was never `observe`d into physis-next), so it returns `(no results)` —
a non-empty string, which means `agent/tools/physis.py:recall` presents total
failure as a successful empty recall. Pinned by
`test_physis_next_arm_is_recorded_unavailable_not_skipped`. Not fixed here; it
needs a service decision, and services on pansa/omo are off limits by instruction.

## 0b — Declared-never-called

`python3 scripts/dead_calls.py` → **CLEAN (736 symbols, all called or
allowlisted)**, exit 0. Allowlist grew 40 → 58 lines.

7 symbols were flagged. Adjudicated individually:

- **6 are false positives from a real blind spot.** `AgentActivity`,
  `CameraActivity`, `CoherenceActivity`, `ConceptsActivity`, `FilesActivity`,
  `LifeOSActivity` are all declared in `android/app/src/main/AndroidManifest.xml`
  and launched by the Android OS. The scanner reads code references only and
  cannot see manifest-declared components. Allowlisted with the manifest as the
  stated reason; **decision open** — teach `dead_calls.py` to read the manifest
  and drop these six, so the gate stops crying wolf.
- **1 is genuinely dead:** `Planner.kt:extend`, a one-line wrapper
  (`tokens.forEach { register(it) }`) superseded by calling `register()`
  directly, with zero call sites including tests. Allowlisted, not deleted, per
  the allowlist-only decision for this phase.

**The gate had no enforcement at all.** `scripts/dead_calls.py` exits 1 by
design but was not referenced by any workflow, so "CLEAN" was never checked by
anything. Now wired into `.github/workflows/ci.yml`.

**Pre-existing CI rot found on the way.** The firmware build matrix named
`xiao_st7735`, `xiao_128x64`, `xiao_128x32`, `xiao_transparent_151` — **none of
which exist** in `firmware/platformio.ini` (or `firmware/mini4/platformio.ini`).
Zero overlap with the real envs. Matrix last synced 2026-07-10, before the `_i2c`
renames, so every matrix job had been failing to resolve its environment. Matrix
corrected to `[xiao_128x32_i2c, feather_128x32_i2c]`, and `xiao_mini4` given its
own step since it is a separate PlatformIO project.

## 0c — Model-swap invariance

Evidence: `tests/fixtures/swap_probe_transcripts.jsonl`, 10 fixed transcripts.
Arms are two different families, both free:

- `space-bunny-free` — Zen, keyless
- `nvidia/nemotron-3.5-lightning:free` — OpenRouter `:free`, measured cost 0

**Result: structure does NOT survive the swap.**

```
space-bunny-free                   ef1287d3dc406d37   14 notes, 1 due resolved
nvidia/nemotron-3.5-lightning:free 9412a5c37bc9f17f   15 notes, 0 dues resolved
type histogram  space-bunny {task 5, decision 3, summary 3, reminder 2, idea 1}
               nemotron    {task 7, decision 2, summary 3, reminder 2, idea 1}
confidence mean 0.985 vs 0.8833
```

5 of 10 transcripts diverge in the `(type, due)` multiset:

| transcript | divergence |
|---|---|
| t01 | space-bunny resolved "by Friday" to `2026-10-09`; nemotron left it null |
| t03 | space-bunny emitted an extra `summary` |
| t04 | nemotron split one item into `summary` + `task` |
| t08 | nemotron emitted an extra `task` |
| t09 | **same text, `decision` vs `task`** |

**Consequence.** `docs/34` licenses "prose beside state with attribution"
*conditional on structure being stable*. It is not stable, so that licence is
**not granted**. Model-extracted `(type, due)` cannot be treated as the belief
substrate. It stays derived-and-disposable, and the ledger's deterministic
machinery plus human confirmation keep owning all state.

The sharpest finding is that **confidence is not a proxy for structural
agreement**: both models report high confidence (0.985 / 0.883) while disagreeing
on half the transcripts, including a straight type conflict on t09. Type drives
routing and urgency, so this matters beyond bookkeeping.

**Scope correction found while building this.** `docs/34` asks for
"entities + topology + grades", but entity extraction in this codebase is
**deterministic keyword tagging**, not model-derived — the retired physis-pro
`classify` call was replaced by `CYCLOPS_ENRICH_ENTITIES`. A model swap therefore
*cannot* perturb entity structure today, so that part of the question is
**DEFERRED**, not passed. What the model actually drives is Note extraction via
`brain/llm_extractor.py`, and that is what was measured. `grades` come from
explicit feedback (`brain/experiences.py`), not from extraction, so they are
likewise out of scope for a transcript-in probe.

Confidence is deliberately **excluded from the hash** — it is a raw float, and
hashing it would let float noise read as structural agreement. It is reported
bucketed instead.

**Reproduction.** `python3 scripts/swap_probe.py` (manual, never in CI: it needs
network egress and both endpoints are rate limited). Results land in
`docs/34-swap-probe-results.json`, prose side by side in
`docs/34-swap-probe-prose.md`. The probe refuses to report
a comparison if any arm fell back to the rule-based extractor — an earlier run
did, and it was rejected rather than recorded as a model result. Both models emit
reasoning before content (`reasoning_content`, 175+ tokens on nemotron), so token
budgets must exceed it or content arrives empty.

---

## What is still NOT MEASURED

- **Retrieval over real notes.** No real stores exist yet; 0a is a fixture harness.
- **The true BM25+RRF bar.** Needs a semantic arm; no embedder is available offline.
- **Swap invariance of entities / topology / grades.** Blocked on entity
  extraction becoming model-derived at all.
- **Everything requiring metal.** No board attached; VAD-as-event-field, audio
  E2E and the heartbeat fix's field behaviour all remain unverified.
- **`dead_calls.py` manifest awareness.** Six allowlisted false positives remain
  until the scanner learns to read `AndroidManifest.xml`.

## Effect on Phase 1

The `docs/34` gate is now satisfiable: three numbers exist, none of them
`NOT MEASURED` at the top level. Two of them are negative findings (retrieval is
weaker than its reference; structure is not swap-invariant), and both argue the
same way — **the deterministic ledger keeps owning state, and model output stays
advisory.** That is a stronger position than "no gate", and it is now evidence
rather than intention.