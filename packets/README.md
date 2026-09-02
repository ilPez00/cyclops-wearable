# cyclops-wearable work packets (device + brain + app + firmware)

Read PROTOCOL.md first. Repo-specific rules:

- **Canonical repo is THIS one** (github.com/ilPez00/cyclops-wearable, branch
  main). The sibling clone ~/dev/cyclops (feather) points at a LOCAL git
  mirror and sat on branch freerouting-omniroute — that is CY-000's problem,
  not a licence to push there.
- Verification is three-gated and all three exist: `python3 tests/run_tests.py
  tests/test_*.py` (zero-dep; 238 passing at last count), `make test` +
  `make proto` (firmware host gates), `pio run` (PlatformIO device builds).
  Never weaken the wire-contract tests (C++/Python byte-identical framing,
  ADPCM contract) — they are the reason on-metal bring-up worked.
- Hardware facts that took a session to learn (STATUS.md 2026-07-12): mic is
  PDM only (clk GPIO42, data GPIO41); BLE notify throughput ~2 KB/s drove the
  ADPCM decision; missing screen/IMU/SD must degrade gracefully.
- No pip, no API keys for the core test path — zero-dependency is a feature.
- Consent gating for incoming device commands (phone drives capture/HUD) is a
  trust boundary, not a UX nicety.
