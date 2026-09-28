# docs/38 — Phone-subtraction audit (docs/41 §3, audit-only)

Rule: a screen that duplicates what a gesture or spoken answer already does
is a candidate for removal. Audit only — removals need explicit confirmation.

## Keep (no wearable equivalent)

- HudMirror (+widget): the point of the phone is seeing the HUD at all.
- Ring: live gauges have no OLED equivalent (128×32 can't draw rings).
- Settings: setup surface; wearable has no keyboard.
- OAuth: browser sign-in is inherently phone-side.
- Onboarding: one-time setup.

## Subtract candidates (ranked)

1. **Chat screen** — duplicates ACT_VOICE_CMD (spoken question → spoken
   answer). Strongest candidate: the wearable path exists and is tested.
2. **Transcript screen** — duplicates the ledger (notes/transcripts API).
   Merge into Memory as a view, not a screen.
3. **Remap screen** — advanced gesture remap. Demote to Settings section,
   not a top-level destination. DONE 2026-09-19: drawer entry removed,
   "Button remap…" button added to Settings; RemapActivity kept.
4. **Feed/Dreams/Experiences/Entities** — four browsers over brain stores
   (Memory browser pattern already covers search+filter). Consolidate into
   Memory with type filters.
5. **Vision screen** — duplicates ACT_PHOTO + ACT_WORLD_* gestures. Keep
   only as the camera viewfinder (capture needs a view); drop its Q&A.
6. **Cost screen** — keep, but read-only (no wearable equivalent for
   spend review; cheap to keep).

## Merge targets

- Memory becomes the single store browser (notes, transcripts, entities,
  experiences, dreams via type filter).
- Settings absorbs Remap.

## Gate

User confirms the removal list. Removal itself is a separate app-update
loop (recall → work → apk-gate → remember), one screen per loop.
