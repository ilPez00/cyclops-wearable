---
id: CY-005
track: cyclops
phase: 2
status: todo
rung: 2
depends: [CY-000]
gate: "test -f .github/workflows/android.yml && gh run list --repo ilPez00/cyclops-wearable --limit 1 2>/dev/null | grep -q pass || test -f packets/reports/CY-005.md"
commit: "branch agent/CY-005; in this repo"
---

# Android app (Kotlin): CI that actually builds the APK

## Why
STATUS.md says Kotlin `:core:test` / APK is "CI-only (no local SDK)" — but
there is no evidence a green CI exists today, and the FCM-cascade work
(branch history: 'route FCM cascade through OmniRoute') landed without a
verified mobile path. Untested Kotlin in a repo with byte-precise C++ is the
weak flank.

## Steps
1. GitHub Actions workflow: JDK 17, gradle :core:test + assembleDebug on
   push/PR; cache gradle. Runs on ubuntu runner (SDK install via
   android-actions/setup-android or gradle's auto).
2. Fix whatever :core:test surfaces (it has never been seen green locally —
   expect rot).
3. FCM cascade: write the current routing down (docs/) — what cascades,
   in what order, with which fallbacks — and a unit test for the route
   decision table.
4. Release path: assembleRelease with a keystore from GH secrets (HUMAN
   creates the keystore; agent wires the workflow referencing secret NAMES
   only).

## Tests you must add
- **Unit (Kotlin :core):** route-decision table for the cascade; note-parse
   parity with the Python extractor for the fixture set (the two must agree —
   wire-contract thinking, applied to notes).

## Gate
```bash
gh run list --repo ilPez00/cyclops-wearable --limit 3   # green build exists
```

## Never
- Commit keystores or FCM keys. Let the Kotlin note parser drift from the
  Python one without a parity test.
