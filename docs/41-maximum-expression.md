# docs/41 — Maximum expression: capture→belief, Jev oracle, phone subtraction, sovereignty

Status: in implementation (2026-09-19). The product's end state in one
sentence: the wearer's past becomes queryable and their present becomes
decidable, with the wearable as the only surface needed.

## 1. Capture→belief through-line

One gesture captures with a question attached; the belief layer answers from
the ledger with citations; the answer lands back on the OLED as the digest.
Rules:
- Voice note: the spoken question becomes the claim statement, the transcript
  locator becomes evidence.
- Photo: tag-and-discard result becomes evidence on an existing claim.
  Photos never auto-claim.
- Digest = claims-driven: active claims (top-confidence) + W7 triage + W8
  calendar due, pushed to HUD. Trigger reuses ACT_NOTES long-press — no
  protocol parity churn.

## 2. Jev oracle (read-only)

Jev (TypeSafe System One) answers typed questions about a ledger state —
noul/choice/score with calibrated probabilities — and scores claims. It is
an oracle AND a scorer, never an author:
- MAY: adjust claim confidence within [0,1]; answer agent questions
  (route? review? which option?) that feed thresholds in code.
- MAY NOT: create, contradict, supersede, or resolve claims. The ledger's
  deterministic machinery + human confirm own all authorship.
- Key absent (waitlisted) → scorer returns None, claims unchanged. All
  oracle paths are offline-testable with a mock transport.
- Key resolution: `TYPESAFE_API_KEY` aliased to `typesafe` in
  `brain/aikeys.py`. Endpoint `POST api.typesafe.ai/v1/systemone`.
- Thresholds named in code (`SCORE_THRESHOLD`, `AUTO_ROUTE_CONFIDENCE`).

## 3. Phone subtraction (audit-only first)

Audit every screen against "does a gesture or spoken answer already do
this?" Suspects: Chat (duplicates ACT_VOICE_CMD), Transcript (duplicates
ledger), Remap (advanced). Removals need explicit confirmation — a separate
step, never bundled with the audit.

## 4. Sovereignty egress audit

Every network egress in `brain/` + `agent/tools/` classified
source/sink/owner. Export path is the only unconfirmed egress. Anything
owner-classified is a documented exception or a bug ticket.

## 5. Loop perfection (done)

`just start` guard matches `system run` failures too (exit_code/process_success
in history output, not just `outcome=failure`). adb branch stays inert until
on-metal.

## Product gate

Three consecutive days where the wearer lived in the through-line
(capture → cited answer → confirmed act). Until then this is a design
wearing a product's clothes.
