---
id: CY-004
track: cyclops
phase: 2
status: todo
rung: 2
depends: [CY-000]
gate: "make test && make proto && pio run -e xiao_selftest -e xiao_128x32_i2c"
commit: "branch agent/CY-004; firmware changes one commit per concern"
---

# Firmware: OTA hardening + long-run battery truth

## Why
OTA is implemented at the protocol level (make proto covers it) but the
long-run story — battery drain over a worn day, brown-out during OTA, flash
wear on the SD logging path — is unmeasured. A wearable that dies at 14:00 is
a necklace.

## Steps
1. Long-run harness: a scripted 8h bench (device + host simulator logging
   status_json deltas) measuring: battery slope, reconnects, dropped frames,
   SD write volume. Runs unattended; output committed to reports (not repo
   artifacts).
2. OTA safety review: power-loss mid-write, version rollback, signature/check
   policy. Fix what the review finds; the framing contract tests must still
   pass byte-identical.
3. SD wear: current logging frequency → write-volume estimate; add a write-
   coalescing option if the estimate is abusive.

## Tests you must add
- **Host-sim (make test):** battery-slope model test (a simulated day stays
  above the documented floor); OTA power-loss resume path.
- **Proto (make proto):** OTA frames under the byte-identical contract; new
  META fields additive only.

## Gate
```bash
make test && make proto
pio run -e xiao_selftest -e xiao_128x32_i2c   # builds clean
```

## Never
- Break ADPCM/frames byte-compatibility (that contract is sacred — STATUS.md
  history). Ship OTA changes only after a bench run on the dev unit (CyclUno
  or XIAO), never untested.
