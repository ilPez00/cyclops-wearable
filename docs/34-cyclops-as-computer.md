# Cyclops as a computer, not a companion — full roadmap

Source: physis `computer-remake-research/notes.md` §§0–8 applied to this repo.
Thesis in one line: **three layers — OBSERVE / BELIEVE / ACT — with the model
outside as a replaceable interpreter.** Cyclops today is capture + chat-boxes
over a pile. This roadmap turns it into the substrate, in phases, each with a
gate. No phase starts until the previous gate is green.

Where cyclops stands against the survey (honest version):

| layer | has | missing |
|---|---|---|
| OBSERVE | mic→ADPCM→transcribe, zero-photo sightings, notes/sightings/experiences JSONL | no shared event primitive (no `duration`, no provenance/locator); no window/process/a11y watcher; capture-first, retrieval never measured |
| BELIEVE | implicit learning (`agent/learning.py`), explicit grades (`brain/experiences.py`), dreams, entities | model-authored prose as the memory; no contradiction / supersede / confidence; no bi-temporality; model-swap invariance unmeasured |
| ACT | terminal tool, `hud_cmd`, HITL gates, `bind()` remap | no act checks prior belief first (Gap 8); no propose-review-apply + undo |
| surface | 14 activities, HUD mirror, widget | chat-as-interface (the survey's §3 reject); phone is 14 remotes, not a viewer of one substrate |

---

## Ship status (2026-09-28)

| Item | State | Where / what is still missing |
|---|---|---|
| 1a one event ledger | **shipped** | `brain/events.py` — append-only JSONL, `duration_s` mandatory, `locator` = provenance in the primitive |
| 1b migrate writers, not readers | **started** | `/api/ingest` and `POST /api/events` append Events *beside* the stores; `HudBridge` appends a `presence` Event on device edges. Transcribe/sighting/experience writers still only write their own store |
| 4a Timeline replaces Feed/Transcript/Memory/Dreams | **partial** | `GET /api/timeline` + the Timeline tab merge ledger + notes + sightings + claims, newest-first, `source` + `locator` per row; the old tabs survive (§4c removal still pending) |
| 4b Ask with citations | **partial** | `GET|POST /api/ask` retrieves evidence first, returns `citations` + `cited`; a model that ignores the ids is reported (`note`), not hidden. Offline = deterministic ledger echo, never invented prose |
| 5b/5c sensor gaps honest | **shipped (firmware + host)** | `pres`/`pos` in `MSG_STATUS`, one `presence` Event per edge (docs/43 C5); the VAD-as-event-field half still needs a metal measurement |
| Phase 0 baselines (0a retrieval, 0c swap probe) | **open** | No numbers recorded yet — "NOT MEASURED" stays legal, implying does not |

## Phase 0 — Baselines and nulls (week 1)

Nothing here is a feature. It is the control every later phase is scored
against. `NOT MEASURED` stays legal; implication does not.

- **0a. Retrieval baseline.** `brain/memory_search.py` (or whatever answers
  "what do we know about X") vs BM25-only on the same corpus, same queries,
  fixed in `tests/`. lss's BM25+RRF is the bar; physis's 2×2 scored 0–1/7
  against a 5/7 ceiling. Expect the same shape here. The number goes in this
  doc, not in a chat log.
- **0b. Declared-never-called audit.** Port the discipline, not the script:
  list every `brain/*.py` symbol with zero non-test callers; delete or wire.
  (`sightings.py`'s SSRF guard is careful; the audit asks whether the guarded
  path is even reachable.)
- **0c. Model-swap probe.** Same evidence (10 transcripts) through two
  interpreters (e.g. omniroute default vs local). Hash structure
  (entities + topology + grades), diff prose. If structure is stable, prose
  goes *beside* state with attribution, never as the thing contradiction is
  computed against. This is the graphiti result, replicated for cyclops.

Gate: three numbers in `docs/34-measurements.md` (retrieval score, dead-symbol
count → 0, swap-invariance hash match/mismatch). No gate, no Phase 1.

---

## Phase 1 — OBSERVE: one event ledger (weeks 2–3)

Steal ActivityWatch's primitive, not its code:

```
Event {ts, duration, source, kind, body, locator}
```

- **1a.** New `brain/events.py`: append-only JSONL, `duration` mandatory
  (the field every re-implementation drops; it turns "what was happening
  while X" from a join into a query), `locator` = where it came from
  (promnesia's provenance-in-the-primitive).
- **1b.** Migrate writers, not readers: transcribe results, sightings tags,
  experience records, agent tool calls each append an Event *in addition to*
  their current store. Old stores keep working; nothing is in the write path
  (TMSU discipline — the ledger sits beside the files).
- **1c.** First real watcher: desktop a11y reader (screenpipe's
  accessibility-tree-first decision — structured state for free, event-driven
  on app switch / typing pause, never per-second screenshots). AT-SPI2 on
  this Linux box first; it is the observer physis never built.
- **1d.** Wearable frames become Events at ingest: MSG_STATUS / note /
  transcript chunks arrive with `source: wearable`, `duration` from capture
  length. The XIAO is a sensor node in the same ledger, not a separate pipe.

Gate: `tests/test_events.py` — append-only (no rewrite API exists),
duration present on every row, one query ("what was happening while
<transcript X>") answered from the ledger alone. Cost gate: watcher tick
bounded by question, not history (the 500k-observation cliff, not repeated).

---

## Phase 2 — BELIEVE: claims with evidence (weeks 4–6)

The middle is empty everywhere (survey §4). This is the phase that fills it,
and the only phase allowed to be clever.

- **2a.** `brain/claims.py`: Claim {id, statement, status: active |
  contradicted | superseded, confidence, evidence: [event ids],
  valid_at / invalid_at (world time, graphiti's primitive — answers *when
  did this stop being true*, which replay alone cannot), created_at}.
  Evidence links are to Phase-1 event ids (screenpipe's `activity_evidence`
  arithmetic: deleting one source does not erase a multiply-supported
  claim).
- **2b.** Contradiction + supersede as deterministic rules first
  (`recall`'s arithmetic is the prior art: cosine ≥0.92 reinforces,
  0.85–0.92 supersedes and lowers the old confidence, every change logged).
  LLM judging explicitly not taken (same condition as physis PH-019).
- **2c.** Experiences grades become evidence, not a parallel system:
  a grade is a claim *about* an action with the graded event as evidence.
  `agent/learning.py`'s implicit facts and `experiences.py`'s explicit
  grades converge on one store instead of two memories that disagree.
- **2d.** Structure hash (`structure_hash` generalised from physis
  `map.rs:70`): hash claims + topology + temporal boundaries. Model swap
  re-run must leave it unchanged or leave a Revision explaining why.
  A change in the hash without a Revision is a bug, not an update.

Gate: contradiction demo end-to-end (two transcripts disagree → old claim
`contradicted`, both evidence rows intact, hash changes exactly once with a
Revision). Plus the Phase-0 retrieval number re-measured: belief-layer
queries must beat the BM25 baseline or Phase 2 is reverted to a branch
(Gap 13 — the structure must pay for itself).

---

## Phase 3 — ACT: actions checked against belief (week 7)

Gap 8: nothing notices when its own action contradicts what it holds.
`act.rs` is the only prior art; port the shape.

- **3a.** Pre-act check: every agent tool with side effects (terminal, settings
  write, hud_cmd, oauth) first surfaces `Contradicted`/relevant claims about
  its target. A contradiction does not block — it attaches to the HITL gate
  that already exists (`brain/hitl.py`), so approval is informed, not blind.
- **3b.** propose-review-apply + undo (ragfs's `.safety/`): side-effecting
  runs write an undo record first. An acting substrate that cannot be undone
  gets to act once.
- **3c.** Silence audit (premortem P1): every `except Exception: pass` in the
  act path becomes log-or-raise. The bridge-None scoping bug survived because
  failure presented as "HOME / no data". That failure mode is now gated in
  tests: a dead tool must produce an error row in the ledger, never a quiet
  default.

Gate: a scripted self-contradiction (belief says "endpoint X is dead", agent
told to use X) produces a HITL gate *with the contradicting claim attached*,
and the undo record reverses the act. `grep -c "except.*pass" brain/` trends
to zero on the act path.

---

## Phase 4 — Surface: kill chat-as-interface (weeks 8–9)

Survey §3: chat is what you build when the structure is not navigable. If
Phases 1–2 worked, the phone becomes a viewer of the substrate.

- **4a.** One **Timeline** activity replaces Feed + Transcript + Memory +
  Dreams browsing: events and claims in time order, contradictions visible
  as forks, grades inline. `cat .query/…` shape: search box over the ledger,
  results are rows, not prose.
- **4b.** **Ask** stays but becomes a convenience on top: every answer cites
  claim/event ids, tappable to the Timeline row. An answer with no citations
  is a UI bug.
- **4c.** **Devices** (wearable + ring status, remap, HUD mirror) and
  **Settings** remain. 14 activities → 4. Deleted screens leave no dead code
  (Phase-0 audit runs again here).
- **4d.** Widget shows next action / contradiction count, not a chat box.

Gate: dogfood week — all daily use through Timeline + Ask-with-citations.
Any question answered twice from chat without touching the ledger is a
Phase-2 retrieval failure filed as a bug, not a shrug.

---

## Phase 5 — Wearable as a first-class node (week 10+)

Only now does firmware change, because only now is there something worth
feeding.

- **5a.** Tilt-scroll and the 2×3 gesture grid stay exactly as-is (they are
  the right input for the hardware). What changes is uplink semantics:
  voice notes arrive as Events with duration + capture provenance, not bare
  text; photo tags arrive as claims with the sighting event as evidence.
- **5b.** On-device VAD gate output becomes an event field (`speech: true`,
  with calibration), so the ledger can distinguish "nothing said" from
  "nothing recorded" — currently indistinguishable downstream.
- **5c.** Presence off-body transition already force-stops capture; log it
  as a claim boundary (`valid_at` end for "wearer present"), which is what
  makes sensor gaps honest instead of silent.

Gate: on-metal walk — 10 minutes worn, Timeline shows capture / off-body /
photo / note events with durations, one induced contradiction resolved in
Phase-2 machinery. Same E2E the STATUS documents, but through the ledger.

---

## Standing rules (inherited from physis, restated because skipping one
caused most failures there)

1. Every phase names its control. No control run ⇒ not a result.
2. `NOT MEASURED` is legal. Implication is not.
3. Numbers not regenerable by a command in this repo get flagged.
4. A comment recording a failure gets updated, never deleted.
5. The model never authors structure. Swap it mid-phase at least once; if
   the belief state does not survive, the phase failed.
6. Cost depends on the question, not the history. Any tick that scales with
   total rows is a bug.
