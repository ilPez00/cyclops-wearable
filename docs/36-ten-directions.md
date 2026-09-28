# docs/36 — Ten directions: senses, world depth, phone, belief payoffs

Companion to 34 (brain as substrate) and 35 (phone as computer, world as
interface). Each direction is scoped to what the hardware and codebase
actually support — no new sensors, no cloud account, no rewrite. Each names
its phase home (34/35 phase it extends), its build order slot, and its gate.
Build order is by value-per-effort within each group, not by number.

Related work already in tree is named so nothing is rebuilt: speaker turns
(transcriber), `brain/sightings.py` (#1 zero-photo), `brain/world.py`
(registry), `WORLD_HOWTO` (27), `agent/tools/calendar.py`, `brain/dreams.py`,
`brain/hitl.py` gates, CHOICE/AGENT views, `bind()` remap grid.

---

## Group 1 — Senses you already own but don't use

### W1. Conversation memory: who was that (order 1)

Transcribe runs, entities extract, but nothing links "the voice from
Tuesday" to a name or a follow-up. Face *recognition* stays off-limits;
voice *re-identification* is not: "same voice as the 2 PM meeting, still
unnamed". Smallest version: speaker-diarized turns + "who was that?"
teachable in World, same registry pattern as `brain/world.py` (tag =
voiceprint hash, answer = name + context). A taught voice resolves
everywhere it recurs; an untaught one stays an honest unnamed cluster,
never a guessed name.

Home: 34 Phase 1 (new event kind) + 35 bridge (World teach surface).
Gate: two meetings, same guest, second transcript auto-labels "same voice
as Tuesday" + teach-once-resolves-everywhere demo. No name is ever
asserted without a registry entry — same honesty rule as world misses.

### W2. Sound as a sense, not just speech (order 2)

The mic hears doors, kettles, traffic, alarms — all discarded after
transcription. A tiny on-device classifier (doorbell, alarm, name-called,
silence-too-long for elderly check-ins) turns the wearable into an
attention device, including for the hard-of-hearing. Nothing persists
except the event row. VAD gate output already exists in firmware; this
adds a sound-class field beside it, same fail-closed shape.

Home: 34 Phase 5b (VAD field) + firmware classifier.
Gate: on-metal week — every doorbell/alarm within earshot becomes a
ledger event with duration; zero false pages to the OLED, counted not
asserted. False-page budget: ≤1/week or the classifier is demoted to
ledger-only (no buzz).

### W3. Phone camera as second wearable eye (order 3)

World gestures use the XIAO camera; the phone camera sits idle. A-double
(photo) fires the phone pipeline for every room the pendant isn't
charged for — same `capture_and_tag`, different source, provenance says
which. Covers the dead-battery case and the "pendant on the desk" case
with zero new hardware.

Home: 35 Phase C (phone as sensor).
Gate: same tag taught once, resolvable from either camera; every world
answer carries `source: pendant/phone` and the miss log distinguishes
"no frame" from "no knowledge".

---

## Group 2 — World-bridge depth (extends the shipped loop)

### W4. Procedural overlays: how-to with state (order 1 — demo pick)

WORLD_HOWTO answers in three steps today and forgets. Real version: the
answer is a checklist the OLED walks one step per tilt-scroll, each step
confirmable with A-single. Recipe mode, fix-the-bike mode, first-aid
mode. The state machine already exists (CHOICE/AGENT views); it needs a
step pointer + per-step confirm, not a new view. Registry stores the
procedure once ("pasta al pomodoro: 5 steps"), gestures replay it anywhere.

Home: 35 bridge + firmware step pointer.
Gate: cook one taught recipe start-to-finish on OLED alone, phone in
pocket. Steps advance, confirm, and survive a screen nap. Miss on step 3
("don't know this step — teach me") is honest, not blocking.

### W5. Price with memory (order 2)

WORLD_PRICE judges one tag today. With a taught registry of past prices
("espresso at Bar Roma €1.20, taught March"), judgement becomes
comparative: "€1.80 here — 50% over your usual". No network, no price
API; your own history is the database. Price entries are claims with the
sighting as evidence (34 Phase 2 shape), so a disputed price ("no, it
was €1.50") becomes a contradiction, not an overwrite.

Home: 35 bridge + 34 Phase 2 (claims).
Gate: three taught prices, one new sighting → comparative judgement on
the OLED quoting the remembered baseline. One induced price dispute
resolves through the contradiction machinery with a Revision.

### W6. Read-then-translate: the travel feature (order 3)

TRANSLATE handles spoken words; nothing handles the sign, menu, or label
in front of you. WORLD_READ + translate in one gesture is a single
pipeline addition (OCR output feeds the existing translator, answer
shows both lines). Highest value-per-line-of-code in this group.

Home: 35 bridge (one pipeline joint).
Gate: five foreign-language signs/menus read + translated on OLED, phone
in pocket, airplane mode on (local models only — the travel case is
roaming, so the LAN must not be required).

---

## Group 3 — Phone-as-computer (extends 35)

### W7. Notification triage on the OLED (order 1 — stickiness pick)

The phone knows what's urgent; the wearable never hears it. A
Notification-listener source feeds the ledger; only priority events buzz
the wearable ("gate approved", "calendar in 10", "message from X").
Consent-gated per app, ledger-first (every buzz cites its event row).
This is the feature that makes Cyclops a phone you don't have to look at.

Home: 35 Phase C (phone as sensor) + `brain/hitl.py` priority.
Gate: dogfood week — phone stays in pocket 8h/day; every OLED buzz is
rated worth-it/not; buzz precision ≥80% or the priority rules get tuned,
not the user's tolerance. No buzz without a ledger row, ever.

### W8. Calendar that closes the loop (order 2)

`calendar.py` exists as a tool but nothing closes the loop: meeting
starts → auto-arm transcribe; meeting ends → notes filed; late (GPS says
still home) → "leave now, 20 min walk" on the OLED. All pieces exist;
only trigger wiring is missing. Triggers are ledger queries (34 Phase 1
shape: "what is happening now" over events), not cron hacks — so a
rescheduled meeting moves the arms automatically.

Home: 35 Phase A (ledger local) + existing calendar tool.
Gate: one real week — every meeting armed/filed without manual capture,
one late-leave prediction delivered before departure. A missed arm is a
filed bug with the ledger query attached.

---

## Group 4 — Belief-layer payoffs (extends 34 Phase 2)

### W9. Contradiction on the wrist (order 1 — moat pick)

Phase 2 detects disagreements; the killer surface is one OLED line:
"Tuesday you said X, today you said Y — which holds?" with A-single /
B-single as yes/no (ACT_CONFIRM_YES/NO already exist and already route
through HITL). The 2-button device becomes a truth-maintenance
instrument. Nothing in the survey has this — it requires the belief
layer, which no competitor ships.

Home: 34 Phase 2 + existing confirm path.
Gate: induced contradiction resolved from the wearable alone, phone in
pocket; Revision lands in the ledger with both evidence rows intact.
Three such resolutions in dogfood without opening the app.

### W10. Morning briefing from the dream loop (order 2)

`dreams.py` consolidates and nobody reads it. One morning digest —
contradictions resolved overnight, things to teach (miss log top 3),
today's likely questions from calendar + history — pushed to the OLED at
wake. Turns a background job into the reason to wear the thing. Content
is claims + events with ids, never prose without citations (34 Phase 4b
rule applies to the wrist too).

Home: 34 Phase 2 + W8 calendar.
Gate: five consecutive mornings the briefing answers a real question
before it is asked (taught tag, known meeting, open contradiction).
Any uncited sentence is a UI bug, same rule as Ask.

---

## Build order across groups (value per effort)

1. W4 (demo) + W6 (travel) — world loop goes from impressive to indispensable.
2. W7 (stickiness) + W8 (loop-closing) — phone earns its pocket place.
3. W1 (voices) + W9 (wrist truth) — belief layer becomes visible and uncopiable.
4. W3 (second eye) + W5 (price memory) + W2 (sound sense) + W10 (briefing) —
   depth and polish on proven loops.

No group starts until the phase it extends is gated (34/35 gates are the
prerequisites; W9 without Phase 2 is a chat box with opinions). Miss logs,
honesty rules, and standing rules 1–7 carry over unchanged — in
particular: no stub dressed as knowledge, no buzz without a ledger row,
no answer without a citation.

---

## Shipped so far (2026-09-18)

| direction | state | where | gate |
|---|---|---|---|
| W6 read-then-translate | **shipped** | `brain/translator.py` (Ollama gemma3:4b → dict), `world.py` `translate_fn`, Kotlin mirror | live: "Dove si trova la stazione?" → "Where is the station?"; 4 translator tests incl. `CYCLOPS_NO_OLLAMA` offline path |
| W4 procedural overlays | **shipped** | `hud.h` `show_steps`/`step_confirm` + `{"kind":"steps"}` DISPLAY_CMD, `world.split_steps`, `hud_bridge` | host tests (tilt/confirm/finish/state-leak) + JSON ingest test |
| W8 calendar loop | **shipped (logic)** | `brain/calendar_loop.py` (`due_actions` pure fn), `/api/calendar/tick`, minute scheduler, calendar tool `at`/`duration_min`/`place` | 7 tests: lifecycle, idempotence, no-leave-without-place, JSON state roundtrip, bridge apply |
| W7 notification triage | **shipped (rules + listener)** | `:core` `Triage.kt`, `CyclopsNotificationListener`, `/api/notify` | 7 Kotlin tests (self-pkg drop, trust, urgent promote, summary drop, OLED budget) + route test (buzz vs silence) |
| 34 Phase 2 belief layer | **shipped (core)** | `brain/claims.py`: claims + evidence + deterministic reinforce/supersede/contradict, bi-temporal, append-only snapshots + revisions, `structure_hash` | 12 tests incl. evidence survival on supersede, revision log, hash identity/time-freedom |
| W9 contradiction on the wrist | **shipped (brain + API)** | `HudBridge.note_claim`/`resolve_contradiction`, HITL gate dedupe, `/api/claims` + `/api/claims/resolve`, `CyclopsApi.claims/resolveClaim` | bridge test (surface + revert + no-op) + route test (surface, resolve, status flips) |

Not yet on metal / still gated by real feeds: W8's "one real week" and
W7's "8h/day, ≥80% worth-it" need a live calendar source and a real phone
with Notification access granted. The logic is proven; the field gates
are open. Remaining: W1, W2, W3, W5, W10, and W9's on-wrist resolution
(the brain/API halves are done; the 2-button physical confirm is the
remaining on-metal step).
