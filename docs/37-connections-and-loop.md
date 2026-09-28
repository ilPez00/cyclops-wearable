# docs/37 — External connections + the physis-assisted app update loop

Two halves. (A) How Cyclops connects to outside apps/services without
becoming their client. (B) How the Android app gets updated with physis
itself, since that update is the repetitive task physis was built to carry.

---

## A. External connections: the ledger stays the center

Principle (from 34 §3, restated because every integration will try to
violate it): **outside services are sources and sinks of the ledger, never
its owners.** A service delivers events in and takes actions out. It never
stores the belief, never authors the structure, never becomes required for
the phone to work (35 rule 7). Any integration that needs the network, the
PC, or the vendor's account to answer a question is a bug, not a feature.

That gives every connection the same three-part shape:

```
inbound  vendor event -> Event{source: <service>, ...} appended to ledger
digest   belief layer claims over those events (same contradiction rules)
outbound agent act -> vendor API, pre-act checked + HITL-gated + undoable
```

Existing code that already fits: `brain/display_telegram.py` (sink),
`brain/obsidian.py` (sink), `agent/tools/whatsapp.py` (import),
`agent/tools/calendar.py` (local file calendar), OAuth device/PKCE flows +
`OAuthActivity` picker (auth without secrets on device).

### A1. Messaging: WhatsApp, Telegram, SMS (read + triage, never send-first)

Today: WhatsApp is a manual .txt export parse; Telegram is a sink via
TGPmini. Both one-directional and manual.

- Inbound becomes a ledger source: new messages arrive as events
  (`source: whatsapp/telegram`, duration 0, locator = chat/thread id).
  WhatsApp via the export watcher first (file appears -> ingest -> events),
  live via the linked-device path only if it stays local-first.
- Digest: unanswered questions addressed to the wearer become claims;
  the W7 notification triage rules decide what buzzes the OLED.
- Outbound: replies are drafted, never sent, until confirmed on the
  wearable (ACT_CONFIRM_YES path already exists) or in Ask. No
  auto-reply, ever — the never-auto-commit principle covers vendors too.
- Gate: one week where every message the wearer actually answered is in
  the ledger first, and zero messages were sent without a confirm row.

### A2. Calendar + mail (close W8, then extend to inbox)

W8 already scopes the calendar loop (arm/file/late-leave). Mail is the
same shape one layer wider: newsletters and receipts become events,
questions addressed to the wearer become claims, triage decides the buzz.
Gmail/IMAP via OAuth (the Google PKCE entry already in the catalog);
local Maildir mirror so the ledger never depends on the vendor's search.
Outbound drafts only, same confirm rule as A1.

Gate: the W8 gate plus "every mail I replied to this week was a ledger
event first". Vendor search is never queried at question time — the
ledger is the index (34 Phase 0 retrieval numbers apply to mail too).

### A3. Notes/knowledge: Obsidian (already a sink — make it a peer)

`brain/obsidian.py` writes notes + daily pages today. Peer means reads
too: vault edits become events (source: obsidian, locator = file path),
so marginalia written on the laptop shows up in Timeline and in Ask
citations. Conflict rule is the ledger's, not the filesystem's: both
revisions kept, contradiction machinery resolves (35 Phase E shape, local
first). No Obsidian plugin required — folders of Markdown, same as now.

Gate: edit a note in Obsidian, ask about it on the phone in airplane
mode, get a cited answer. Either side offline a week, resync lossless.

### A4. Health: ring today, Health Connect next

`brain/health.py` + ring BLE already feed HR/SpO2/battery. Android Health
Connect is the same inbound shape with a phone-native source (sleep,
steps, workouts the ring never sees). Claims over both ("resting HR trend
up 2 weeks") with the ring as evidence, not a dashboard. Outbound: none —
health data never leaves the ledger except as an explicit export the user
confirms per destination.

Gate: one month of ring + Health Connect rows merged; a trend question
answered with citations from both sources. No health row ever sent
anywhere without a confirm row.

### A5. Media + voice: Spotify/music control, voice assistants (outbound only)

Music control was in the original roadmap gaps and stays outbound-only:
play/pause/next as agent acts from a wearable gesture, pre-act checked
like any act. No listening-history ingest — playback state is not
evidence about the world, and ingesting it would be capture without a
question (34 §3 reject: unbounded capture). Voice assistants (Alexa etc.)
are skipped entirely: a second interpreter that authors state would
reintroduce the failure 34 exists to remove.

Gate: gesture-driven transport control works in airplane mode against
downloaded media; nothing about playback ever appears in the ledger
unless the wearer explicitly notes it.

### A6. Maps/places: the world registry's public half (W5 extended)

W5's price memory is private history. Places add a public, cached layer:
taught tags ("Luigi's") gain coordinates + opening hours from an offline
tile/POI pack, never a live API at question time. Navigation (ACT_NAV)
resolves against taught places first, cached POIs second, live network
never — the roaming case (W6 gate) is the design case. A place the system
navigated to becomes a claim with the trip as evidence.

Gate: navigate to three taught places in airplane mode; each arrival
logged with duration. No position fix ever leaves the device.

### What is explicitly NOT connected

- Anything requiring a cloud account as the sync owner (34/35 rule:
  whoever hosts the sync owns the past).
- Social feeds (ingest without a question; unbounded capture).
- A second AI interpreter with write access (competing memory author).
- Payment, banking, or anything moving money (irreversible acts outside
  the undo design — 35 Phase E undo covers vendor acts or the vendor is
  read-only).

---

## B. Updating the app with physis (the dogfood loop)

The Android app update is exactly the repetitive task physis's dev loop
was built for: recall what was tried → do the work → run the gate →
remember the outcome with a verdict. `~/dev/physis-pro/justfile` already
ships it (`recall`, `dev-loop`, `note`); the scripts are offline and need
no server. Cyclops adopts the loop instead of re-deriving it.

### B1. The loop, concretely (per app change)

```
<recall>   # verdict failure = already tried and failed, don't repeat
<do the work>                 # Kotlin + Python + firmware, same session
<fast gate>                   # :core:test + assembleDebug + python suite + make test/proto
<remember>                    # failure / success, with evidence refs
```

Implemented as `/home/gio/cyclops/justfile` (2026-09-19): `just start`
(recall + past-failure guard + predict), `just apk-gate` (the five gates,
for iteration), `just update` (final gate + adb install when a
phone is attached + auto-remember with gate numbers). Iterate with
`apk-gate`; open with `start`; close once with `update`.

**Re-pointed to physis-next (2026-09-28, docs/43 §6).** physis-pro was retired
2026-09-20 and its CLI (`system history|remember|predict`) no longer exists, so
the loop was dead. physis-next has no `system` subcommand either — those verbs
live on its MCP surface — so the loop now drives `scripts/physis_mcp.py`, one
`tools/call` per invocation against a running server:

```
just physis-serve      # physis serve --http 127.0.0.1:19876 --path <PHYSIS_ROOT>
just recall "<task>"   # -> MCP physis.history
just remember "<outcome>" success|failure   # -> MCP physis.remember
```

No server ⇒ the scripts print `physis-next unreachable` + the start command on
stderr and exit 2; `just start`/`just update` treat that as an empty history, so
the past-failure guard never produces a false BLOCK and never silently passes.
The old licence/keygen caveat is gone with physis-pro — nothing here needs a
licence, a model, or a network beyond loopback.

Verdict discipline (inherited, restated because it is the whole value):
- `-1` means tried-and-failed — the next session must not retry the same
  approach without new evidence. (Example candidates already in tree:
  Java-style setters on Kotlin `object` members; `hint =` shadowing
  `TextView.hint`; Python-regex scripted Kotlin edits.)
- `0` means inert — built but unproven (e.g. an uncompiled edit, a test
  that never ran on metal).
- `+1` means worked with a green gate named in the note.

### B2. What gets recorded (and where)

Outcome notes live in physis's store (`.physis/`), not in cyclops docs —
the memory belongs to the loop that replays it. What goes in:

- Failing approach + error string verbatim (compiler errors are the most
  reusable memory: `Val cannot be reassigned` → the `hint` fix).
- Gate results as numbers (51/51, 415/415, BUILD SUCCESSFUL), never
  adjectives.
- Hardware facts that cost a session (XIAO invisible on USB from pansa;
  `lsusb` shows only the LaCie drive) so the next session checks
  attachment before planning on-metal work.

Cyclops docs keep the design (34/35/36/37); physis keeps the outcomes.
Design without outcomes is a folder with opinions (34 §5, applied to
ourselves).

### B3. The standing app-update checklist (the repetitive part, written once)

Every app change runs the same five gates; the loop remembers which ones
bite:

1. `:core:test` — protocol + bridge logic (51 tests, includes world-id
   parity with `hud.h`).
2. `:app:assembleDebug` — full compile (catches the Kotlin `object`
   property class of bug).
3. Python suite (`tests/run_tests.py`) — brain + server + world (415+).
4. `make test` + `make proto` in firmware/ — host logic + wire contract.
5. Wire-id parity grep: `ACT_*` ids equal across `hud.h`,
   `protocol_v2.py`, Kotlin `HudBridge` (today enforced by three
   independent tests asserting 24–27; a single source of truth is the
   standing improvement — see B4).

### B4. First physis-assisted improvements to the loop itself

- Single source of truth for ACT ids: generate `protocol_v2.py` constants
  + Kotlin `const val`s from `hud.h` (or a small `protocol/acts.yaml` all
  three read). Kills the parity-test class of failure instead of testing
  for it.
- `just recall` wired into the session start for cyclops work: before
  touching the app, recall; after the gate, note. (Live again via
  physis-next — see the §B1 re-point note above.)
- Capability check ported: physis's `declared-never-called` discipline
  (34 Phase 0b) becomes a script over `brain/*.py` + the Kotlin sources,
  run in gate 3. Dead code is the failure mode both repos share.
  DONE 2026-09-19: `scripts/dead_calls.py` + `just capabilities` (6th gate).

Gate for B as a whole: three consecutive app updates where the loop
caught a repeat (a `-1` verdict stopped a retry, or a checklist gate
caught what a previous session missed). Until then it is a proposal,
not a practice.
