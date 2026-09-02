---
id: CY-002
track: cyclops
phase: 1
status: todo
rung: 2
depends: [CY-000]
gate: "python3 tests/run_tests.py tests/test_physis_sink.py"
commit: "branch agent/CY-002"
---

# Notes → physis: the wearable feeds the semantic store

## Why
Two home products, zero integration. Cyclops produces the highest-value
semantic content on the fleet (what you thought during the day); physis is a
semantic engine begging for content. A sink that mirrors notes into a physis
store makes 'ask my wearable history anything' work through physis recall —
and gives physis a demo story no benchmark can (OP-002 outreach material).

## Steps
1. Follow the Obsidian-sink pattern (#37): a sink is additive, opt-in via
   env (CYCLOPS_PHYSIS_URL), fails soft (physis down = notes still stored
   locally; retry queue with cap).
2. Sink posts notes to physis via its HTTP surface; tag kind
   (task/reminder/decision/idea) and device. Embedder consistency: physis
   embeds server-side with ITS embedder — the sink sends text, never
   embeddings.
3. Idempotency: note id = sink key; re-running must not duplicate nodes.
4. Docs: one paragraph in README features + the demo command that shows it.

## Tests you must add
- **Unit:** payload shaping, idempotency key, retry-queue cap behaviour.
- **Integration:** tests/test_physis_sink.py against a fixture HTTP server
  (stdlib http.server in the test): success, physis-down (soft fail + queue),
  duplicate note (no second POST of same id).

## Gate
```bash
python3 tests/run_tests.py tests/test_brain.py tests/test_physis_sink.py
```

## Never
- Send audio or raw transcripts by default (kinds + summaries only; full text
  behind explicit env). Make physis a hard dependency of capture.
