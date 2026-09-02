---
id: CY-003
track: cyclops
phase: 2
status: todo
rung: 2
depends: [CY-001]
gate: "python3 tests/run_tests.py tests/test_vad.py && make test && make proto"
commit: "branch agent/CY-003"
---

# VAD + light speaker handling on the brain (Omi parity, CPU-budget aware)

## Why
Omi's backend runs VAD + diarizer as core pipeline stages; without VAD, every
minute of silence is transcription cost and every note inherits babble. The
brain runs on pansa (CPU) — the budget rule is: anything added must run
real-time on ONE pansa core.

## Steps
1. VAD first: energy-based, zero-dep, deterministic (repo ethos) — a simple
   hysteresis gate over RMS with hangover. Ship that before any neural VAD;
   measure note-quality delta first.
2. Diarization-lite: DO NOT build a neural diarizer. Segment metadata
   (gaps > 2s = new segment) is enough for meeting notes v1. Re-evaluate
   after CY-100 discovery.
3. Wire into pipeline: capture → VAD gate → transcriber (faster-whisper if
   present, stub otherwise) → extractor. VAD decision recorded in note meta.
4. Benchmark: scripts/bench-vad.py — minutes of fixture audio vs segments
   produced vs wall time on one core; committed numbers in the report.

## Tests you must add
- **Unit:** hysteresis gate over synthetic RMS streams (silence/speech/
  hangover edges); deterministic across runs.
- **Integration:** pipeline with VAD on fixture audio: silence produces zero
  transcription calls; note meta records vad=on; fallback path (VAD off)
  unchanged (contract with existing 238 tests intact).

## Gate
```bash
python3 tests/run_tests.py tests/test_*.py
make test && make proto
python3 scripts/bench-vad.py --assert-rt-one-core
```

## Never
- Add numpy/scipy for this (zero-dep rule) — or if truly unavoidable, a
  design note + human decision first. Break the stub transcriber path (tests
  must pass with NO model files).
